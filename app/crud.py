from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ms_core import CRUD

from app.models import (
    BankTransferPayment,
    BankTransferStatus,
    OwnerSubscription,
    Payment,
    PaymentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.schemas import BankTransferResponse, PaymentResponse


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


class SubscriptionCRUD:
    """CRUD operations for subscription plans and owner subscriptions."""

    async def list_plans(self) -> list[SubscriptionPlan]:
        """Return all active subscription plans."""
        return await SubscriptionPlan.filter(is_active=True).all()

    async def get_plan_by_slug(self, slug: str) -> SubscriptionPlan | None:
        return await SubscriptionPlan.get_or_none(slug=slug)

    async def get_owner_subscription(self, owner_id: UUID) -> OwnerSubscription | None:
        return await OwnerSubscription.get_or_none(owner_id=owner_id).select_related("plan")

    async def get_by_stripe_subscription_id(self, stripe_sub_id: str) -> OwnerSubscription | None:
        return await OwnerSubscription.get_or_none(
            stripe_subscription_id=stripe_sub_id
        ).select_related("plan")

    async def upsert_subscription(
        self,
        owner_id: UUID,
        plan_id: UUID,
        status: SubscriptionStatus,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
    ) -> OwnerSubscription:
        sub, _ = await OwnerSubscription.get_or_create(owner_id=owner_id)
        sub.plan_id = plan_id
        sub.status = status
        if stripe_customer_id:
            sub.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id:
            sub.stripe_subscription_id = stripe_subscription_id
        if current_period_end:
            sub.current_period_end = current_period_end
        await sub.save()
        return await OwnerSubscription.get(id=sub.id).select_related("plan")

    async def cancel_subscription(self, owner_id: UUID) -> OwnerSubscription | None:
        sub = await self.get_owner_subscription(owner_id)
        if sub:
            sub.status = SubscriptionStatus.CANCELLED
            sub.cancelled_at = datetime.utcnow()
            await sub.save()
        return sub

    async def can_add_listing(self, owner_id: UUID) -> bool:
        """Return True if owner has an active subscription with quota remaining."""
        sub = await self.get_owner_subscription(owner_id)
        if sub is None or sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            return False
        if sub.plan.max_listings == -1:
            return True
        active_count = await _count_owner_listings(owner_id)
        return active_count < sub.plan.max_listings


async def _count_owner_listings(owner_id: UUID) -> int:
    """Cross-service stub — replaced by PaymentsClient call in properties-ms Task 4."""
    return 0


subscription_crud = SubscriptionCRUD()


class BankTransferCRUD:
    """CRUD operations for bank-transfer payment intents."""

    async def create_intent(
        self,
        booking_id: UUID,
        user_id: UUID,
        property_owner_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> BankTransferPayment:
        from app import settings

        reference = f"BK-{str(booking_id)[:8].upper()}"
        return await BankTransferPayment.create(
            booking_id=booking_id,
            user_id=user_id,
            property_owner_id=property_owner_id,
            amount=amount,
            currency=currency,
            bank_iban=settings.bank_iban,
            bank_bic=settings.bank_bic,
            bank_name=settings.bank_name,
            account_holder=settings.bank_account_holder,
            reference=reference,
        )

    async def get_by_id(self, intent_id: UUID) -> BankTransferPayment | None:
        """Return a bank transfer intent by primary key."""
        return await BankTransferPayment.get_or_none(id=intent_id)

    async def confirm_intent(self, intent_id: UUID) -> BankTransferPayment | None:
        """Mark the intent as confirmed (owner received the transfer)."""
        intent = await self.get_by_id(intent_id)
        if intent:
            intent.status = BankTransferStatus.CONFIRMED
            await intent.save()
        return intent

    async def cancel_intent(self, intent_id: UUID) -> BankTransferPayment | None:
        """Mark the intent as cancelled."""
        intent = await self.get_by_id(intent_id)
        if intent:
            intent.status = BankTransferStatus.CANCELLED
            await intent.save()
        return intent


bank_transfer_crud = BankTransferCRUD()
