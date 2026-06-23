"""Startup task: ensure subscription plans exist in DB and Stripe."""

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger
from stripe import StripeClient

from app.models import SubscriptionPlan, SubscriptionPlanSlug

if TYPE_CHECKING:
    from stripe._base_address import BaseAddresses
from app.settings import stripe_api_base, stripe_secret_key

_PLACEHOLDER_KEYS = {"sk_test_placeholder", ""}

PLAN_DEFINITIONS: list[dict[str, Any]] = [
    dict(
        slug=SubscriptionPlanSlug.STARTER,
        name="Starter",
        max_listings=1,
        price_eur_cents=800,
    ),
    dict(
        slug=SubscriptionPlanSlug.BASIC,
        name="Basic",
        max_listings=5,
        price_eur_cents=2500,
    ),
    dict(slug=SubscriptionPlanSlug.PRO, name="Pro", max_listings=10, price_eur_cents=4000),
    dict(
        slug=SubscriptionPlanSlug.BUSINESS,
        name="Business",
        max_listings=15,
        price_eur_cents=5500,
    ),
    dict(
        slug=SubscriptionPlanSlug.ENTERPRISE,
        name="Enterprise",
        max_listings=-1,
        price_eur_cents=0,
    ),
]


def _find_or_create_stripe_price(client: StripeClient, plan_def: dict[str, Any]) -> str:
    slug = str(plan_def["slug"])
    query = f'metadata["brighter_plan_slug"]:"{slug}"'

    products = client.v1.products.search(params={"query": query, "limit": 1})
    if products.data:
        product_id = products.data[0].id
    else:
        product = client.v1.products.create(
            params={
                "name": f"Brighter {plan_def['name']} Plan",
                "metadata": {"brighter_plan_slug": slug},
            }
        )
        product_id = product.id
        logger.info("Created Stripe product {} for plan {}", product_id, slug)

    prices = client.v1.prices.list(
        params={
            "product": product_id,
            "active": True,
            "type": "recurring",
            "limit": 10,
        }
    )
    monthly = [p for p in prices.data if p.recurring and p.recurring.interval == "month"]
    if monthly:
        return monthly[0].id

    price = client.v1.prices.create(
        params={
            "product": product_id,
            "unit_amount": plan_def["price_eur_cents"],
            "currency": "eur",
            "recurring": {"interval": "month"},
            "metadata": {"brighter_plan_slug": slug},
        }
    )
    logger.info("Created Stripe price {} for plan {}", price.id, slug)
    return price.id


async def ensure_subscription_plans() -> None:
    has_stripe = stripe_secret_key not in _PLACEHOLDER_KEYS
    base_addresses: BaseAddresses = {}  # type: ignore[assignment]
    if stripe_api_base:
        base_addresses = {  # type: ignore[assignment]
            "api": stripe_api_base,
            "connect": stripe_api_base,
            "files": stripe_api_base,
        }
    client = StripeClient(stripe_secret_key, base_addresses=base_addresses) if has_stripe else None

    if not has_stripe:
        logger.warning("STRIPE_SECRET_KEY not configured — seeding plans without Stripe price IDs")

    for plan_def in PLAN_DEFINITIONS:
        slug: SubscriptionPlanSlug = plan_def["slug"]
        stripe_price_id: str | None = None

        if client is not None and slug != SubscriptionPlanSlug.ENTERPRISE:
            try:
                stripe_price_id = await asyncio.to_thread(
                    _find_or_create_stripe_price, client, plan_def
                )
            except Exception:
                logger.exception("Failed to sync Stripe price for plan {}", slug)

        plan, created = await SubscriptionPlan.get_or_create(
            slug=slug,
            defaults={**plan_def, "stripe_price_id": stripe_price_id},
        )
        if not created and stripe_price_id is not None and plan.stripe_price_id != stripe_price_id:
            plan.stripe_price_id = stripe_price_id
            await plan.save(update_fields=["stripe_price_id"])
            logger.info("Updated stripe_price_id for plan {}", slug)

        logger.debug("Plan {} ready (stripe_price_id={})", slug, plan.stripe_price_id)
