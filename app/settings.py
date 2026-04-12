import os

db_url = os.environ.get("DB_URL", "sqlite://:memory:")

bookings_ms_url = os.environ.get("BOOKINGS_MS_URL", "http://localhost:8002")

# Stripe credentials — use test keys locally, live keys in production
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")

# Return URLs after Stripe Checkout — should be your frontend origin
stripe_success_url = os.environ.get(
    "STRIPE_SUCCESS_URL",
    "http://localhost/bookings?payment=success",
)
stripe_cancel_url = os.environ.get(
    "STRIPE_CANCEL_URL",
    "http://localhost/bookings?payment=cancelled",
)

# How long the Stripe Checkout page stays valid before expiring (minutes)
stripe_checkout_expires_minutes = int(
    os.environ.get("STRIPE_CHECKOUT_EXPIRES_MINUTES", "30")
)

stripe_connect_refresh_uri = os.environ.get(
    "STRIPE_CONNECT_REFRESH_URI",
    "http://localhost/payments/connect/onboard",
)
stripe_connect_success_url = os.environ.get(
    "STRIPE_CONNECT_SUCCESS_URL",
    "http://localhost/admin/settings/payments",
)

# Platform fee charged on each payment routed to a connected account (percentage)
stripe_platform_fee_percent = float(
    os.environ.get("STRIPE_PLATFORM_FEE_PERCENT", "10.0")
)
