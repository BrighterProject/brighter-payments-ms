from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from ms_core import setup_app

from app.logging import setup_logging
from app.settings import db_url, stripe_secret_key, stripe_webhook_secret

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

tortoise_conf = setup_app(application, db_url, Path("app") / "routers", ["app.models"])
