import os

db_url = os.environ.get("DB_URL", "sqlite://:memory:")

bookings_ms_url = os.environ.get("BOOKINGS_MS_URL", "http://localhost:8002")
notifications_ms_url = os.environ.get("NOTIFICATIONS_MS_URL", "http://localhost:8004")
properties_ms_url = os.environ.get("PROPERTIES_MS_URL", "http://localhost:8001")

# Stripe credentials — use test keys locally, live keys in production
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
# Separate signing secret for the Stripe Connect / V2 webhook destination
stripe_connect_webhook_secret = os.environ.get(
    "STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_connect_placeholder"
)

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
    "http://localhost/api/payments/connect/refresh",
)
stripe_connect_settings_url = os.environ.get(
    "STRIPE_CONNECT_SUCCESS_URL",
    "http://localhost/admin/settings/payments",
)

# Platform fee charged on each payment routed to a connected account (percentage)
stripe_platform_fee_percent = float(
    os.environ.get("STRIPE_PLATFORM_FEE_PERCENT", "10.0")
)

users_ms_url = os.environ.get("USERS_MS_URL", "http://localhost:8000")
internal_api_key = os.environ.get("INTERNAL_API_KEY", "")

# Stripe processing fee passed to customer on card payments
stripe_processing_fee_pct = float(os.environ.get("STRIPE_PROCESSING_FEE_PCT", "1.5"))
stripe_processing_fee_fixed_eur_cents = int(
    os.environ.get("STRIPE_PROCESSING_FEE_FIXED_EUR_CENTS", "25")
)

# Subscription checkout return URLs
stripe_subscription_success_url = os.environ.get(
    "STRIPE_SUBSCRIPTION_SUCCESS_URL",
    "http://localhost/en/owner/subscription?status=success",
)
stripe_subscription_cancel_url = os.environ.get(
    "STRIPE_SUBSCRIPTION_CANCEL_URL",
    "http://localhost/en/owner/subscription?status=cancelled",
)
stripe_portal_return_url = os.environ.get(
    "STRIPE_PORTAL_RETURN_URL",
    "http://localhost/en/owner/subscription",
)
