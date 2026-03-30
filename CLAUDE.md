# CLAUDE.md — brighter-payments-ms

FastAPI microservice for Stripe payment processing (part of the BrighterProject platform).

## Package management

Always use `uv`. Never use `pip` directly.

```bash
uv add <package>       # add dependency
uv sync                # install from lockfile
uv run <command>       # run in the venv
```

## Running

```bash
uv run pytest                                                        # run tests
uv run uvicorn main:application --host 0.0.0.0 --port 8003          # dev server
```

## Architecture

### Technology Stack

- **API Framework**: FastAPI with Uvicorn (port 8003)
- **Database**: PostgreSQL with Tortoise ORM and Aerich migrations
- **Payment provider**: Stripe (via `stripe` Python SDK, StripeClient v8+)
- **Testing**: pytest with AsyncMock-based CRUD mocking (no real DB or Stripe in tests)

## Auth architecture — critical

Auth is delegated entirely to Traefik via `forwardAuth`. JWT validation happens at the gateway. This service only reads the headers Traefik injects after a successful check:

| Header          | Type   | Description                        |
|-----------------|--------|------------------------------------|
| `X-User-Id`     | UUID   | Authenticated user's ID            |
| `X-Username`    | string | Authenticated user's username      |
| `X-User-Scopes` | string | Space-separated list of scopes     |

`get_current_user()` in `app/deps.py` reads these headers — it does not validate any token itself. **Do not add JWT validation middleware inside this service.**

## Stripe integration

### Checkout flow

1. Frontend POSTs to `POST /bookings/` on bookings-ms → booking created (PENDING)
2. Frontend POSTs to `POST /payments/checkout` → payments-ms creates Stripe Checkout Session
3. Frontend redirects customer to `checkout_url`
4. Customer completes payment on Stripe-hosted page
5. Stripe fires `checkout.session.completed` webhook → payment marked PAID
6. Property owner sees PENDING booking and confirms/cancels manually

### Refund flow

- When property owner cancels a booking, bookings-ms calls `POST /payments/booking/{id}/refund`
  forwarding the owner's auth headers → full Stripe refund issued
- Customer cancellations do NOT trigger a refund (no-refund policy for customer cancellations)

### Webhook security

- `POST /payments/webhook` is declared PUBLIC in Traefik (no forwardAuth)
- Every event is verified via `stripe_client.construct_event(raw_body, sig_header, secret)`
- Never parse the body before verifying — always use `await request.body()` raw bytes
- `STRIPE_WEBHOOK_SECRET` must match the signing secret in your Stripe Dashboard

### Stripe client

```python
from stripe import StripeClient
client = StripeClient(api_key)        # v8+ API
client.checkout.sessions.create(params={...})
client.refunds.create(params={"payment_intent": pi_id})
event = client.construct_event(raw_body, sig_header, webhook_secret)
```

## Cross-service calls

payments-ms calls bookings-ms via `BookingsClient` in `app/deps.py` using the internal
Docker network (`http://bookings-ms:8002`). It forwards caller headers for normal auth,
or injects system admin headers (`_get_system_admin()`) for webhook-triggered cancellations.

## Project structure

```
app/
  settings.py          # DB_URL, BOOKINGS_MS_URL, STRIPE_* (all env vars)
  models.py            # Tortoise ORM model: Payment + PaymentStatus
  schemas.py           # Pydantic: PaymentResponse, CheckoutRequest, CheckoutResponse
  crud.py              # PaymentCRUD — all DB operations
  deps.py              # Auth deps, BookingsClient, get_stripe_client, scope checkers
  scopes.py            # PaymentScope StrEnum + PAYMENT_SCOPE_DESCRIPTIONS
  routers/
    payments.py        # /payments endpoints
tests/
  conftest.py          # Fixtures: customer_client, owner_client, admin_client, anon_app, client_factory
  factories.py         # make_customer(), make_property_owner(), make_admin(), payment_response(), etc.
  test_payments.py     # Full endpoint test suite
  test_scopes.py       # Scope enum/description tests
```

## Scopes

| Scope                    | Who has it  | Purpose                                 |
|--------------------------|-------------|-----------------------------------------|
| `payments:read`          | Customer    | View own payment history                |
| `admin:payments`         | Admin       | Super-scope                             |
| `admin:payments:read`    | Admin       | Read any payment                        |
| `admin:payments:write`   | Admin       | Modify / refund any payment             |
| `admin:payments:delete`  | Admin       | Hard-delete any payment record          |

## Payment status machine

```
PENDING  → PAID      (checkout.session.completed webhook)
PENDING  → FAILED    (checkout.session.expired webhook)
PAID     → REFUNDED  (refund endpoint or charge.refunded webhook)
```

Terminal states: `FAILED`, `REFUNDED`.

## Environment variables

| Variable                          | Default                                     | Description                                    |
|-----------------------------------|---------------------------------------------|------------------------------------------------|
| `DB_URL`                          | `sqlite://:memory:`                         | Database connection string                     |
| `BOOKINGS_MS_URL`                 | `http://localhost:8002`                     | Bookings microservice base URL                 |
| `STRIPE_SECRET_KEY`               | `sk_test_placeholder`                       | Stripe secret key (test or live)               |
| `STRIPE_WEBHOOK_SECRET`           | `whsec_placeholder`                         | Stripe webhook signing secret                  |
| `STRIPE_SUCCESS_URL`              | `http://localhost/bookings?payment=success` | Frontend URL after successful payment          |
| `STRIPE_CANCEL_URL`               | `http://localhost/bookings?payment=cancelled`| Frontend URL when customer cancels checkout   |
| `STRIPE_CHECKOUT_EXPIRES_MINUTES` | `30`                                        | Minutes until Checkout Session expires         |

> **Gotcha — locale prefix in redirect URLs:** The frontend uses intlayer `prefix-all` mode, so bare `/bookings` redirects will 404. `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` must include the locale prefix (e.g. `http://localhost/en/bookings?payment=success`). payments-ms injects the locale into the return URLs dynamically at checkout creation time using the `Accept-Language` header or a `locale` query param passed by the frontend.

## Testing conventions

- **Mock the CRUD layer** with `AsyncMock` (`patch("app.routers.payments.payment_crud")`)
- **Mock BookingsClient** via `client_factory(..., bookings_client=mock_bc)`
- **Mock StripeClient** via `client_factory(..., stripe_client=mock_sc)`
- Use `anon_app` for real scope/auth dep checks (422 assertions on missing headers)
- Webhook tests: mock `stripe_client.construct_event` to return fake event objects

## Database

- Tests: SQLite in-memory (default, mocked via CRUD patch)
- Production: PostgreSQL (`DB_URL` env var)
- Migrations: Aerich

```bash
uv run aerich migrate --name <description>
uv run aerich upgrade
```
