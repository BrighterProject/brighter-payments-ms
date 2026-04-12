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
ACCOUNT_LINK_URL = "https://connect.stripe.com/setup/e/acct_test_abc123/abc"


# ---------------------------------------------------------------------------
# App builder for connect endpoint tests
# ---------------------------------------------------------------------------


def _noop_stripe_client():
    mock = MagicMock()
    mock.v1 = MagicMock()

    # accounts.create returns an object with .id
    new_account_mock = MagicMock()
    new_account_mock.id = STRIPE_ACCOUNT_ID
    mock.v1.accounts.create.return_value = new_account_mock

    # account_links.create returns an object with .url
    link_mock = MagicMock()
    link_mock.url = ACCOUNT_LINK_URL
    mock.v1.account_links.create.return_value = link_mock

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
# GET /payments/connect/status
# ---------------------------------------------------------------------------


def test_status_not_connected(owner_client):
    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=None)):
        resp = owner_client.get("/payments/connect/status")
    assert resp.status_code == 200
    assert resp.json() == {
        "connected": False,
        "verified": False,
        "charges_enabled": False,
        "stripe_account_id": None,
        "requirements_outstanding": False,
    }


def test_status_connected_verified(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_account.verified = True
    mock_account.charges_enabled = True
    mock_account.requirements_outstanding = False

    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=mock_account)):
        resp = owner_client.get("/payments/connect/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["verified"] is True
    assert data["charges_enabled"] is True
    assert data["stripe_account_id"] == STRIPE_ACCOUNT_ID
    assert data["requirements_outstanding"] is False


def test_status_connected_pending(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_account.verified = False
    mock_account.charges_enabled = False
    mock_account.requirements_outstanding = False

    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=mock_account)):
        resp = owner_client.get("/payments/connect/status")

    data = resp.json()
    assert data["connected"] is True
    assert data["verified"] is False
    assert data["charges_enabled"] is False
    assert data["requirements_outstanding"] is False


def test_status_shows_requirements_outstanding(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID
    mock_account.verified = True
    mock_account.charges_enabled = True
    mock_account.requirements_outstanding = True

    with patch("app.routers.connect.connect_crud.get_by_owner", AsyncMock(return_value=mock_account)):
        resp = owner_client.get("/payments/connect/status")

    assert resp.json()["requirements_outstanding"] is True


def test_status_requires_auth(anon_app):
    client = TestClient(anon_app, raise_server_exceptions=False)
    resp = client.get("/payments/connect/status")
    assert resp.status_code == 422  # missing X-User-Id header


# ---------------------------------------------------------------------------
# POST /payments/connect/onboard
# ---------------------------------------------------------------------------


def test_onboard_creates_new_account_when_not_connected(owner_client):
    """When the owner has no account, a new Express account is created and the link returned."""
    with (
        patch(
            "app.routers.connect.connect_crud.get_by_owner",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.routers.connect.connect_crud.upsert",
            AsyncMock(return_value=MagicMock()),
        ),
    ):
        resp = owner_client.post("/payments/connect/onboard")

    assert resp.status_code == 200
    data = resp.json()
    assert "redirect_url" in data
    assert data["redirect_url"] == ACCOUNT_LINK_URL


def test_onboard_reuses_existing_account_when_connected(owner_client):
    """When the owner already has an account, no new account is created."""
    from app.models import OwnerStripeAccount

    existing = MagicMock(spec=OwnerStripeAccount)
    existing.stripe_account_id = STRIPE_ACCOUNT_ID

    sc = _noop_stripe_client()
    client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc), raise_server_exceptions=True)

    with patch(
        "app.routers.connect.connect_crud.get_by_owner",
        AsyncMock(return_value=existing),
    ):
        resp = client.post("/payments/connect/onboard")

    sc.v1.accounts.create.assert_not_called()
    assert resp.status_code == 200
    assert resp.json()["redirect_url"] == ACCOUNT_LINK_URL


def test_onboard_account_link_uses_correct_type(owner_client):
    """Account link must be of type account_onboarding."""
    sc = _noop_stripe_client()
    client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc), raise_server_exceptions=True)

    with (
        patch(
            "app.routers.connect.connect_crud.get_by_owner",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.routers.connect.connect_crud.upsert",
            AsyncMock(return_value=MagicMock()),
        ),
    ):
        client.post("/payments/connect/onboard")

    call_params = sc.v1.account_links.create.call_args[1]["params"]
    assert call_params["type"] == "account_onboarding"


def test_onboard_requires_auth(anon_app):
    client = TestClient(anon_app, raise_server_exceptions=False)
    resp = client.post("/payments/connect/onboard")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /payments/connect
# ---------------------------------------------------------------------------


def test_disconnect_removes_account(owner_client):
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID

    with (
        patch(
            "app.routers.connect.connect_crud.get_by_owner",
            AsyncMock(return_value=mock_account),
        ),
        patch(
            "app.routers.connect.connect_crud.delete_by_owner",
            AsyncMock(return_value=True),
        ),
    ):
        resp = owner_client.delete("/payments/connect")

    assert resp.status_code == 204


def test_disconnect_404_when_not_connected(owner_client):
    with patch(
        "app.routers.connect.connect_crud.get_by_owner",
        AsyncMock(return_value=None),
    ):
        resp = owner_client.delete("/payments/connect")
    assert resp.status_code == 404


def test_disconnect_still_removes_if_stripe_delete_fails(owner_client):
    """Local DB record removed even if Stripe account deletion raises."""
    from app.models import OwnerStripeAccount

    mock_account = MagicMock(spec=OwnerStripeAccount)
    mock_account.stripe_account_id = STRIPE_ACCOUNT_ID

    sc = _noop_stripe_client()
    sc.v1.accounts.delete.side_effect = Exception("Stripe error")

    delete_mock = AsyncMock(return_value=True)
    client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc), raise_server_exceptions=True)

    with (
        patch(
            "app.routers.connect.connect_crud.get_by_owner",
            AsyncMock(return_value=mock_account),
        ),
        patch("app.routers.connect.connect_crud.delete_by_owner", delete_mock),
    ):
        resp = client.delete("/payments/connect")

    assert resp.status_code == 204
    delete_mock.assert_called_once()


def test_disconnect_requires_auth(anon_app):
    client = TestClient(anon_app, raise_server_exceptions=False)
    resp = client.delete("/payments/connect")
    assert resp.status_code == 422


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
    mock_inst.verified = False
    mock_inst.charges_enabled = False

    with (
        patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=None)),
        patch.object(OwnerStripeAccount, "create", AsyncMock(return_value=mock_inst)),
    ):
        result = await ConnectCRUD().upsert(
            PROPERTY_OWNER_ID, STRIPE_ACCOUNT_ID, verified=False, charges_enabled=False
        )

    assert result.stripe_account_id == STRIPE_ACCOUNT_ID


@pytest.mark.asyncio
async def test_crud_upsert_updates_when_exists():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    existing = MagicMock(spec=OwnerStripeAccount)
    existing.save = AsyncMock()
    existing.stripe_account_id = "acct_old"

    with patch.object(OwnerStripeAccount, "get_or_none", AsyncMock(return_value=existing)):
        await ConnectCRUD().upsert(
            PROPERTY_OWNER_ID, STRIPE_ACCOUNT_ID, verified=True, charges_enabled=True
        )

    assert existing.stripe_account_id == STRIPE_ACCOUNT_ID
    assert existing.verified is True
    assert existing.charges_enabled is True
    existing.save.assert_called_once()


@pytest.mark.asyncio
async def test_crud_update_charges_enabled():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.update = AsyncMock(return_value=1)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        await ConnectCRUD().update_charges_enabled(STRIPE_ACCOUNT_ID, charges_enabled=True)

    mock_qs.update.assert_called_once_with(charges_enabled=True, verified=True)


@pytest.mark.asyncio
async def test_crud_delete_returns_true_on_success():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.delete = AsyncMock(return_value=1)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        result = await ConnectCRUD().delete_by_owner(PROPERTY_OWNER_ID)

    assert result is True


@pytest.mark.asyncio
async def test_crud_delete_returns_false_when_not_found():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.delete = AsyncMock(return_value=0)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        result = await ConnectCRUD().delete_by_owner(PROPERTY_OWNER_ID)

    assert result is False


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


# ---------------------------------------------------------------------------
# POST /payments/connect/webhook  (Connect / V2 event destination)
# ---------------------------------------------------------------------------


def _make_connect_stripe_client(event_type: str, account_id: str, *, charges_enabled: bool = True):
    """Build a mock StripeClient for connect webhook tests."""
    sc = MagicMock()

    # parse_thin_event returns a thin event
    thin_event = MagicMock()
    thin_event.type = event_type
    thin_event.related_object.id = account_id
    sc.parse_thin_event.return_value = thin_event

    # v1.accounts.retrieve returns a minimal account object
    account = MagicMock()
    account.charges_enabled = charges_enabled
    account.requirements.currently_due = []
    account.requirements.past_due = []
    sc.v1.accounts.retrieve.return_value = account

    return sc


class TestConnectWebhook:
    def test_account_updated_flips_charges_enabled(self, owner_client):
        sc = _make_connect_stripe_client("v2.core.account.updated", STRIPE_ACCOUNT_ID, charges_enabled=True)
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc))

        with patch("app.routers.connect.connect_crud.update_charges_enabled", AsyncMock()) as mock_update:
            resp = client.post(
                "/payments/connect/webhook",
                content=b'{"type":"v2.core.account.updated"}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        mock_update.assert_called_once_with(STRIPE_ACCOUNT_ID, True)

    def test_account_updated_charges_disabled(self, owner_client):
        sc = _make_connect_stripe_client("v2.core.account.updated", STRIPE_ACCOUNT_ID, charges_enabled=False)
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc))

        with patch("app.routers.connect.connect_crud.update_charges_enabled", AsyncMock()) as mock_update:
            resp = client.post(
                "/payments/connect/webhook",
                content=b'{}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_update.assert_called_once_with(STRIPE_ACCOUNT_ID, False)

    def test_requirements_updated_sets_flag_when_due(self, owner_client):
        sc = _make_connect_stripe_client(
            "v2.core.account[requirements].updated", STRIPE_ACCOUNT_ID
        )
        # Simulate an outstanding currently_due requirement
        sc.v1.accounts.retrieve.return_value.requirements.currently_due = ["individual.id_number"]
        sc.v1.accounts.retrieve.return_value.requirements.past_due = []
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc))

        with patch("app.routers.connect.connect_crud.update_requirements", AsyncMock()) as mock_update:
            resp = client.post(
                "/payments/connect/webhook",
                content=b'{}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_update.assert_called_once_with(STRIPE_ACCOUNT_ID, True)

    def test_requirements_updated_clears_flag_when_resolved(self, owner_client):
        sc = _make_connect_stripe_client(
            "v2.core.account[requirements].updated", STRIPE_ACCOUNT_ID
        )
        # All requirements resolved
        sc.v1.accounts.retrieve.return_value.requirements.currently_due = []
        sc.v1.accounts.retrieve.return_value.requirements.past_due = []
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc))

        with patch("app.routers.connect.connect_crud.update_requirements", AsyncMock()) as mock_update:
            resp = client.post(
                "/payments/connect/webhook",
                content=b'{}',
                headers={"Stripe-Signature": "t=1,v1=abc"},
            )

        assert resp.status_code == 200
        mock_update.assert_called_once_with(STRIPE_ACCOUNT_ID, False)

    def test_invalid_signature_returns_400(self, owner_client):
        import stripe as stripe_lib

        sc = MagicMock()
        sc.parse_thin_event.side_effect = stripe_lib.SignatureVerificationError(
            "invalid", "sig"
        )
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc), raise_server_exceptions=False)

        resp = client.post(
            "/payments/connect/webhook",
            content=b"bad payload",
            headers={"Stripe-Signature": "invalid"},
        )
        assert resp.status_code == 400

    def test_invalid_payload_returns_400(self, owner_client):
        sc = MagicMock()
        sc.parse_thin_event.side_effect = ValueError("bad payload")
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc), raise_server_exceptions=False)

        resp = client.post(
            "/payments/connect/webhook",
            content=b"not json",
            headers={"Stripe-Signature": "t=1,v1=abc"},
        )
        assert resp.status_code == 400

    def test_unknown_event_type_returns_200(self, owner_client):
        sc = _make_connect_stripe_client("v2.core.account.something_else", STRIPE_ACCOUNT_ID)
        client = TestClient(build_connect_app(make_property_owner(), stripe_client=sc))

        resp = client.post(
            "/payments/connect/webhook",
            content=b'{}',
            headers={"Stripe-Signature": "t=1,v1=abc"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"received": True}


# ---------------------------------------------------------------------------
# ConnectCRUD.update_requirements unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_update_requirements_sets_flag():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.update = AsyncMock(return_value=1)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        await ConnectCRUD().update_requirements(STRIPE_ACCOUNT_ID, has_requirements=True)

    mock_qs.update.assert_called_once_with(requirements_outstanding=True)


@pytest.mark.asyncio
async def test_crud_update_requirements_clears_flag():
    from app.crud_connect import ConnectCRUD
    from app.models import OwnerStripeAccount

    mock_qs = MagicMock()
    mock_qs.update = AsyncMock(return_value=1)

    with patch.object(OwnerStripeAccount, "filter", return_value=mock_qs):
        await ConnectCRUD().update_requirements(STRIPE_ACCOUNT_ID, has_requirements=False)

    mock_qs.update.assert_called_once_with(requirements_outstanding=False)
