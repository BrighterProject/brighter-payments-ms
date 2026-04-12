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
    verified = fields.BooleanField(default=False)

    class Meta:  # type: ignore
        table = "owner_stripe_accounts"
