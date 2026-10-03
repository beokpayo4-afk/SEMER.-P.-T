import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.enums import PaymentStatus

ALLOWED_METHODS = frozenset({"cod", "upi", "card", "netbanking"})
SENSITIVE_FIELDS = frozenset(
    {
        "card",
        "card_number",
        "cardnumber",
        "cvv",
        "cvc",
        "pan",
        "pin",
        "upi_pin",
        "upipin",
        "account_number",
        "expiry",
        "exp_month",
        "exp_year",
    }
)
PUBLIC_STATUS = {
    "PENDING": PaymentStatus.pending,
    "PAID": PaymentStatus.paid,
    "FAILED": PaymentStatus.failed,
    "REFUNDED": PaymentStatus.refunded,
}


@dataclass(frozen=True)
class ProviderEvent:
    transaction_id: str
    status: PaymentStatus


class PaymentProvider:
    name = "manual"

    def start(self, *, amount_paise: int, currency: str, payment_method: str) -> tuple[str, PaymentStatus]:
        del amount_paise, currency, payment_method
        return f"manual-{uuid.uuid4().hex}", PaymentStatus.pending

    def verify(
        self,
        *,
        transaction_id: str | None,
        amount_paise: int,
        currency: str,
        current_status: PaymentStatus,
    ) -> PaymentStatus:
        del amount_paise, currency
        if not transaction_id:
            raise APIError(status_code=409, detail="Payment could not be verified")
        return current_status

    def parse_webhook(self, body: bytes, signature: str | None) -> ProviderEvent:
        _require_signature(body, signature)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise APIError(status_code=422, detail="Payment webhook is invalid") from exc
        reject_sensitive(payload)
        if not isinstance(payload, dict):
            raise APIError(status_code=422, detail="Payment webhook is invalid")
        transaction_id = payload.get("transaction_id")
        status_name = payload.get("status")
        allowed = {"transaction_id", "status"}
        if set(payload) - allowed or not isinstance(transaction_id, str) or not transaction_id.strip():
            raise APIError(status_code=422, detail="Payment webhook is invalid")
        status = PUBLIC_STATUS.get(str(status_name))
        if status is None:
            raise APIError(status_code=422, detail="Payment webhook is invalid")
        return ProviderEvent(transaction_id=transaction_id.strip(), status=status)


def get_payment_provider() -> PaymentProvider:
    name = settings.payment_provider
    if name == PaymentProvider.name:
        return PaymentProvider()
    raise APIError(status_code=503, detail="Payment provider is not available")


def reject_sensitive(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in SENSITIVE_FIELDS:
                raise APIError(status_code=422, detail="Payment credentials are not accepted")
            reject_sensitive(value)
    elif isinstance(payload, list):
        for item in payload:
            reject_sensitive(item)


def _require_signature(body: bytes, signature: str | None) -> None:
    secret = settings.payment_webhook_secret
    if not secret or not signature:
        raise APIError(status_code=401, detail="Payment webhook could not be verified")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        valid = hmac.compare_digest(expected, signature.strip())
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise APIError(status_code=401, detail="Payment webhook could not be verified")
