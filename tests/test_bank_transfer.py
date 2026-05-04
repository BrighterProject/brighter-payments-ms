"""Tests for POST /payments/bank-transfer endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_bookings_client, get_current_user
from app.routers.bank_transfer import router as bt_router

from .factories import (
    BOOKING_ID,
    CUSTOMER_ID,
    PROPERTY_OWNER_ID,
    NOW,
    booking_dict,
    make_customer,
    make_property_owner,
    make_admin,
)

CRUD_PATH = "app.routers.bank_transfer.bank_transfer_crud"

INTENT_ID = uuid4()


def _bank_transfer_response(**overrides) -> dict:
    base = dict(
        id=str(INTENT_ID),
        booking_id=str(BOOKING_ID),
        status="pending",
        amount="40.00",
        currency="EUR",
        bank_iban="BG80BNBG96611020345678",
        bank_bic="BNBGBGSD",
        bank_name="BNB",
        account_holder="Brighter OOD",
        reference=f"BK-{str(BOOKING_ID)[:8].upper()}",
        updated_at=NOW.isoformat(),
    )
    return {**base, **overrides}


def _build_bt_app(current_user, bookings_client=None) -> FastAPI:
    app = FastAPI()
    app.include_router(bt_router)

    async def _user():
        return current_user

    app.dependency_overrides[get_current_user] = _user

    bc = bookings_client or MagicMock(
        get_booking=AsyncMock(return_value=None),
    )
    app.dependency_overrides[get_bookings_client] = lambda: bc

    return app


@pytest.fixture()
def owner_client():
    mock_bc = MagicMock()
    mock_bc.get_booking = AsyncMock(
        return_value=booking_dict(
            user_id=str(CUSTOMER_ID),
            property_owner_id=str(PROPERTY_OWNER_ID),
            status="pending",
        )
    )
    app = _build_bt_app(make_property_owner(), bookings_client=mock_bc)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def customer_client():
    mock_bc = MagicMock()
    mock_bc.get_booking = AsyncMock(
        return_value=booking_dict(
            user_id=str(CUSTOMER_ID),
            property_owner_id=str(PROPERTY_OWNER_ID),
            status="pending",
        )
    )
    app = _build_bt_app(make_customer(), bookings_client=mock_bc)
    return TestClient(app, raise_server_exceptions=True)


class TestCreateBankTransferIntent:
    def test_create_bank_transfer_intent(self, customer_client):
        with patch(CRUD_PATH) as mock:
            mock.create_intent = AsyncMock(return_value=_bank_transfer_response())
            resp = customer_client.post(
                "/payments/bank-transfer/", json={"booking_id": str(BOOKING_ID)}
            )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"
        assert resp.json()["bank_iban"] == "BG80BNBG96611020345678"

    def test_non_owner_user_is_forbidden(self):
        """A different user cannot create an intent for someone else's booking."""
        other_user = make_customer(user_id=uuid4())
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(
            return_value=booking_dict(user_id=str(CUSTOMER_ID), status="pending")
        )
        app = _build_bt_app(other_user, bookings_client=mock_bc)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/payments/bank-transfer/", json={"booking_id": str(BOOKING_ID)}
        )
        assert resp.status_code == 403

    def test_booking_not_found_returns_404(self):
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(return_value=None)
        app = _build_bt_app(make_customer(), bookings_client=mock_bc)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/payments/bank-transfer/", json={"booking_id": str(BOOKING_ID)}
        )
        assert resp.status_code == 404

    def test_non_pending_booking_returns_422(self):
        mock_bc = MagicMock()
        mock_bc.get_booking = AsyncMock(
            return_value=booking_dict(user_id=str(CUSTOMER_ID), status="confirmed")
        )
        app = _build_bt_app(make_customer(), bookings_client=mock_bc)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/payments/bank-transfer/", json={"booking_id": str(BOOKING_ID)}
        )
        assert resp.status_code == 422


class TestConfirmBankTransfer:
    def test_owner_can_confirm(self, owner_client):
        with patch(CRUD_PATH) as mock:
            mock.get_by_id = AsyncMock(
                return_value=MagicMock(
                    id=INTENT_ID,
                    property_owner_id=PROPERTY_OWNER_ID,
                )
            )
            mock.confirm_intent = AsyncMock(
                return_value=_bank_transfer_response(status="confirmed")
            )
            resp = owner_client.post(f"/payments/bank-transfer/{INTENT_ID}/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    def test_intent_not_found_returns_404(self, owner_client):
        with patch(CRUD_PATH) as mock:
            mock.get_by_id = AsyncMock(return_value=None)
            resp = owner_client.post(f"/payments/bank-transfer/{INTENT_ID}/confirm")
        assert resp.status_code == 404
