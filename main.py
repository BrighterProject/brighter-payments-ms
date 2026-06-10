from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from ms_core import setup_app

from app.logging import setup_logging
from app.routers._connect import router as connect_router
from app.settings import db_url, stripe_secret_key, stripe_webhook_secret
from app.startup import ensure_subscription_plans
from app.telemetry import setup_telemetry

TORTOISE_ORM = {
    "connections": {"default": db_url},
    "apps": {
        "models": {
            "models": ["app.models"],
            "default_connection": "default",
            "migrations": "migrations.models",
        },
    },
}

setup_logging()

_PLACEHOLDER_KEYS = {"sk_test_placeholder", "whsec_placeholder"}
if stripe_secret_key in _PLACEHOLDER_KEYS or stripe_webhook_secret in _PLACEHOLDER_KEYS:
    logger.warning(
        "STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET is using a placeholder value. "
        "Set real keys via environment variables before processing payments."
    )

application = FastAPI(title="brighter-payments-ms", redirect_slashes=False)

application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_telemetry(application, "brighter-payments-ms")
application.include_router(connect_router)
setup_app(application, db_url, Path("app") / "routers", ["app.models"])

# Wrap the existing lifespan (which includes Tortoise init) so that
# ensure_subscription_plans runs after the ORM is ready.
_existing_lifespan = application.router.lifespan_context


@asynccontextmanager
async def _lifespan_with_plans(app: FastAPI):
    async with _existing_lifespan(app):
        await ensure_subscription_plans()
        yield


application.router.lifespan_context = _lifespan_with_plans
