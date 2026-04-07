# Payment Capture Automation

Flask webhook that receives Razorpay `payment.captured` events, verifies the signature, and appends a row to Google Sheets.
It also protects against duplicate inserts by normalizing `payment_id` (`strip` + `lower`) and skipping rows that already exist in the sheet.

## Prerequisites

- Python 3.10+
- Razorpay account with a webhook URL pointing to `POST /webhooks/razorpay`
- Google Cloud project with **Google Sheets API** enabled and a **service account** JSON key
- A spreadsheet whose first row matches this **exact** column order:

`payment_id` | `name` | `email` | `contact` | `amount_inr` | `status` | `preferred_batch` | `mode` | `captured_at_ist`

Share the spreadsheet with the service account email (Editor).

## Setup

1. `python -m venv .venv` then activate it.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` (or create `.env`) and set the variables below.
4. Set `GOOGLE_SERVICE_ACCOUNT_JSON` with the full service account JSON payload.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signing secret from the Razorpay Dashboard |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full Google service account JSON payload (single-line JSON string) |
| `GOOGLE_SHEET_ID` | Spreadsheet ID from the Google Sheets URL |
| `GOOGLE_WORKSHEET_NAME` | Tab name (default in config: `Payments`) |
| `SKIP_WEBHOOK_VERIFY` | Set to `true` / `1` **only for local testing** to skip HMAC checks. Use **false** (or unset) in production. |

`tzdata` is included in `requirements.txt` so IST conversion works on Windows as well as Linux/macOS.

## Run (development)

```bash
flask --app wsgi run
```

With auto-reload:

```bash
flask --app wsgi run --debug
```

Default URL: `http://127.0.0.1:5000` — `GET /health`, `POST /webhooks/razorpay`.

## Dashboard (Streamlit)

Run the payments dashboard:

```bash
streamlit run dashboard.py
```

Dashboard highlights:

- Data is fetched from Google Sheets via `@st.cache_data(ttl=30)`.
- Auto-refresh updates data every 30 seconds without full browser reload (filters remain intact).
- Filters include batch, mode, and case-insensitive search on name/email/phone.
- Table shows newest payments first (`captured_at_ist` parsed safely with invalid dates handled).
- Status highlighting: `captured` in green, `failed` in red.
- CSV export downloads the currently filtered rows as `payments_export.csv`.
- Insights include top batch by revenue, most common mode, and average payment amount.

## Run (production, Linux)

```bash
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

Use HTTPS in front of the app and set env vars on the host (do not rely on `SKIP_WEBHOOK_VERIFY`).

## Test

```bash
pytest
```

## Duplicate handling

- Existing `payment_id`s are read from the sheet before insert.
- Incoming and existing IDs are normalized (`strip`, `lower`) before comparison.
- If a duplicate is found, insertion is skipped and a retry-safe info log is emitted.

## Exposing local dev to Razorpay

Razorpay needs a public HTTPS URL. Use **ngrok** (or similar) to tunnel to your machine, then point the webhook at `https://<your-tunnel>/webhooks/razorpay`.
