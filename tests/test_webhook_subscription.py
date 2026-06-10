"""Unit tests for _handle_subscription_updated scope grant + welcome email logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest

from app.models import SubscriptionStatus
from app.routers.payments import _handle_subscription_deleted, _handle_subscription_updated


def _make_subscription(
    status: str,
    owner_id: str,
    plan_slug: str = "starter",
    cancel_at_period_end: bool = False,
) -> MagicMock:
    sub = MagicMock()
    sub.status = status
    sub.id = "sub_test_123"
    sub.customer = "cus_test_123"
    sub.current_period_end = 9_999_999_999
    sub.cancel_at_period_end = cancel_at_period_end
    sub.metadata = MagicMock(owner_id=owner_id, plan_slug=plan_slug)
    sub.items = MagicMock(
        data=[MagicMock(price=MagicMock(metadata=MagicMock(plan_slug=plan_slug)))]
    )
    return sub


def _make_collaborators(user: dict | None = None):
    mock_plan = MagicMock(id=uuid4())
    users_client = MagicMock()
    users_client.get_user = AsyncMock(return_value=user or {"email": "owner@test.com", "locale": "bg"})
    users_client.grant_role = AsyncMock()
    users_client.revoke_owner = AsyncMock()
    notifications_client = MagicMock()
    notifications_client.send = AsyncMock()
    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()
    return mock_plan, users_client, notifications_client, background_tasks


# ---------------------------------------------------------------------------
# Contract: SubscriptionStatus string values must match Stripe's API exactly.
# Stripe uses single-L "canceled" — a mismatch here silently misfires webhooks.
# ---------------------------------------------------------------------------

def test_subscription_status_string_values_match_stripe():
    assert SubscriptionStatus.ACTIVE == "active"
    assert SubscriptionStatus.TRIALING == "trialing"
    assert SubscriptionStatus.PAST_DUE == "past_due"
    assert SubscriptionStatus.CANCELED == "canceled"
    assert SubscriptionStatus.INCOMPLETE == "incomplete"


def test_subscription_status_canceled_parses_from_stripe_string():
    """SubscriptionStatus('canceled') must not raise — this is what Stripe sends."""
    assert SubscriptionStatus("canceled") is SubscriptionStatus.CANCELED


def test_subscription_status_rejects_double_l():
    """Ensure the old double-L typo is not silently accepted."""
    import pytest as _pytest
    with _pytest.raises(ValueError):
        SubscriptionStatus("cancelled")


# ---------------------------------------------------------------------------
# upsert_subscription is called with the correct parsed status from Stripe.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_upsert_receives_correct_status_for_active():
    owner_id = str(uuid4())
    sub = _make_subscription("active", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()
    upsert_mock = AsyncMock()

    with (
        patch("app.routers.payments.subscription_crud.get_plan_by_slug", new=AsyncMock(return_value=mock_plan)),
        patch("app.routers.payments.subscription_crud.upsert_subscription", new=upsert_mock),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    assert upsert_mock.call_args.kwargs["status"] == SubscriptionStatus.ACTIVE


@pytest.mark.anyio
async def test_upsert_receives_correct_status_for_past_due():
    owner_id = str(uuid4())
    sub = _make_subscription("past_due", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()
    upsert_mock = AsyncMock()

    with (
        patch("app.routers.payments.subscription_crud.get_plan_by_slug", new=AsyncMock(return_value=mock_plan)),
        patch("app.routers.payments.subscription_crud.upsert_subscription", new=upsert_mock),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    assert upsert_mock.call_args.kwargs["status"] == SubscriptionStatus.PAST_DUE
    users_client.grant_role.assert_not_called()


# ---------------------------------------------------------------------------
# customer.subscription.deleted: handler correctly cancels and revokes scopes.
# (Webhook dispatcher routing is tested in test_payments.py via HTTP client.)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_subscription_deleted_no_grant_no_welcome():
    """Deleted subscription must not trigger a grant or welcome email."""
    owner_id = str(uuid4())
    sub = MagicMock()
    sub.metadata = MagicMock(owner_id=owner_id)
    _, users_client, notifications_client, background_tasks = _make_collaborators()

    with patch(
        "app.routers.payments.subscription_crud.cancel_subscription",
        new=AsyncMock(),
    ):
        await _handle_subscription_deleted(sub, users_client)

    users_client.grant_role.assert_not_called()
    background_tasks.add_task.assert_not_called()


@pytest.mark.anyio
async def test_active_subscription_grants_owner_role():
    owner_id = str(uuid4())
    sub = _make_subscription("active", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()

    with (
        patch(
            "app.routers.payments.subscription_crud.get_plan_by_slug",
            new=AsyncMock(return_value=mock_plan),
        ),
        patch(
            "app.routers.payments.subscription_crud.upsert_subscription",
            new=AsyncMock(),
        ),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    users_client.grant_role.assert_called_once_with(UUID(owner_id))
    background_tasks.add_task.assert_called_once()


@pytest.mark.anyio
async def test_trialing_subscription_grants_owner_role():
    owner_id = str(uuid4())
    sub = _make_subscription("trialing", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()

    with (
        patch(
            "app.routers.payments.subscription_crud.get_plan_by_slug",
            new=AsyncMock(return_value=mock_plan),
        ),
        patch(
            "app.routers.payments.subscription_crud.upsert_subscription",
            new=AsyncMock(),
        ),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    users_client.grant_role.assert_called_once_with(UUID(owner_id))


@pytest.mark.anyio
async def test_incomplete_subscription_skips_grant():
    owner_id = str(uuid4())
    sub = _make_subscription("incomplete", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()

    with (
        patch(
            "app.routers.payments.subscription_crud.get_plan_by_slug",
            new=AsyncMock(return_value=mock_plan),
        ),
        patch(
            "app.routers.payments.subscription_crud.upsert_subscription",
            new=AsyncMock(),
        ),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    users_client.grant_role.assert_not_called()
    background_tasks.add_task.assert_not_called()


@pytest.mark.anyio
async def test_welcome_email_uses_user_locale():
    owner_id = str(uuid4())
    sub = _make_subscription("active", owner_id)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators(
        user={"email": "owner@test.com", "locale": "en"}
    )

    with (
        patch(
            "app.routers.payments.subscription_crud.get_plan_by_slug",
            new=AsyncMock(return_value=mock_plan),
        ),
        patch(
            "app.routers.payments.subscription_crud.upsert_subscription",
            new=AsyncMock(),
        ),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    call_kwargs = background_tasks.add_task.call_args.kwargs
    assert call_kwargs.get("locale") == "en"


@pytest.mark.anyio
async def test_missing_owner_id_returns_early():
    sub = MagicMock()
    sub.metadata = MagicMock(owner_id=None)
    _, users_client, notifications_client, background_tasks = _make_collaborators()

    await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    users_client.grant_role.assert_not_called()


@pytest.mark.anyio
async def test_unknown_plan_slug_returns_early():
    owner_id = str(uuid4())
    sub = _make_subscription("active", owner_id, plan_slug="nonexistent")
    _, users_client, notifications_client, background_tasks = _make_collaborators()

    with patch(
        "app.routers.payments.subscription_crud.get_plan_by_slug",
        new=AsyncMock(return_value=None),
    ):
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    users_client.grant_role.assert_not_called()


@pytest.mark.anyio
async def test_cancel_at_period_end_persisted_and_no_grant():
    """cancel_at_period_end=True: upsert records the flag; no grant or welcome email sent."""
    owner_id = str(uuid4())
    sub = _make_subscription("active", owner_id, cancel_at_period_end=True)
    mock_plan, users_client, notifications_client, background_tasks = _make_collaborators()

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
        await _handle_subscription_updated(sub, users_client, notifications_client, background_tasks)

    upsert_mock.assert_called_once()
    call_kwargs = upsert_mock.call_args.kwargs
    assert call_kwargs["cancel_at_period_end"] is True
    users_client.grant_role.assert_not_called()
    background_tasks.add_task.assert_not_called()


@pytest.mark.anyio
async def test_subscription_deleted_cancels_and_revokes_owner():
    """customer.subscription.deleted: cancel_subscription called and owner scopes revoked."""
    owner_id = str(uuid4())
    sub = MagicMock()
    sub.metadata = MagicMock(owner_id=owner_id)
    _, users_client, _, _ = _make_collaborators()

    with patch(
        "app.routers.payments.subscription_crud.cancel_subscription",
        new=AsyncMock(),
    ) as cancel_mock:
        await _handle_subscription_deleted(sub, users_client)

    cancel_mock.assert_called_once_with(UUID(owner_id))
    users_client.revoke_owner.assert_called_once_with(UUID(owner_id))


@pytest.mark.anyio
async def test_subscription_deleted_missing_owner_id_returns_early():
    sub = MagicMock()
    sub.metadata = MagicMock(owner_id=None)
    _, users_client, _, _ = _make_collaborators()

    await _handle_subscription_deleted(sub, users_client)

    users_client.revoke_owner.assert_not_called()
