"""Seed the subscription_plans table with the four standard tiers."""

import asyncio
import os
import sys
from pathlib import Path

from tortoise import Tortoise

from app.models import SubscriptionPlan, SubscriptionPlanSlug

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PLANS = [
    dict(
        slug=SubscriptionPlanSlug.STARTER,
        name="Starter",
        max_listings=1,
        price_eur_cents=800,
        stripe_price_id=None,
    ),
    dict(
        slug=SubscriptionPlanSlug.BASIC,
        name="Basic",
        max_listings=5,
        price_eur_cents=2500,
        stripe_price_id=None,
    ),
    dict(
        slug=SubscriptionPlanSlug.PRO,
        name="Pro",
        max_listings=10,
        price_eur_cents=4000,
        stripe_price_id=None,
    ),
    dict(
        slug=SubscriptionPlanSlug.BUSINESS,
        name="Business",
        max_listings=15,
        price_eur_cents=5500,
        stripe_price_id=None,
    ),
    dict(
        slug=SubscriptionPlanSlug.ENTERPRISE,
        name="Enterprise",
        max_listings=-1,
        price_eur_cents=0,
        stripe_price_id=None,
    ),
]


async def seed() -> None:
    """Insert subscription plans if they don't already exist."""
    db_url = os.environ["DB_URL"]
    await Tortoise.init(db_url=db_url, modules={"models": ["app.models"]})
    for p in PLANS:
        await SubscriptionPlan.get_or_create(slug=p["slug"], defaults=p)
        print(f"  seeded {p['slug']}")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(seed())
