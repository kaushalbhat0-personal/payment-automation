import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    razorpay_webhook_secret: str
    google_service_account_file: str
    google_sheet_id: str
    google_worksheet_name: str
    skip_webhook_verify: bool = False

    @staticmethod
    def from_env() -> "Config":
        skip = os.getenv("SKIP_WEBHOOK_VERIFY", "false").lower() == "true"
        return Config(
            razorpay_webhook_secret=os.environ.get("RAZORPAY_WEBHOOK_SECRET", ""),
            google_service_account_file=os.environ.get(
                "GOOGLE_SERVICE_ACCOUNT_FILE", ""
            ),
            google_sheet_id=os.environ.get("GOOGLE_SHEET_ID", ""),
            google_worksheet_name=os.environ.get("GOOGLE_WORKSHEET_NAME", "Payments"),
            skip_webhook_verify=skip,
        )
