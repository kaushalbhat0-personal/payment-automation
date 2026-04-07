from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedPaymentRow:
    payment_id: str
    email: str
    contact: str
    amount_inr: float
    status: str
    name: str
    preferred_batch: str
    mode: str
    captured_at_ist: str

    def as_sheet_row(self) -> list[Any]:
        return [
            self.payment_id,
            self.name,
            self.email,
            self.contact,
            self.amount_inr,
            self.status,
            self.preferred_batch,
            self.mode,
            self.captured_at_ist,
        ]
