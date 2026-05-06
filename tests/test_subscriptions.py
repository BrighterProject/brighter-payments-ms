"""Tests for subscription plan models, CRUD, and router endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_stripe_client
from tests.factories import make_admin, make_property_owner


# ---------------------------------------------------------------------------
# Local fixtures — build an app that includes the subscriptions router
# ---------------------------------------------------------------------------


def _build_sub_app(current_user):
    from app.routers.subscriptions import router as sub_router

    app = FastAPI()
    app.include_router(sub_router)

    async def _user():
        return current_user

    app.dependency_overrides[get_current_user] = _user

    mock_stripe = MagicMock()
    app.dependency_overrides[get_stripe_client] = lambda: mock_stripe

    return app, mock_stripe


@pytest.fixture()
def sub_owner_client():
    app, _ = _build_sub_app(make_property_owner())
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def sub_admin_client():
    app, _ = _build_sub_app(make_admin())
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def sub_owner_client_with_stripe():
    app, mock_stripe = _build_sub_app(make_property_owner())
    return TestClient(app, raise_server_exceptions=True), mock_stripe


# ---------------------------------------------------------------------------
# Task 1 — model shape (pure instantiation, no DB)
# ---------------------------------------------------------------------------


def test_subscription_plan_fields():
    from app.models import SubscriptionPlan, SubscriptionPlanSlug

    plan = SubscriptionPlan(
        slug=SubscriptionPlanSlug.BASIC,
        name="Basic",
        max_listings=5,
        price_eur_cents=1500,
        stripe_price_id="price_test_123",
    )
    assert plan.max_listings == 5


def test_owner_subscription_default_status():
    from app.models import SubscriptionStatus

    assert SubscriptionStatus.ACTIVE == "active"
    assert SubscriptionStatus.PAST_DUE == "past_due"


# ---------------------------------------------------------------------------
# Task 2 — CRUD via router
# ---------------------------------------------------------------------------


def _make_plan(slug, plan_name, max_listings, price, stripe_price_id):
    """Build a MagicMock plan that pydantic model_validate can read."""
    m = MagicMock()
    m.id = uuid4()
    m.slug = slug
    m.name = plan_name
    m.max_listings = max_listings
    m.price_eur_cents = price
    m.stripe_price_id = stripe_price_id
    m.is_active = True
    return m


def test_list_all_subscriptions_admin(sub_admin_client):
    mock_sub = MagicMock()
    mock_sub.id = uuid4()
    mock_sub.owner_id = uuid4()
    mock_sub.status = "active"
    mock_sub.current_period_end = None
    mock_sub.cancelled_at = None
    mock_sub.plan = _make_plan("basic", "Basic", 5, 2500, "price_b")
    with patch("app.routers.subscriptions.subscription_crud") as mock:
        mock.list_all = AsyncMock(return_value=[mock_sub])
        resp = sub_admin_client.get("/subscriptions/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_all_subscriptions_forbidden_for_owner(sub_owner_client):
    resp = sub_owner_client.get("/subscriptions/")
    assert resp.status_code == 403


def test_list_plans_returns_all(sub_admin_client):
    mock_plans = [
        _make_plan("starter", "Starter", 1, 800, "price_s"),
        _make_plan("basic", "Basic", 5, 2500, "price_b"),
    ]
    with patch("app.routers.subscriptions.subscription_crud") as mock:
        mock.list_plans = AsyncMock(return_value=mock_plans)
        resp = sub_admin_client.get("/subscriptions/plans")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_my_subscription_not_found(sub_owner_client):
    with patch("app.routers.subscriptions.subscription_crud") as mock:
        mock.get_owner_subscription = AsyncMock(return_value=None)
        resp = sub_owner_client.get("/subscriptions/me")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 3 — checkout + portal endpoints
# ---------------------------------------------------------------------------


def test_get_plans_public():
    from app.routers.subscriptions import router as sub_router

    app = FastAPI()
    app.include_router(sub_router)
    client = TestClient(app, raise_server_exceptions=True)
    with patch("app.routers.subscriptions.subscription_crud") as mock:
        mock.list_plans = AsyncMock(return_value=[])
        resp = client.get("/subscriptions/plans")
    assert resp.status_code == 200


def test_subscribe_creates_checkout(sub_owner_client_with_stripe):
    client, mock_stripe = sub_owner_client_with_stripe
    mock_plan = MagicMock(stripe_price_id="price_123", slug="basic")
    mock_session = MagicMock(url="https://checkout.stripe.com/s/test", id="cs_test")
    mock_stripe.v1.checkout.sessions.create.return_value = mock_session
    with patch("app.routers.subscriptions.subscription_crud") as mock_crud:
        mock_crud.get_plan_by_slug = AsyncMock(return_value=mock_plan)
        resp = client.post("/subscriptions/checkout?plan_slug=basic")
    assert resp.status_code == 201
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/s/test"


def test_subscribe_enterprise_returns_422(sub_owner_client):
    mock_plan = MagicMock(stripe_price_id=None, slug="enterprise")
    with patch("app.routers.subscriptions.subscription_crud") as mock_crud:
        mock_crud.get_plan_by_slug = AsyncMock(return_value=mock_plan)
        resp = sub_owner_client.post("/subscriptions/checkout?plan_slug=enterprise")
    assert resp.status_code == 422
