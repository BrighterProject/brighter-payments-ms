from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ms_core import CRUD

from app.models import (
    BankTransferPayment,
    BankTransferStatus,
    OwnerBankAccount,
    OwnerSubscription,
    Payment,
    PaymentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.schemas import OwnerBankAccountResponse, PaymentResponse


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
        locale: str = "en",
    ) -> PaymentResponse:
        inst = await Payment.create(
            booking_id=booking_id,
            user_id=user_id,
            property_owner_id=property_owner_id,
            stripe_session_id=stripe_session_id,
            amount=amount,
            currency=currency,
            locale=locale,
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

    async def mark_paid(self, session_id: str, payment_intent_id: str) -> Payment | None:
        inst = await Payment.get_or_none(stripe_session_id=session_id)
        if inst is None:
            return None
        inst.status = PaymentStatus.PAID
        inst.stripe_payment_intent_id = payment_intent_id
        await inst.save(update_fields=["status", "stripe_payment_intent_id", "updated_at"])
        return inst

    async def mark_failed(self, session_id: str) -> Payment | None:
        inst = await Payment.get_or_none(stripe_session_id=session_id)
        if inst is None:
            return None
        inst.status = PaymentStatus.FAILED
        await inst.save(update_fields=["status", "updated_at"])
        return inst

    async def mark_refunded(
        self,
        payment_intent_id: str,
        refunded_amount: Decimal | None = None,
        is_full: bool = True,
    ) -> Payment | None:
        """Record a refund against a paid payment.

        Idempotent across the endpoint and the ``charge.refunded`` webhook: a
        payment already in ``PARTIALLY_REFUNDED`` can still be escalated to a
        larger or full refund.
        """
        inst = await Payment.get_or_none(
            stripe_payment_intent_id=payment_intent_id,
            status__in=[PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED],
        )
        if inst is None:
            return None
        inst.status = PaymentStatus.REFUNDED if is_full else PaymentStatus.PARTIALLY_REFUNDED
        inst.refunded_amount = refunded_amount if refunded_amount is not None else inst.amount
        await inst.save(update_fields=["status", "refunded_amount", "updated_at"])
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
        cancel_at_period_end: bool = False,
    ) -> OwnerSubscription:
        defaults: dict = {
            "plan_id": plan_id,
            "status": status,
            "cancel_at_period_end": cancel_at_period_end,
        }
        if stripe_customer_id is not None:
            defaults["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id is not None:
            defaults["stripe_subscription_id"] = stripe_subscription_id
        if current_period_end is not None:
            defaults["current_period_end"] = current_period_end
        if status == SubscriptionStatus.CANCELED:
            defaults["cancelled_at"] = datetime.utcnow()
        sub, _ = await OwnerSubscription.update_or_create(defaults, owner_id=owner_id)
        await sub.fetch_related("plan")
        return sub

    async def cancel_subscription(self, owner_id: UUID) -> OwnerSubscription | None:
        sub = await self.get_owner_subscription(owner_id)
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.cancelled_at = datetime.utcnow()
            await sub.save()
        return sub

    async def list_all(self) -> list[OwnerSubscription]:
        """Return all owner subscriptions with plan data (admin use)."""
        return await OwnerSubscription.all().select_related("plan").order_by("-created_at")

    async def can_add_listing(self, owner_id: UUID, current_count: int) -> bool:
        """Return True if owner has an active subscription with quota remaining."""
        sub = await self.get_owner_subscription(owner_id)
        if sub is None or sub.status not in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
        ):
            return False
        if sub.plan.max_listings == -1:
            return True
        return current_count < sub.plan.max_listings


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
        bank_iban: str,
        bank_bic: str,
        bank_name: str,
        account_holder: str,
    ) -> BankTransferPayment:
        reference = f"BK-{str(booking_id)[:8].upper()}"
        return await BankTransferPayment.create(
            booking_id=booking_id,
            user_id=user_id,
            property_owner_id=property_owner_id,
            amount=amount,
            currency=currency,
            bank_iban=bank_iban,
            bank_bic=bank_bic,
            bank_name=bank_name,
            account_holder=account_holder,
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

    async def list_by_status(
        self,
        status: BankTransferStatus | None = None,
        owner_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[BankTransferPayment]:
        """List bank transfer intents, optionally filtered by status and/or owner."""
        qs = BankTransferPayment.all()
        if status is not None:
            qs = qs.filter(status=status)
        if owner_id is not None:
            qs = qs.filter(property_owner_id=owner_id)
        offset = (page - 1) * page_size
        return await qs.order_by("-created_at").offset(offset).limit(page_size)


bank_transfer_crud = BankTransferCRUD()


class OwnerBankAccountCRUD:
    """CRUD operations for owner bank accounts used in bank-transfer payments."""

    async def upsert(
        self,
        owner_id: UUID,
        iban: str,
        account_holder: str,
        bic: str | None = None,
        bank_name: str | None = None,
    ) -> OwnerBankAccountResponse:
        account, _ = await OwnerBankAccount.get_or_create(dict(iban=iban), owner_id=owner_id)
        account.account_holder = account_holder
        account.bic = bic
        account.bank_name = bank_name
        await account.save()
        return OwnerBankAccountResponse.model_validate(account)

    async def get_by_owner(self, owner_id: UUID) -> OwnerBankAccountResponse | None:
        account = await OwnerBankAccount.get_or_none(owner_id=owner_id)
        return OwnerBankAccountResponse.model_validate(account) if account else None


owner_bank_account_crud = OwnerBankAccountCRUD()
