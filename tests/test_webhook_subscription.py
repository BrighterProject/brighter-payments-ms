"""Unit tests for _handle_subscription_updated scope grant + welcome email logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest

from app.routers.payments import _handle_subscription_updated


def _make_subscription(status: str, owner_id: str, plan_slug: str = "starter") -> MagicMock:
    sub = MagicMock()
    sub.status = status
    sub.id = "sub_test_123"
    sub.customer = "cus_test_123"
    sub.current_period_end = 9_999_999_999
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
    notifications_client = MagicMock()
    notifications_client.send = AsyncMock()
    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()
    return mock_plan, users_client, notifications_client, background_tasks


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
