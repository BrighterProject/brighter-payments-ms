# brighter-payments-ms

Handles Stripe Checkout sessions, webhooks, and refunds.

**Port:** `8003` | **Prefix:** `/payments`

## Endpoints

| Method | Path | Auth |
|---|---|---|
| `POST` | `/payments/checkout` | `payments:write` |
| `GET` | `/payments` | `payments:read` / admin |
| `GET` | `/payments/{id}` | Same as list |
| `POST` | `/payments/booking/{id}/refund` | Owner / Admin |
| `POST` | `/payments/webhook` | **Public** — Stripe only |

## Payment flow

1. Booking created (PENDING) → frontend calls `/payments/checkout` → Stripe Checkout session
2. Customer pays on Stripe-hosted page
3. Stripe fires `checkout.session.completed` → payment marked PAID
4. Property owner confirms/cancels booking manually

Refund policy: owner cancels → full refund. Customer cancels → no refund.

## Running

```bash
uv run uvicorn main:application --host 0.0.0.0 --port 8003
uv run pytest
```

## Key env vars

| Variable | Default |
|---|---|
| `DB_URL` | `sqlite://:memory:` |
| `BOOKINGS_MS_URL` | `http://localhost:8002` |
| `STRIPE_SECRET_KEY` | `sk_test_placeholder` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_placeholder` |
| `STRIPE_SUCCESS_URL` | `http://localhost/bookings?payment=success` |
| `STRIPE_CANCEL_URL` | `http://localhost/bookings?payment=cancelled` |
| `STRIPE_CHECKOUT_EXPIRES_MINUTES` | `30` |

## Notes

- Auth via Traefik headers — no JWT validation here.
- Webhook endpoint is declared public in Traefik (priority 20); verified via `construct_event`.
- Uses Stripe Python SDK v8+ (`StripeClient` API).
- Tests mock CRUD, `BookingsClient`, and `StripeClient` with `AsyncMock`.
