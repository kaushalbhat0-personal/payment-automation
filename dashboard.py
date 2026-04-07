import json
import logging
import re
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread

logger = logging.getLogger(__name__)
_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
_AUTO_REFRESH_SECONDS = 30
_COLUMNS = [
    "payment_id",
    "name",
    "email",
    "contact",
    "amount_inr",
    "status",
    "preferred_batch",
    "mode",
    "captured_at_ist",
]
_COLUMN_ALIAS_MAP = {
    "phone": "contact",
    "amount": "amount_inr",
}


def _format_inr(amount: float) -> str:
    # Use the Rupee symbol and Indian-style readability.
    return f"₹{round(float(amount)):,.0f}"


def _clean_batch(value: Any) -> str:
    text = str(value).strip()
    # Remove timing text inside brackets for cleaner chart labels.
    text = re.sub(r"\s*\([^)]*\)|\s*\[[^\]]*\]", "", text)
    return text.strip()


def _normalize_sheet_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Make headers consistent across manual entries and webhook-driven rows.
    normalized_columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in df.columns
    ]
    df = df.copy()
    df.columns = normalized_columns

    # Align known alternate names to internal schema.
    for source, target in _COLUMN_ALIAS_MAP.items():
        if source not in df.columns:
            continue
        if target not in df.columns:
            df = df.rename(columns={source: target})
            continue
        target_values = df[target].astype(str).str.strip()
        source_values = df[source].astype(str).str.strip()
        df[target] = df[target].where(target_values != "", df[source])
        df = df.drop(columns=[source])

    return df


def _parse_captured_at_ist(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    missing_mask = parsed.isna()
    if missing_mask.any():
        parsed.loc[missing_mask] = pd.to_datetime(
            series.loc[missing_mask],
            errors="coerce",
            dayfirst=True,
        )
    return parsed


def _status_cell_style(value: Any) -> str:
    status = str(value).strip().lower()
    if status == "captured":
        return "background-color: #DCFCE7; color: #166534; font-weight: 600;"
    if status == "failed":
        return "background-color: #FEE2E2; color: #991B1B; font-weight: 600;"
    return ""


def _style_payments_table(df: pd.DataFrame):
    return (
        df.style.map(_status_cell_style, subset=["status"])
        .set_properties(
            **{
                "font-size": "0.92rem",
                "padding": "0.42rem 0.55rem",
            }
        )
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#F3F4F6"),
                        ("color", "#111827"),
                        ("font-weight", "600"),
                        ("padding", "0.5rem 0.6rem"),
                        ("border-bottom", "1px solid #E5E7EB"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [("border-bottom", "1px solid #F3F4F6")],
                },
                {
                    "selector": "tbody tr:nth-child(even) td",
                    "props": [("background-color", "#FAFAFA")],
                },
            ]
        )
    )


def _load_service_account_info() -> dict[str, Any]:
    raw_value = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_value is None:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set in Streamlit secrets")
    if isinstance(raw_value, dict):
        return raw_value

    raw_json = str(raw_value).strip()
    if not raw_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON in Streamlit secrets is empty")

    candidates = [raw_json]
    # Some platforms wrap the full JSON value in quotes.
    if (raw_json.startswith('"') and raw_json.endswith('"')) or (
        raw_json.startswith("'") and raw_json.endswith("'")
    ):
        candidates.append(raw_json[1:-1])

    parse_errors: list[str] = []
    parsed: Any = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            # Handle double-encoded payloads such as "{\"type\":\"service_account\",...}".
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            break
        except json.JSONDecodeError as exc:
            parse_errors.append(
                f"{exc.msg} (line {exc.lineno}, column {exc.colno}, char {exc.pos})"
            )

    if parsed is None:
        reason = " | ".join(parse_errors) if parse_errors else "Unknown JSON parsing error"
        logger.error(
            "Invalid GOOGLE_SERVICE_ACCOUNT_JSON in Streamlit secrets. Raw length=%s. Reason=%s",
            len(raw_json),
            reason,
        )
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON in Streamlit secrets is invalid JSON. "
            f"Exact reason: {reason}"
        )

    try:
        if not isinstance(parsed, dict):
            logger.error(
                "GOOGLE_SERVICE_ACCOUNT_JSON parsed to unexpected type: %s",
                type(parsed).__name__,
            )
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must decode to a JSON object")
    except RuntimeError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while parsing GOOGLE_SERVICE_ACCOUNT_JSON")
        raise RuntimeError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must decode to a JSON object")
    return parsed


def _get_worksheet():
    service_account_info = _load_service_account_info()
    creds = Credentials.from_service_account_info(service_account_info, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    google_sheet_id = st.secrets.get("GOOGLE_SHEET_ID")
    if not google_sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is not set in Streamlit secrets")
    worksheet_name = st.secrets.get("GOOGLE_WORKSHEET_NAME")
    if not worksheet_name:
        raise RuntimeError("GOOGLE_WORKSHEET_NAME is not set in Streamlit secrets")
    sh = gc.open_by_key(str(google_sheet_id))
    return sh.worksheet(str(worksheet_name))


@st.cache_data(ttl=30, show_spinner=False)
def fetch_payments_df() -> pd.DataFrame:
    # Streamlit doesn't automatically load `.env` in all environments.
    load_dotenv(override=False)
    ws = _get_worksheet()

    # Assumes row 1 is headers; converts each row to a dict keyed by header.
    records: list[dict[str, Any]] = ws.get_all_records(default_blank="")
    df = pd.DataFrame.from_records(records)
    df = _normalize_sheet_columns(df)

    # Ensure exact column order; add missing columns.
    for col in _COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[_COLUMNS]

    return df


def main() -> None:
    st.set_page_config(page_title="Payments Dashboard", layout="wide")
    st.title("Payments Dashboard")
    st.caption("Auto-refresh: every 30 seconds (data only)")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.25rem; padding-bottom: 1.25rem;}
        div[data-testid="stMetricValue"] {font-size: 1.35rem;}
        div[data-testid="stMetricLabel"] {font-size: 0.95rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if fragment is None:
        st.warning(
            "Auto-refresh is unavailable in this Streamlit version. "
            "Upgrade Streamlit to enable periodic data refresh without resetting filters."
        )

        def render_dashboard():
            _render_dashboard_body()
    else:

        @fragment(run_every=_AUTO_REFRESH_SECONDS)
        def render_dashboard():
            _render_dashboard_body()

    def _render_dashboard_body() -> None:
        try:
            df = fetch_payments_df()
        except Exception as exc:
            st.error(str(exc))
            st.stop()

        search_query = st.text_input("Search (name, email, phone)", key="search_query")

        filter_col1, filter_col2 = st.columns(2)
        batch_options = ["All"] + sorted(
            [v for v in df["preferred_batch"].dropna().astype(str).unique() if v.strip()]
        )
        mode_options = ["All"] + sorted(
            [v for v in df["mode"].dropna().astype(str).unique() if v.strip()]
        )

        selected_batch = filter_col1.selectbox(
            "Preferred Batch", batch_options, index=0, key="selected_batch"
        )
        selected_mode = filter_col2.selectbox("Mode", mode_options, index=0, key="selected_mode")

        filtered_df = df.copy()
        if selected_batch != "All":
            filtered_df = filtered_df[filtered_df["preferred_batch"] == selected_batch]
        if selected_mode != "All":
            filtered_df = filtered_df[filtered_df["mode"] == selected_mode]
        if search_query.strip():
            query = search_query.strip()
            search_mask = (
                filtered_df["name"].astype(str).str.contains(query, case=False, na=False)
                | filtered_df["email"].astype(str).str.contains(query, case=False, na=False)
                | filtered_df["contact"].astype(str).str.contains(query, case=False, na=False)
            )
            filtered_df = filtered_df[search_mask]

        captured_at_series = _parse_captured_at_ist(filtered_df["captured_at_ist"])
        filtered_df = (
            filtered_df.assign(captured_at_ist_dt=captured_at_series)
            .sort_values("captured_at_ist_dt", ascending=False, na_position="last")
            .drop(columns=["captured_at_ist_dt"])
        )

        amount_numeric = pd.to_numeric(filtered_df["amount_inr"], errors="coerce").fillna(0.0)
        total_revenue = float(amount_numeric.sum())
        total_students = int(len(filtered_df))
        unique_batches = int(
            filtered_df["preferred_batch"].replace("", pd.NA).dropna().nunique()
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Revenue", _format_inr(total_revenue))
        c2.metric("Total Students", f"{total_students:,}")
        c3.metric("Unique Batches", f"{unique_batches:,}")

        non_empty_batch_df = filtered_df[
            filtered_df["preferred_batch"].astype(str).str.strip() != ""
        ].copy()
        if non_empty_batch_df.empty:
            top_batch_name = "-"
            top_batch_revenue = 0.0
        else:
            batch_revenue = (
                non_empty_batch_df.assign(
                    clean_batch=non_empty_batch_df["preferred_batch"].map(_clean_batch),
                    amount_inr_num=pd.to_numeric(
                        non_empty_batch_df["amount_inr"], errors="coerce"
                    ).fillna(0.0)
                )
                .groupby("clean_batch", dropna=False)["amount_inr_num"]
                .sum()
                .loc[lambda s: s.index.astype(str).str.strip() != ""]
                .sort_values(ascending=False)
            )
            top_batch_name = str(batch_revenue.index[0])
            top_batch_revenue = float(batch_revenue.iloc[0])

        mode_counts_for_insights = (
            filtered_df["mode"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .value_counts()
        )
        most_common_mode = (
            str(mode_counts_for_insights.index[0]) if not mode_counts_for_insights.empty else "-"
        )

        average_payment = float(amount_numeric.mean()) if not amount_numeric.empty else 0.0

        st.subheader("Insights")
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        insight_col1.metric("Top Batch by Revenue", top_batch_name)
        insight_col1.caption(f"Revenue: {_format_inr(top_batch_revenue)}")
        insight_col2.metric("Most Common Mode", most_common_mode)
        insight_col3.metric("Average Payment Amount", _format_inr(average_payment))

        st.caption(f"Rows: {len(filtered_df):,}")
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download filtered data (CSV)",
            data=csv_data,
            file_name="payments_export.csv",
            mime="text/csv",
        )
        st.dataframe(
            _style_payments_table(filtered_df),
            use_container_width=True,
            hide_index=True,
        )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Revenue by Batch")
            revenue_by_batch_df = (
                filtered_df.assign(
                    clean_batch=filtered_df["preferred_batch"].map(_clean_batch),
                    amount_inr_num=pd.to_numeric(filtered_df["amount_inr"], errors="coerce").fillna(
                        0.0
                    ),
                )
                .groupby("clean_batch", dropna=False, as_index=False)["amount_inr_num"]
                .sum()
            )
            revenue_by_batch_df = revenue_by_batch_df[
                revenue_by_batch_df["clean_batch"].astype(str).str.strip() != ""
            ].sort_values("amount_inr_num", ascending=False)
            if revenue_by_batch_df.empty:
                st.info("No data available for revenue by batch.")
            else:
                revenue_by_batch_df["amount_inr_label"] = revenue_by_batch_df[
                    "amount_inr_num"
                ].map(_format_inr)
                bar_base = alt.Chart(revenue_by_batch_df).encode(
                    y=alt.Y(
                        "clean_batch:N",
                        sort="-x",
                        title="Batch",
                        axis=alt.Axis(labelColor="#E5E7EB", titleColor="#E5E7EB"),
                    ),
                    x=alt.X(
                        "amount_inr_num:Q",
                        title="Revenue (INR)",
                        axis=alt.Axis(labelColor="#E5E7EB", titleColor="#E5E7EB"),
                    ),
                    tooltip=[
                        alt.Tooltip("clean_batch:N", title="Batch"),
                        alt.Tooltip("amount_inr_label:N", title="Revenue"),
                    ],
                )
                bars = bar_base.mark_bar(color="#4C78A8", cornerRadiusEnd=4)
                labels = bar_base.mark_text(
                    align="left", baseline="middle", dx=6, color="#E5E7EB", fontSize=12
                ).encode(text="amount_inr_label:N")
                st.altair_chart(
                    (bars + labels)
                    .properties(height=360)
                    .configure(background="#0E1117")
                    .configure_view(strokeWidth=0)
                    .configure_axis(gridColor="#2D3748", domainColor="#2D3748"),
                    use_container_width=True,
                )

        with chart_col2:
            st.subheader("Mode Distribution")
            mode_counts = filtered_df["mode"].astype(str).str.strip()
            mode_counts = mode_counts[mode_counts != ""].value_counts()
            if mode_counts.empty:
                st.info("No data available for mode distribution.")
            else:
                mode_df = (
                    mode_counts.rename_axis("mode")
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
                )
                total_count = int(mode_df["count"].sum())
                mode_df["percent"] = mode_df["count"] / total_count
                mode_df["percent_label"] = (mode_df["percent"] * 100).map(
                    lambda v: f"{v:.1f}%"
                )
                mode_df["legend_label"] = mode_df.apply(
                    lambda row: f"{row['mode']} ({int(row['count'])}, {row['percent_label']})",
                    axis=1,
                )

                donut = (
                    alt.Chart(mode_df)
                    .mark_arc(innerRadius=70, outerRadius=130)
                    .encode(
                        theta=alt.Theta("count:Q"),
                        color=alt.Color(
                            "legend_label:N",
                            title=None,
                            legend=alt.Legend(
                                orient="bottom", labelColor="#E5E7EB", symbolType="circle"
                            ),
                            scale=alt.Scale(
                                range=[
                                    "#4C78A8",
                                    "#F58518",
                                    "#54A24B",
                                    "#E45756",
                                    "#B279A2",
                                    "#72B7B2",
                                ]
                            ),
                        ),
                        tooltip=[
                            alt.Tooltip("mode:N", title="Mode"),
                            alt.Tooltip("count:Q", title="Count", format=",d"),
                            alt.Tooltip("percent:Q", title="Percentage", format=".1%"),
                        ],
                    )
                )
                labels = (
                    alt.Chart(mode_df)
                    .mark_text(radius=155, color="#E5E7EB", fontSize=12)
                    .encode(
                        theta=alt.Theta("count:Q", stack=True),
                        text=alt.Text("percent:Q", format=".1%"),
                    )
                )
                st.altair_chart(
                    (donut + labels)
                    .properties(height=360)
                    .configure(background="#0E1117")
                    .configure_view(strokeWidth=0)
                    .configure_legend(labelFontSize=12),
                    use_container_width=True,
                )

    render_dashboard()


if __name__ == "__main__":
    main()

