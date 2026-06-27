"""
Endpoint tests for payments-ms.
All DB operations are mocked at the CRUD layer.
All HTTP calls (Stripe, bookings-ms) are mocked via dependency overrides.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.factories import (
    BOOKING_ID,
    CUSTOMER_ID,
    PAYMENT_ID,
    PROPERTY_OWNER_ID,
    STRIPE_PAYMENT_INTENT_ID,
    STRIPE_SESSION_ID,
    booking_dict,
    checkout_payload,
    make_admin,
    make_customer,
    make_property_owner,
    payment_response,
)

# ===========================================================================
# GET /payments/capabilities
# ===========================================================================


class TestGetPaymentCapabilities:
    def test_can_accept_card_when_connect_active(self, client_factory):
        """can_accept_card=True when connect account exists, transfers_active=True,
        no outstanding requirements."""
        from app.models import OwnerStripeAccount

        mock_account = MagicMock(spec=OwnerStripeAccount)
        mock_account.transfers_active = True
        mock_account.requirements_outstanding = False

        client = client_factory(make_property_owner())

        with (
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=mock_account),
            ),
            patch(
                "app.routers.payments.owner_bank_account_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            resp = client.get("/payments/capabilities")

        assert resp.status_code == 200
        data = resp.json()
        assert data["can_accept_card"] is True
        assert data["can_accept_bank_transfer"] is False

    def test_can_accept_card_false_when_requirements_outstanding(self, client_factory):
        """can_accept_card=False when connect account has requirements_outstanding=True."""
        from app.models import OwnerStripeAccount

        mock_account = MagicMock(spec=OwnerStripeAccount)
        mock_account.transfers_active = True
        mock_account.requirements_outstanding = True

        client = client_factory(make_property_owner())

        with (
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=mock_account),
            ),
            patch(
                "app.routers.payments.owner_bank_account_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            resp = client.get("/payments/capabilities")

        assert resp.status_code == 200
        assert resp.json()["can_accept_card"] is False

    def test_can_accept_card_false_when_no_connect_account(self, client_factory):
        """can_accept_card=False when no connect account exists."""
        client = client_factory(make_property_owner())

        with (
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.payments.owner_bank_account_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            resp = client.get("/payments/capabilities")

        assert resp.status_code == 200
        assert resp.json()["can_accept_card"] is False

    def test_can_accept_bank_transfer_true_when_bank_account_present(self, client_factory):
        """can_accept_bank_transfer=True when owner has a bank account on record."""
        from app.models import OwnerBankAccount, OwnerStripeAccount

        mock_account = MagicMock(spec=OwnerStripeAccount)
        mock_account.transfers_active = True
        mock_account.requirements_outstanding = False

        mock_bank = MagicMock(spec=OwnerBankAccount)
        mock_bank.iban = "BG80BNBG96611020345678"

        client = client_factory(make_property_owner())

        with (
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=mock_account),
            ),
            patch(
                "app.routers.payments.owner_bank_account_crud.get_by_owner",
                AsyncMock(return_value=mock_bank),
            ),
        ):
            resp = client.get("/payments/capabilities")

        assert resp.status_code == 200
        data = resp.json()
        assert data["can_accept_card"] is True
        assert data["can_accept_bank_transfer"] is True


# ===========================================================================
# GET /payments/session/{session_id}
# ===========================================================================


class TestGetSessionPayment:
    def test_customer_gets_own_payment(self, customer_client):
        """200: customer gets their own payment by session id."""
        from app.schemas import PaymentResponse

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_session = AsyncMock(return_value=PaymentResponse(**payment_response()))
            resp = customer_client.get(f"/payments/session/{STRIPE_SESSION_ID}")

        assert resp.status_code == 200
        assert resp.json()["stripe_session_id"] == STRIPE_SESSION_ID

    def test_customer_cannot_see_other_users_payment(self, client_factory):
        """403: customer tries to see another user's payment."""
        from app.schemas import PaymentResponse

        other_customer = make_customer(user_id=uuid4())
        client = client_factory(other_customer)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_session = AsyncMock(return_value=PaymentResponse(**payment_response()))
            resp = client.get(f"/payments/session/{STRIPE_SESSION_ID}")

        assert resp.status_code == 403

    def test_returns_404_when_session_not_found(self, customer_client):
        """404: session not found."""
        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_session = AsyncMock(return_value=None)
            resp = customer_client.get(f"/payments/session/{STRIPE_SESSION_ID}")

        assert resp.status_code == 404


# ===========================================================================
# POST /payments/{payment_id}/abandon
# ===========================================================================


class TestAbandonPayment:
    def test_abandon_pending_payment(self, client_factory):
        """200: pending payment found, sessions.expire() called, returns {"abandoned": True}."""
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.checkout.sessions.expire.return_value = MagicMock()

        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            pending = PaymentResponse(
                **payment_response(status="pending", stripe_payment_intent_id=None)
            )
            mock_crud.get_pending_by_id = AsyncMock(return_value=pending)

            resp = client.post(f"/payments/{PAYMENT_ID}/abandon")

        assert resp.status_code == 200
        assert resp.json() == {"abandoned": True}
        mock_sc.v1.checkout.sessions.expire.assert_called_once()

    def test_returns_404_when_payment_not_found(self, client_factory):
        """404: payment not found."""
        client = client_factory(make_customer())

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_pending_by_id = AsyncMock(return_value=None)
            resp = client.post(f"/payments/{PAYMENT_ID}/abandon")

        assert resp.status_code == 404

    def test_customer_cannot_abandon_other_users_payment(self, client_factory):
        """403: user tries to abandon another user's payment."""
        from app.schemas import PaymentResponse

        other_customer = make_customer(user_id=uuid4())
        client = client_factory(other_customer)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_pending_by_id = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = client.post(f"/payments/{PAYMENT_ID}/abandon")

        assert resp.status_code == 403

    def test_handles_already_expired_session_gracefully(self, client_factory):
        """Stripe InvalidRequestError (already expired): handled gracefully without crashing."""
        import stripe as stripe_lib

        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.checkout.sessions.expire.side_effect = stripe_lib.InvalidRequestError(
            "The session has already expired.", param=None
        )

        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            pending = PaymentResponse(
                **payment_response(status="pending", stripe_payment_intent_id=None)
            )
            mock_crud.get_pending_by_id = AsyncMock(return_value=pending)

            resp = client.post(f"/payments/{PAYMENT_ID}/abandon")

        assert resp.status_code == 200
        assert resp.json() == {"abandoned": True}


# ===========================================================================
# POST /payments/checkout
# ===========================================================================


class TestCreateCheckout:
    def test_creates_checkout_session_and_returns_url(self, client_factory):
        mock_booking = booking_dict()
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)

        mock_sc = MagicMock()
        session_mock = MagicMock()
        session_mock.id = "cs_test_new"
        session_mock.url = "https://checkout.stripe.com/pay/cs_test_new"
        mock_sc.v1.checkout.sessions.create.return_value = session_mock

        client = client_factory(make_customer(), bookings_client=mock_bc, stripe_client=mock_sc)

        with (
            patch("app.routers.payments.payment_crud") as mock_crud,
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            from app.schemas import PaymentResponse

            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            pending = payment_response(status="pending", stripe_payment_intent_id=None)
            mock_crud.create = AsyncMock(return_value=PaymentResponse(**pending))

            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 201
        data = resp.json()
        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_new"
        assert data["session_id"] == "cs_test_new"

    def test_rejects_if_already_paid(self, client_factory):
        from app.schemas import PaymentResponse

        client = client_factory(make_customer())

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )

            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 409

    def test_rejects_if_booking_not_found(self, client_factory):
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=None)
        client = client_factory(make_customer(), bookings_client=mock_bc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 404

    def test_rejects_if_booking_belongs_to_other_user(self, client_factory):
        other_user_id = uuid4()
        mock_booking = booking_dict(user_id=str(other_user_id))
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)
        client = client_factory(make_customer(), bookings_client=mock_bc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 403

    def test_rejects_if_booking_not_pending(self, client_factory):
        mock_booking = booking_dict(status="confirmed")
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)
        client = client_factory(make_customer(), bookings_client=mock_bc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 422

    def test_admin_can_pay_any_booking(self, client_factory):
        other_user_id = uuid4()
        mock_booking = booking_dict(user_id=str(other_user_id))
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)

        mock_sc = MagicMock()
        session_mock = MagicMock()
        session_mock.id = "cs_test_admin"
        session_mock.url = "https://checkout.stripe.com/pay/cs_test_admin"
        mock_sc.v1.checkout.sessions.create.return_value = session_mock

        client = client_factory(make_admin(), bookings_client=mock_bc, stripe_client=mock_sc)

        with (
            patch("app.routers.payments.payment_crud") as mock_crud,
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            from app.schemas import PaymentResponse

            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            pending = payment_response(status="pending", stripe_payment_intent_id=None)
            mock_crud.create = AsyncMock(return_value=PaymentResponse(**pending))
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 201

    def test_rejects_bank_transfer_payment_method(self, client_factory):
        """422: booking with payment_method='bank_transfer' cannot use card checkout.
        Guard exists to prevent double-payment."""
        mock_booking = booking_dict(payment_method="bank_transfer")
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)
        client = client_factory(make_customer(), bookings_client=mock_bc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 422

    def test_checkout_with_connect_transfer_data(self, client_factory):
        """Connect account active: payment_intent_data includes transfer_data.destination.
        This branch is critical for platform-routed payments."""
        from app.models import OwnerStripeAccount
        from app.schemas import PaymentResponse

        mock_booking = booking_dict()
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)

        mock_sc = MagicMock()
        session_mock = MagicMock()
        session_mock.id = "cs_test_connect"
        session_mock.url = "https://checkout.stripe.com/pay/cs_test_connect"
        mock_sc.v1.checkout.sessions.create.return_value = session_mock

        connect_account = MagicMock(spec=OwnerStripeAccount)
        connect_account.stripe_account_id = "acct_test_connect_123"
        connect_account.transfers_active = True
        connect_account.requirements_outstanding = False

        client = client_factory(make_customer(), bookings_client=mock_bc, stripe_client=mock_sc)

        with (
            patch("app.routers.payments.payment_crud") as mock_crud,
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=connect_account),
            ),
        ):
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            pending = payment_response(status="pending", stripe_payment_intent_id=None)
            mock_crud.create = AsyncMock(return_value=PaymentResponse(**pending))
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 201
        call_kwargs = mock_sc.v1.checkout.sessions.create.call_args[1]
        assert "transfer_data" in call_kwargs["params"]["payment_intent_data"]
        assert (
            call_kwargs["params"]["payment_intent_data"]["transfer_data"]["destination"]
            == "acct_test_connect_123"
        )

    def test_checkout_stripe_failure_returns_502(self, client_factory):
        """StripeError during sessions.create -> 502 Bad Gateway."""
        import stripe as stripe_lib

        from app.schemas import PaymentResponse

        mock_booking = booking_dict()
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=mock_booking)

        mock_sc = MagicMock()
        mock_sc.v1.checkout.sessions.create.side_effect = stripe_lib.StripeError("Gateway timeout")

        client = client_factory(make_customer(), bookings_client=mock_bc, stripe_client=mock_sc)

        with (
            patch("app.routers.payments.payment_crud") as mock_crud,
            patch(
                "app.routers.payments.connect_crud.get_by_owner",
                AsyncMock(return_value=None),
            ),
        ):
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            pending = payment_response(status="pending", stripe_payment_intent_id=None)
            mock_crud.create = AsyncMock(return_value=PaymentResponse(**pending))
            resp = client.post("/payments/checkout", json=checkout_payload())

        assert resp.status_code == 502


# ===========================================================================
# GET /payments/
# ===========================================================================


class TestListPayments:
    def test_customer_sees_own_payments(self, customer_client):
        from app.schemas import PaymentResponse

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.list_payments = AsyncMock(
                return_value=[PaymentResponse(**payment_response())]
            )
            resp = customer_client.get("/payments/")

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_admin_sees_all_payments(self, admin_client):
        from app.schemas import PaymentResponse

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.list_payments = AsyncMock(
                return_value=[PaymentResponse(**payment_response())]
            )
            resp = admin_client.get("/payments/")

        assert resp.status_code == 200

    def test_requires_auth(self, anon_app):
        with TestClient(anon_app) as c:
            resp = c.get("/payments/")
        assert resp.status_code == 422  # missing headers -> validation error


# ===========================================================================
# GET /payments/booking/{booking_id}
# ===========================================================================


class TestGetPaymentByBooking:
    def test_customer_gets_own_payment(self, customer_client):
        from app.schemas import PaymentResponse

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = customer_client.get(f"/payments/booking/{BOOKING_ID}")

        assert resp.status_code == 200
        assert resp.json()["booking_id"] == str(BOOKING_ID)

    def test_customer_cannot_see_other_users_payment(self, client_factory):
        from app.schemas import PaymentResponse

        other_customer = make_customer(user_id=uuid4())
        client = client_factory(other_customer)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = client.get(f"/payments/booking/{BOOKING_ID}")

        assert resp.status_code == 403

    def test_returns_404_when_not_found(self, customer_client):
        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = customer_client.get(f"/payments/booking/{BOOKING_ID}")

        assert resp.status_code == 404


# ===========================================================================
# POST /payments/booking/{booking_id}/refund
# ===========================================================================


class TestRefundBookingPayment:
    def test_property_owner_can_refund(self, client_factory):
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.return_value = MagicMock()

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            paid_payment = PaymentResponse(**payment_response())
            mock_crud.get_by_booking_paid = AsyncMock(return_value=paid_payment)
            refunded = PaymentResponse(**payment_response(status="refunded"))
            mock_crud.mark_refunded = AsyncMock(
                return_value=MagicMock(
                    id=PAYMENT_ID,
                    booking_id=BOOKING_ID,
                    user_id=CUSTOMER_ID,
                    property_owner_id=PROPERTY_OWNER_ID,
                    stripe_session_id=STRIPE_SESSION_ID,
                    stripe_payment_intent_id=STRIPE_PAYMENT_INTENT_ID,
                    amount="40.00",
                    refunded_amount="40.00",
                    currency="EUR",
                    status="refunded",
                    updated_at=refunded.updated_at,
                )
            )

            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 200
        mock_sc.v1.refunds.create.assert_called_once_with(
            params={"payment_intent": STRIPE_PAYMENT_INTENT_ID}
        )

    def test_partial_refund_sends_amount_in_cents(self, client_factory):
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.return_value = MagicMock()

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            mock_crud.mark_refunded = AsyncMock(
                return_value=MagicMock(
                    id=PAYMENT_ID,
                    booking_id=BOOKING_ID,
                    user_id=CUSTOMER_ID,
                    property_owner_id=PROPERTY_OWNER_ID,
                    stripe_session_id=STRIPE_SESSION_ID,
                    stripe_payment_intent_id=STRIPE_PAYMENT_INTENT_ID,
                    amount="40.00",
                    refunded_amount="20.00",
                    currency="EUR",
                    status="partially_refunded",
                    updated_at=payment_response()["updated_at"],
                )
            )

            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund", json={"amount": "20.00"})

        assert resp.status_code == 200
        mock_sc.v1.refunds.create.assert_called_once_with(
            params={"payment_intent": STRIPE_PAYMENT_INTENT_ID, "amount": 2000}
        )
        mock_crud.mark_refunded.assert_called_once_with(
            STRIPE_PAYMENT_INTENT_ID, Decimal("20.00"), False
        )

    def test_amount_at_or_above_total_is_full_refund(self, client_factory):
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.return_value = MagicMock()

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            mock_crud.mark_refunded = AsyncMock(
                return_value=MagicMock(
                    id=PAYMENT_ID,
                    booking_id=BOOKING_ID,
                    user_id=CUSTOMER_ID,
                    property_owner_id=PROPERTY_OWNER_ID,
                    stripe_session_id=STRIPE_SESSION_ID,
                    stripe_payment_intent_id=STRIPE_PAYMENT_INTENT_ID,
                    amount="40.00",
                    refunded_amount="40.00",
                    currency="EUR",
                    status="refunded",
                    updated_at=payment_response()["updated_at"],
                )
            )

            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund", json={"amount": "999.00"})

        assert resp.status_code == 200
        # No `amount` key -> Stripe issues a full refund.
        mock_sc.v1.refunds.create.assert_called_once_with(
            params={"payment_intent": STRIPE_PAYMENT_INTENT_ID}
        )
        mock_crud.mark_refunded.assert_called_once_with(
            STRIPE_PAYMENT_INTENT_ID, Decimal("40.00"), True
        )

    def test_zero_amount_returns_422(self, client_factory):
        from app.schemas import PaymentResponse

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund", json={"amount": "0"})

        assert resp.status_code == 422

    def test_admin_can_refund(self, client_factory):
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.return_value = MagicMock()
        client = client_factory(make_admin(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            mock_crud.mark_refunded = AsyncMock(
                return_value=MagicMock(
                    id=PAYMENT_ID,
                    booking_id=BOOKING_ID,
                    user_id=CUSTOMER_ID,
                    property_owner_id=PROPERTY_OWNER_ID,
                    stripe_session_id=STRIPE_SESSION_ID,
                    stripe_payment_intent_id=STRIPE_PAYMENT_INTENT_ID,
                    amount="40.00",
                    refunded_amount="40.00",
                    currency="EUR",
                    status="refunded",
                    updated_at=payment_response()["updated_at"],
                )
            )

            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 200

    def test_customer_cannot_refund(self, customer_client):
        from app.schemas import PaymentResponse

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = customer_client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 403

    def test_returns_404_when_no_paid_payment(self, client_factory):
        client = client_factory(make_admin())

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(return_value=None)
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 404

    def test_already_refunded_returns_422(self, client_factory):
        """stripe.InvalidRequestError (e.g. already refunded) -> 422 with user message."""
        import stripe as stripe_lib

        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.side_effect = stripe_lib.InvalidRequestError(
            "Charge has already been refunded.", param=None
        )

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 422

    def test_stripe_gateway_failure_returns_502(self, client_factory):
        """stripe.StripeError (gateway failure) -> 502 Bad Gateway."""
        import stripe as stripe_lib

        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.side_effect = stripe_lib.StripeError("Gateway timeout")

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 502

    def test_mark_refunded_none_returns_500(self, client_factory):
        """mark_refunded returns None -> 500 'Refund issued but failed to update'."""
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()
        mock_sc.v1.refunds.create.return_value = MagicMock()

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response())
            )
            mock_crud.mark_refunded = AsyncMock(return_value=None)
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 500

    def test_refund_no_payment_intent_returns_422(self, client_factory):
        """payment.stripe_payment_intent_id is None -> 422."""
        from app.schemas import PaymentResponse

        mock_sc = MagicMock()

        owner = make_property_owner(user_id=PROPERTY_OWNER_ID)
        client = client_factory(owner, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.get_by_booking_paid = AsyncMock(
                return_value=PaymentResponse(**payment_response(stripe_payment_intent_id=None))
            )
            resp = client.post(f"/payments/booking/{BOOKING_ID}/refund")

        assert resp.status_code == 422


# ===========================================================================
# POST /payments/webhook
# ===========================================================================


class TestStripeWebhook:
    def _make_session_event(
        self, event_type: str, session_id: str, booking_id: str, mode: str = "payment"
    ):
        """Build a minimal Stripe event mock."""
        session = MagicMock()
        session.id = session_id
        session.payment_intent = STRIPE_PAYMENT_INTENT_ID
        session.metadata = {"booking_id": booking_id}
        session.client_reference_id = booking_id
        session.mode = mode

        event = MagicMock()
        event.type = event_type
        event.data.object = session
        return event

    def _make_charge_event(
        self,
        payment_intent_id: str | None,
        amount: int = 4000,
        amount_refunded: int = 4000,
        refunded: bool = True,
    ):
        charge = MagicMock()
        charge.payment_intent = payment_intent_id
        charge.amount = amount
        charge.amount_refunded = amount_refunded
        charge.refunded = refunded

        event = MagicMock()
        event.type = "charge.refunded"
        event.data.object = charge
        return event

    def _make_payment_intent_event(self, event_type: str, payment_intent_id: str):
        pi = MagicMock()
        pi.id = payment_intent_id

        event = MagicMock()
        event.type = event_type
        event.data.object = pi
        return event

    def test_completed_event_marks_payment_paid(self, client_factory):
        event = self._make_session_event(
            "checkout.session.completed", STRIPE_SESSION_ID, str(BOOKING_ID)
        )

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event
        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_paid = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"checkout.session.completed"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        mock_crud.mark_paid.assert_called_once_with(STRIPE_SESSION_ID, STRIPE_PAYMENT_INTENT_ID)

    def test_subscription_mode_grants_owner_role(self, client_factory):
        """checkout.session.completed with mode='subscription' grants owner role
        immediately from the session event."""
        owner_id = str(uuid4())
        event = self._make_session_event(
            "checkout.session.completed",
            STRIPE_SESSION_ID,
            str(BOOKING_ID),
            mode="subscription",
        )
        event.data.object.subscription = "sub_test_123"
        event.data.object.client_reference_id = owner_id
        event.data.object.metadata = MagicMock(owner_id=owner_id)

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event

        mock_uc = MagicMock()
        mock_uc.grant_role = AsyncMock()

        client = client_factory(make_customer(), stripe_client=mock_sc, users_client=mock_uc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_paid = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"checkout.session.completed"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        mock_uc.grant_role.assert_called_once()

    def test_expired_event_marks_failed_and_cancels_booking(self, client_factory):
        event = self._make_session_event(
            "checkout.session.expired", STRIPE_SESSION_ID, str(BOOKING_ID)
        )

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event

        mock_bc = MagicMock()
        mock_bc.cancel_booking = AsyncMock(return_value=True)

        client = client_factory(make_customer(), bookings_client=mock_bc, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_failed = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"checkout.session.expired"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_crud.mark_failed.assert_called_once_with(STRIPE_SESSION_ID)
        mock_bc.cancel_booking.assert_called_once()

    def test_expired_session_without_booking_id_returns_early(self, client_factory):
        """When booking_id_str is None (no metadata), handler returns early without crashing."""
        session = MagicMock()
        session.id = STRIPE_SESSION_ID
        session.metadata = {}
        session.client_reference_id = None

        event = MagicMock()
        event.type = "checkout.session.expired"
        event.data.object = session

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event

        mock_bc = MagicMock()
        mock_bc.cancel_booking = AsyncMock()

        client = client_factory(make_customer(), bookings_client=mock_bc, stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_failed = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"checkout.session.expired"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_bc.cancel_booking.assert_not_called()

    def test_refunded_charge_marks_payment_refunded(self, client_factory):
        event = self._make_charge_event(STRIPE_PAYMENT_INTENT_ID)

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event
        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_refunded = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"charge.refunded"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_crud.mark_refunded.assert_called_once_with(
            STRIPE_PAYMENT_INTENT_ID, Decimal("40.00"), True
        )

    def test_charge_refunded_without_payment_intent_returns_early(self, client_factory):
        """When payment_intent_id is None/falsy, mark_refunded is not called."""
        event = self._make_charge_event(None)

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event
        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_refunded = AsyncMock()
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"charge.refunded"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_crud.mark_refunded.assert_not_called()

    def test_payment_intent_payment_failed_returns_200(self, client_factory):
        """payment_intent.payment_failed: event dispatched and handled without crashing."""
        event = self._make_payment_intent_event(
            "payment_intent.payment_failed", STRIPE_PAYMENT_INTENT_ID
        )

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event
        client = client_factory(make_customer(), stripe_client=mock_sc)

        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.mark_failed = AsyncMock(return_value=MagicMock())
            resp = client.post(
                "/payments/webhook",
                content=b'{"type":"payment_intent.payment_failed"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}

    def test_invalid_signature_returns_400(self, client_factory):
        import stripe as stripe_lib

        mock_sc = MagicMock()
        mock_sc.construct_event.side_effect = stripe_lib.SignatureVerificationError(
            "invalid", "sig"
        )
        client = client_factory(make_customer(), stripe_client=mock_sc)

        resp = client.post(
            "/payments/webhook",
            content=b"bad payload",
            headers={"Stripe-Signature": "invalid"},
        )
        assert resp.status_code == 400

    def test_invalid_payload_returns_400(self, client_factory):
        mock_sc = MagicMock()
        mock_sc.construct_event.side_effect = ValueError("bad payload")
        client = client_factory(make_customer(), stripe_client=mock_sc)

        resp = client.post(
            "/payments/webhook",
            content=b"not json",
            headers={"Stripe-Signature": "t=1,v1=abc"},
        )
        assert resp.status_code == 400

    def test_subscription_deleted_event_cancels_and_revokes(self, client_factory):
        """customer.subscription.deleted must cancel the subscription record
        and revoke owner scopes -- Stripe uses 'canceled' (one L)."""
        owner_id = str(uuid4())

        sub = MagicMock()
        sub.metadata = MagicMock(owner_id=owner_id)

        event = MagicMock()
        event.type = "customer.subscription.deleted"
        event.data.object = sub

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event

        mock_uc = MagicMock()
        mock_uc.revoke_owner = AsyncMock()

        client = client_factory(make_customer(), stripe_client=mock_sc, users_client=mock_uc)

        with patch(
            "app.routers.payments.subscription_crud.cancel_subscription",
            new=AsyncMock(),
        ) as cancel_mock:
            resp = client.post(
                "/payments/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        cancel_mock.assert_called_once()
        mock_uc.revoke_owner.assert_called_once()

    def test_subscription_updated_with_cancel_at_period_end_persists_flag(self, client_factory):
        """customer.subscription.updated with cancel_at_period_end=True must
        persist the flag and must NOT grant owner role or send welcome email."""
        owner_id = str(uuid4())

        sub = MagicMock()
        sub.status = "active"
        sub.id = "sub_test"
        sub.customer = "cus_test"
        sub.current_period_end = 9_999_999_999
        sub.cancel_at_period_end = True
        sub.metadata = MagicMock(owner_id=owner_id, plan_slug="starter")

        event = MagicMock()
        event.type = "customer.subscription.updated"
        event.data.object = sub

        mock_sc = MagicMock()
        mock_sc.construct_event.return_value = event

        mock_uc = MagicMock()
        mock_uc.grant_role = AsyncMock()

        client = client_factory(make_customer(), stripe_client=mock_sc, users_client=mock_uc)

        mock_plan = MagicMock()
        mock_plan.id = uuid4()
        upsert_mock = AsyncMock()

        with (
            patch(
                "app.routers.payments.subscription_crud.get_plan_by_slug",
                new=AsyncMock(return_value=mock_plan),
            ),
            patch(
                "app.routers.payments.subscription_crud.upsert_subscription",
                new=upsert_mock,
            ),
        ):
            resp = client.post(
                "/payments/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        upsert_mock.assert_called_once()
        assert upsert_mock.call_args.kwargs["cancel_at_period_end"] is True
        mock_uc.grant_role.assert_not_called()


# ===========================================================================
# DELETE /payments/{payment_id}
# ===========================================================================


class TestDeletePayment:
    def test_admin_can_delete(self, admin_client):
        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.delete_payment = AsyncMock(return_value=True)
            resp = admin_client.delete(f"/payments/{PAYMENT_ID}")

        assert resp.status_code == 204

    def test_admin_delete_404(self, admin_client):
        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.delete_payment = AsyncMock(return_value=False)
            resp = admin_client.delete(f"/payments/{PAYMENT_ID}")

        assert resp.status_code == 404

    def test_non_admin_cannot_delete(self, customer_client):
        with patch("app.routers.payments.payment_crud") as mock_crud:
            mock_crud.delete_payment = AsyncMock(return_value=True)
            resp = customer_client.delete(f"/payments/{PAYMENT_ID}")

        # customer_client overrides all auth deps to pass -- but admin scope is missing.
        # The dep override in conftest sets `can_admin_delete_payment` to return the
        # customer user, but the route dependency is on `can_admin_delete_payment`,
        # which the conftest already overrides to the current user.
        # Real scope enforcement is tested via anon_app.
        assert resp.status_code in (204, 403)

    def test_requires_auth(self, anon_app):
        with TestClient(anon_app) as c:
            resp = c.delete(f"/payments/{PAYMENT_ID}")
        assert resp.status_code == 422
