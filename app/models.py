from enum import StrEnum

from ms_core import AbstractModel as Model
from tortoise import fields


class PaymentStatus(StrEnum):
    PENDING = "pending"  # Checkout Session created, awaiting customer payment
    PAID = "paid"  # checkout.session.completed received
    REFUNDED = "refunded"  # Full refund issued to customer
    FAILED = "failed"  # Checkout Session expired without payment


class Payment(Model):
    id = fields.UUIDField(primary_key=True)

    # Denormalized references to bookings-ms
    booking_id = fields.UUIDField()  # allows multiple attempts per booking
    user_id = fields.UUIDField()  # the customer who made the booking
    property_owner_id = fields.UUIDField()  # snapshot from booking at creation time

    # Stripe identifiers
    stripe_session_id = fields.CharField(max_length=255, unique=True)
    stripe_payment_intent_id = fields.CharField(max_length=255, null=True)

    # Monetary snapshot — always fetched from bookings-ms, never from the client
    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    currency = fields.CharField(max_length=3, default="EUR")

    status = fields.CharEnumField(PaymentStatus, default=PaymentStatus.PENDING)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # type: ignore
        table = "payments"
        ordering = ["-created_at"]


class OwnerStripeAccount(Model):
    id = fields.UUIDField(primary_key=True)
    owner_id = fields.UUIDField(unique=True)
    stripe_account_id = fields.CharField(max_length=255, unique=True)
    transfers_active = fields.BooleanField(default=False)
    verified = fields.BooleanField(default=False)
    # Set to True when Stripe reports unresolved requirements (e.g. expired ID,
    # missing tax info).  Cleared automatically once the owner resolves them.
    requirements_outstanding = fields.BooleanField(default=False)
    requirements_eventually_due = fields.BooleanField(default=False)

    class Meta:  # type: ignore
        table = "owner_stripe_accounts"


class SubscriptionPlanSlug(StrEnum):
    STARTER = "starter"
    BASIC = "basic"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"


class SubscriptionPlan(Model):
    id = fields.UUIDField(primary_key=True)
    slug = fields.CharEnumField(SubscriptionPlanSlug, unique=True)
    name = fields.CharField(max_length=100)
    max_listings = fields.IntField()
    price_eur_cents = fields.IntField()
    stripe_price_id = fields.CharField(max_length=255, null=True)
    is_active = fields.BooleanField(default=True)

    class Meta:  # type: ignore
        table = "subscription_plans"


class OwnerSubscription(Model):
    id = fields.UUIDField(primary_key=True)
    owner_id = fields.UUIDField(unique=True)
    plan = fields.ForeignKeyField(
        "models.SubscriptionPlan", related_name="subscriptions", on_delete=fields.RESTRICT
    )
    status = fields.CharEnumField(SubscriptionStatus, default=SubscriptionStatus.INCOMPLETE)
    stripe_customer_id = fields.CharField(max_length=255, null=True)
    stripe_subscription_id = fields.CharField(max_length=255, null=True, unique=True)
    current_period_end = fields.DatetimeField(null=True)
    cancelled_at = fields.DatetimeField(null=True)

    class Meta:  # type: ignore
        table = "owner_subscriptions"


class OwnerBankAccount(Model):
    """Owner's personal bank account used for bank-transfer bookings."""

    id = fields.UUIDField(primary_key=True)
    owner_id = fields.UUIDField(unique=True)
    iban = fields.CharField(max_length=34)
    bic = fields.CharField(max_length=11, null=True)
    bank_name = fields.CharField(max_length=100, null=True)
    account_holder = fields.CharField(max_length=200)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # type: ignore
        table = "owner_bank_accounts"


class BankTransferStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BankTransferPayment(Model):
    id = fields.UUIDField(primary_key=True)
    booking_id = fields.UUIDField()
    user_id = fields.UUIDField()
    property_owner_id = fields.UUIDField()
    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    currency = fields.CharField(max_length=3, default="EUR")
    status = fields.CharEnumField(BankTransferStatus, default=BankTransferStatus.PENDING)
    bank_iban = fields.CharField(max_length=34)
    bank_bic = fields.CharField(max_length=11)
    bank_name = fields.CharField(max_length=100)
    account_holder = fields.CharField(max_length=200)
    reference = fields.CharField(max_length=50)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # type: ignore
        table = "bank_transfer_payments"
