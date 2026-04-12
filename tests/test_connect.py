"""Tests for the Stripe Connect CRUD and endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_stripe_client
from app.routers.connect import router as connect_router

from .factories import make_property_owner, PROPERTY_OWNER_ID

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

STRIPE_ACCOUNT_ID = "acct_test_abc123"


# ---------------------------------------------------------------------------
# App builder for connect endpoint tests
# ---------------------------------------------------------------------------


def _noop_stripe_client():
    mock = MagicMock()
    account_mock = MagicMock()
    account_mock.details_submitted = True
    account_mock.requirements = MagicMock()
    account_mock.requirements.disabled_reason = None
    mock.v1 = MagicMock()
    mock.v1.accounts.retrieve.return_value = account_mock
    return mock


def build_connect_app(current_user, stripe_client=None) -> FastAPI:
    app = FastAPI()
    app.include_router(connect_router)
    app.dependency_overrides[get_current_user] = lambda: current_user
    sc = stripe_client if stripe_client is not None else _noop_stripe_client()
    app.dependency_overrides[get_stripe_client] = lambda: sc
    return app


@pytest.fixture()
def owner_client():
    return TestClient(build_connect_app(make_property_owner()), raise_server_exceptions=True)


@pytest.fixture()
def anon_app():
    """Bare app with no dependency overrides — for auth/scope assertions."""
    app = FastAPI()
    app.include_router(connect_router)
    return app


# ---------------------------------------------------------------------------
# ConnectCRUD unit tests (ORM mocked)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /payments/connect/status
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# POST /payments/connect/onboard
# ---------------------------------------------------------------------------


def test_onboard_returns_redirect_url(owner_client):
    resp = owner_client.post("/payments/connect/onboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "redirect_url" in data
    assert "connect.stripe.com/oauth/authorize" in data["redirect_url"]


def test_onboard_url_encodes_owner_state(owner_client):
    resp = owner_client.post("/payments/connect/onboard")
    data = resp.json()
    assert str(PROPERTY_OWNER_ID) in data["redirect_url"]


def test_onboard_url_contains_client_id(owner_client):
    resp = owner_client.post("/payments/connect/onboard")
    data = resp.json()
    assert "client_id=" in data["redirect_url"]


def test_onboard_requires_auth(anon_app):
    client = TestClient(anon_app, raise_server_exceptions=False)
    resp = client.post("/payments/connect/onboard")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /payments/connect/status
# ---------------------------------------------------------------------------


def test_status_not_connected(owner_client):
    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=None)):
        resp = owner_client.get("/payments/connect/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "verified": False, "stripe_account_id": None}


def test_status_connected_verified(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_account.verified = True

    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=mock_account)):
        resp = owner_client.get("/payments/connect/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["verified"] is True
    assert data["stripe_account_id"] == STRIPE_ACCOUNT_ID


def test_status_connected_pending(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_account.verified = False

    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=mock_account)):
        resp = owner_client.get("/payments/connect/status")

    data = resp.json()
    assert data["connected"] is True
    assert data["verified"] is False


def test_status_requires_auth(anon_app):
    client = TestClient(anon_app, raise_server_exceptions=False)
    resp = client.get("/payments/connect/status")
    assert resp.status_code == 422  # missing X-User-Id header


# ---------------------------------------------------------------------------
# ConnectCRUD unit tests (ORM mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_get_by_owner_returns_none_when_missing():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    with patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=None)):
        result = await ConnectCRUD().get_by_owner(PROPERTY_OWNER_ID)

    assert result is None


@pytest.mark.asyncio
async def test_crud_get_by_owner_returns_record_when_found():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_inst = MagicMock(spec=OwnerStripeAccount)
    mock_inst.stripe_account_id = STRIPE_ACCOUNT_ID

    with patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=mock_inst)):
        result = await ConnectCRUD().get_by_owner(PROPERTY_OWNER_ID)

    assert result is mock_inst


@pytest.mark.asyncio
async def test_crud_upsert_creates_when_not_exists():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_inst = MagicMock(spec=OwnerStripeAccount)
    mock_inst.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_inst.verified = True

    with (
        patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=None)),
        patch.object(OwnerStripeAccount, "create", AsyncMock(return_value=mock_inst)),
    ):
        result = await ConnectCRUD().upsert(PROPERTY_OWNER_ID, STRIPE_ACCOUNT_ID, verified=True)

    assert result.stripe_account_id == STRIPE_ACCOUNT_ID


@pytest.mark.asyncio
async def test_crud_upsert_updates_when_exists():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    existing = MagicMock(spec=OwnerStripeAccount)
    existing.save = AsyncMock()
    existing.stripe_account_id = "acct_old"

    with patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=existing)):
        await ConnectCRUD().upsert(PROPERTY_OWNER_ID, STRIPE_ACCOUNT_ID, verified=True)

    assert existing.stripe_account_id == STRIPE_ACCOUNT_ID
    assert existing.verified is True
    existing.save.assert_called_once()


@pytest.mark.asyncio
async def test_crud_delete_returns_true_on_success():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.delete = AsyncMock(return_value=1)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        result = await ConnectCRUD().delete_by_owner(PROPERTY_OWNER_ID)

    assert result is True


# ---------------------------------------------------------------------------
# require_owner unit tests
# ---------------------------------------------------------------------------


def test_require_owner_blocks_regular_user():
    from app.deps import CurrentUser, require_owner
    from fastapi import HTTPException

    user = CurrentUser(id=uuid4(), username="user", scopes=["payments:read"])
    with pytest.raises(HTTPException) as exc_info:
        require_owner(current_user=user)
    assert exc_info.value.status_code == 403


def test_require_owner_allows_owner():
    from app.deps import CurrentUser, require_owner

    owner = CurrentUser(id=uuid4(), username="owner", scopes=["bookings:manage"])
    result = require_owner(current_user=owner)
    assert result is owner


def test_require_owner_allows_admin():
    from app.deps import CurrentUser, require_owner

    admin = CurrentUser(id=uuid4(), username="admin", scopes=["admin:scopes"])
    result = require_owner(current_user=admin)
    assert result is admin


@pytest.mark.asyncio
async def test_crud_delete_returns_false_when_not_found():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.delete = AsyncMock(return_value=0)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        result = await ConnectCRUD().delete_by_owner(PROPERTY_OWNER_ID)

    assert result is False
