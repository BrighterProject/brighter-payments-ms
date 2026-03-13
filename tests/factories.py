"""
All test-data builders in one place.
Import from here in every test file — never define dummy data inline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.deps import CurrentUser
from app.scopes import PaymentScope

# ---------------------------------------------------------------------------
# Stable IDs — use these when a specific, repeatable UUID is needed.
# ---------------------------------------------------------------------------

CUSTOMER_ID: UUID = uuid4()
PROPERTY_OWNER_ID: UUID = uuid4()
ADMIN_ID: UUID = uuid4()
OTHER_USER_ID: UUID = uuid4()

PAYMENT_ID: UUID = uuid4()
BOOKING_ID: UUID = uuid4()

STRIPE_SESSION_ID = "cs_test_abc123"
STRIPE_PAYMENT_INTENT_ID = "pi_test_xyz789"

NOW = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------


def make_customer(
    user_id: UUID = CUSTOMER_ID,
    scopes: list[str] | None = None,
) -> CurrentUser:
    if scopes is None:
        scopes = [PaymentScope.READ]
    return CurrentUser(id=user_id, username=f"customer_{user_id}", scopes=scopes)


def make_property_owner(
    user_id: UUID = PROPERTY_OWNER_ID,
    scopes: list[str] | None = None,
) -> CurrentUser:
    if scopes is None:
        scopes = ["bookings:manage"]
    return CurrentUser(id=user_id, username=f"owner_{user_id}", scopes=scopes)


def make_admin() -> CurrentUser:
    return CurrentUser(
        id=ADMIN_ID,
        username="admin",
        scopes=[
            "admin:scopes",
            PaymentScope.READ,
            PaymentScope.ADMIN,
            PaymentScope.ADMIN_READ,
            PaymentScope.ADMIN_WRITE,
            PaymentScope.ADMIN_DELETE,
        ],
    )


# ---------------------------------------------------------------------------
# Response dict factories
# ---------------------------------------------------------------------------


def payment_response(**overrides) -> dict:
    base = dict(
        id=str(PAYMENT_ID),
        booking_id=str(BOOKING_ID),
        user_id=str(CUSTOMER_ID),
        property_owner_id=str(PROPERTY_OWNER_ID),
        stripe_session_id=STRIPE_SESSION_ID,
        stripe_payment_intent_id=STRIPE_PAYMENT_INTENT_ID,
        amount="40.00",
        currency="EUR",
        status="paid",
        updated_at=NOW.isoformat(),
    )
    return {**base, **overrides}


def booking_dict(**overrides) -> dict:
    """Minimal bookings-ms booking representation used by BookingsClient mocks."""
    base = dict(
        id=str(BOOKING_ID),
        property_id=str(uuid4()),
        property_owner_id=str(PROPERTY_OWNER_ID),
        user_id=str(CUSTOMER_ID),
        start_datetime=NOW.isoformat(),
        end_datetime=LATER.isoformat(),
        status="pending",
        total_price="40.00",
        currency="EUR",
    )
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# Request payload factories
# ---------------------------------------------------------------------------


def checkout_payload(**overrides) -> dict:
    base = dict(booking_id=str(BOOKING_ID))
    return {**base, **overrides}
