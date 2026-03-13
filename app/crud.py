from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ms_core import CRUD

from app.models import Payment, PaymentStatus
from app.schemas import PaymentResponse


class PaymentCRUD(CRUD[Payment, PaymentResponse]):  # type: ignore
    async def create(
        self,
        *,
        booking_id: UUID,
        user_id: UUID,
        property_owner_id: UUID,
        stripe_session_id: str,
        amount: Decimal,
        currency: str,
    ) -> PaymentResponse:
        inst = await Payment.create(
            booking_id=booking_id,
            user_id=user_id,
            property_owner_id=property_owner_id,
            stripe_session_id=stripe_session_id,
            amount=amount,
            currency=currency,
        )
        return PaymentResponse.model_validate(inst)

    async def get_by_booking_paid(self, booking_id: UUID) -> PaymentResponse | None:
        """Return the most recent PAID payment for a booking, or None."""
        inst = (
            await Payment.filter(booking_id=booking_id, status=PaymentStatus.PAID)
            .order_by("-created_at")
            .first()
        )
        return PaymentResponse.model_validate(inst) if inst else None

    async def get_pending_by_id(self, payment_id: UUID) -> Payment | None:
        """Return a PENDING payment by primary key, or None."""
        return await Payment.get_or_none(id=payment_id, status=PaymentStatus.PENDING)

    async def get_by_session(self, session_id: str) -> Payment | None:
        """Return the raw model instance for internal webhook processing."""
        return await Payment.get_or_none(stripe_session_id=session_id)

    async def mark_paid(
        self, session_id: str, payment_intent_id: str
    ) -> Payment | None:
        inst = await Payment.get_or_none(stripe_session_id=session_id)
        if inst is None:
            return None
        inst.status = PaymentStatus.PAID
        inst.stripe_payment_intent_id = payment_intent_id
        await inst.save(
            update_fields=["status", "stripe_payment_intent_id", "updated_at"]
        )
        return inst

    async def mark_failed(self, session_id: str) -> Payment | None:
        inst = await Payment.get_or_none(stripe_session_id=session_id)
        if inst is None:
            return None
        inst.status = PaymentStatus.FAILED
        await inst.save(update_fields=["status", "updated_at"])
        return inst

    async def mark_refunded(self, payment_intent_id: str) -> Payment | None:
        inst = await Payment.get_or_none(
            stripe_payment_intent_id=payment_intent_id,
            status=PaymentStatus.PAID,
        )
        if inst is None:
            return None
        inst.status = PaymentStatus.REFUNDED
        await inst.save(update_fields=["status", "updated_at"])
        return inst

    async def list_payments(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        user_id: UUID | None = None,
    ) -> list[PaymentResponse]:
        qs = Payment.all()
        if user_id is not None:
            qs = qs.filter(user_id=user_id)
        offset = (page - 1) * page_size
        items = await qs.offset(offset).limit(page_size)
        return [PaymentResponse.model_validate(p) for p in items]

    async def delete_payment(self, payment_id: UUID) -> bool:
        deleted = await Payment.filter(id=payment_id).delete()
        return deleted > 0


payment_crud = PaymentCRUD(Payment, PaymentResponse)
