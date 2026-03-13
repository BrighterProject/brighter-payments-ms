from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentResponse(BaseModel):
    id: UUID
    booking_id: UUID
    user_id: UUID
    property_owner_id: UUID
    stripe_session_id: str
    stripe_payment_intent_id: str | None
    amount: Decimal
    currency: str
    status: PaymentStatus
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckoutRequest(BaseModel):
    booking_id: UUID
    locale: str | None = None


class CheckoutResponse(BaseModel):
    """Returned to the frontend after creating a Checkout Session."""

    checkout_url: str
    session_id: str
    payment_id: UUID
