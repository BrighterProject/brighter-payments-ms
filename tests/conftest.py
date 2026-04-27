"""
Shared pytest fixtures available to every test file automatically.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import (
    can_admin_delete_payment,
    can_read_payment,
    get_bookings_client,
    get_current_user,
    get_notifications_client,
    get_properties_client,
    get_stripe_client,
)
from app.routers.payments import router

from .factories import make_admin, make_customer, make_property_owner

# ---------------------------------------------------------------------------
# Default no-op mocks — prevent real HTTP / Stripe calls in tests
# ---------------------------------------------------------------------------


def _noop_bookings_client():
    mock = MagicMock()
    mock.get_booking = AsyncMock(return_value=None)
    mock.get_booking_as_admin = AsyncMock(return_value=None)
    mock.cancel_booking = AsyncMock(return_value=True)
    return mock


def _noop_notifications_client():
    mock = MagicMock()
    mock.send = AsyncMock(return_value=None)
    return mock


def _noop_properties_client():
    mock = MagicMock()
    mock.get_property_name = AsyncMock(return_value=None)
    return mock


def _noop_stripe_client():
    """Stripe client mock with no-op checkout and refund methods."""
    mock = MagicMock()
    # checkout.sessions.create returns an object with .id and .url
    session_mock = MagicMock()
    session_mock.id = "cs_test_mock"
    session_mock.url = "https://checkout.stripe.com/pay/cs_test_mock"
    mock.checkout.sessions.create.return_value = session_mock
    mock.refunds.create.return_value = MagicMock()
    # construct_event raises by default — tests that need it should override
    mock.construct_event.side_effect = Exception("Override construct_event in tests")
    return mock


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------


def build_app(
    current_user,
    bookings_client=None,
    stripe_client=None,
    notifications_client=None,
    properties_client=None,
) -> FastAPI:
    """
    Fresh FastAPI app with auth/scope dependencies overridden to return
    `current_user` unconditionally.

    Pass `bookings_client` / `stripe_client` to inject custom mocks.
    """
    app = FastAPI()
    app.include_router(router)

    async def _user():
        return current_user

    for dep in (can_read_payment, can_admin_delete_payment, get_current_user):
        app.dependency_overrides[dep] = _user

    bc = bookings_client if bookings_client is not None else _noop_bookings_client()
    sc = stripe_client if stripe_client is not None else _noop_stripe_client()
    nc = notifications_client if notifications_client is not None else _noop_notifications_client()
    pc = properties_client if properties_client is not None else _noop_properties_client()
    app.dependency_overrides[get_bookings_client] = lambda: bc
    app.dependency_overrides[get_stripe_client] = lambda: sc
    app.dependency_overrides[get_notifications_client] = lambda: nc
    app.dependency_overrides[get_properties_client] = lambda: pc

    return app


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer_client():
    return TestClient(build_app(make_customer()), raise_server_exceptions=True)


@pytest.fixture()
def owner_client():
    return TestClient(build_app(make_property_owner()), raise_server_exceptions=True)


@pytest.fixture()
def admin_client():
    return TestClient(build_app(make_admin()), raise_server_exceptions=True)


@pytest.fixture()
def anon_app():
    """Bare app with NO dependency overrides — for real auth/scope assertions."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client_factory():
    def _make(
        current_user,
        bookings_client=None,
        stripe_client=None,
        notifications_client=None,
        properties_client=None,
    ) -> TestClient:
        return TestClient(
            build_app(
                current_user,
                bookings_client=bookings_client,
                stripe_client=stripe_client,
                notifications_client=notifications_client,
                properties_client=properties_client,
            ),
            raise_server_exceptions=True,
        )

    return _make
