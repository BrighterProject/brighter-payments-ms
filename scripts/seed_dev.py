"""Seed an active Starter subscription for dev_owner_sub.

Requires subscription plans to already exist (payments-ms seeds them on startup).
Run inside the payments-ms container:
    docker compose exec -T payments-ms uv run python scripts/seed_dev.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise

from app.models import OwnerSubscription, SubscriptionPlan, SubscriptionPlanSlug, SubscriptionStatus

DB_URL: str = os.environ.get("DB_URL", "asyncpg://brighter:brighter@localhost:5432/brighter")

# Must match brighter-users-ms/scripts/seed.py
DEV_OWNER_SUB_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")


async def seed() -> None:
    """Upsert an active subscription for dev_owner_sub."""
    await Tortoise.init(db_url=DB_URL, modules={"models": ["app.models"]})

    plan = await SubscriptionPlan.get(slug=SubscriptionPlanSlug.STARTER)
    _, created = await OwnerSubscription.update_or_create(
        owner_id=DEV_OWNER_SUB_ID,
        defaults={
            "id": uuid.UUID("b0000000-0000-0000-0000-000000000002"),
            "plan": plan,
            "status": SubscriptionStatus.ACTIVE,
            "current_period_end": datetime.now(timezone.utc) + timedelta(days=365),
        },
    )
    action = "Created" if created else "Updated"
    print(f"[seed] {action} ACTIVE starter subscription for dev_owner_sub")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(seed())
