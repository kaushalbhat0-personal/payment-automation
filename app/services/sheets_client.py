import json
import os

import gspread
from google.oauth2.service_account import Credentials

from app.config import Config

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


def _normalize_payment_id(payment_id: str | None) -> str:
    if payment_id is None:
        return ""
    return str(payment_id).strip().lower()


def _get_worksheet(config: Config):
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set")

    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=_SCOPES,
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(config.google_sheet_id)
    return sh.worksheet(config.google_worksheet_name)


def _existing_payment_ids(ws) -> set[str]:
    # Column A stores payment IDs as the first field in each row.
    payment_ids = ws.col_values(1)
    return {
        normalized
        for pid in payment_ids
        for normalized in [_normalize_payment_id(pid)]
        if normalized and normalized != "payment_id"
    }


def append_row_if_payment_new(
    config: Config, payment_id: str | None, values: list
) -> bool:
    ws = _get_worksheet(config)
    normalized_payment_id = _normalize_payment_id(payment_id)
    if normalized_payment_id in _existing_payment_ids(ws):
        return False
    # Keep header in row 1 and always place newest payment at top.
    ws.insert_row(values, index=2, value_input_option="USER_ENTERED")
    return True
