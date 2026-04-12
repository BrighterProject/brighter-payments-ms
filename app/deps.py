from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import quote, unquote
from uuid import UUID

import httpx
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from stripe import StripeClient

from app import settings
from app.scopes import PAYMENT_SCOPE_DESCRIPTIONS, PaymentScope

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.bookings_ms_url}/auth/token",
    scopes={**PAYMENT_SCOPE_DESCRIPTIONS},
)

# ---------------------------------------------------------------------------
# Synthetic identity used for internal service-to-service calls
# (payments-ms → bookings-ms to cancel an unpaid booking)
# ---------------------------------------------------------------------------

_SYSTEM_ADMIN = None  # populated lazily to avoid circular import at module load


def _get_system_admin() -> "CurrentUser":
    global _SYSTEM_ADMIN
    if _SYSTEM_ADMIN is None:
        _SYSTEM_ADMIN = CurrentUser(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            username="payments-ms",
            scopes=["admin:bookings:write", "admin:scopes"],
        )
    return _SYSTEM_ADMIN


# ---------------------------------------------------------------------------
# Auth — reads Traefik-injected headers
# ---------------------------------------------------------------------------


@dataclass
class CurrentUser:
    id: UUID
    username: str
    scopes: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "admin:scopes" in self.scopes


def get_current_user(
    x_user_id: str = Header(...),
    x_username: str = Header(...),
    x_user_scopes: str = Header(default=""),
) -> CurrentUser:
    """
    Reads headers injected by Traefik after forwardAuth validation.
    JWT has already been verified at the gateway — never validate it here.
    """
    try:
        user_id = UUID(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity from gateway",
        ) from None

    scopes = x_user_scopes.split(" ") if x_user_scopes else []
    return CurrentUser(id=user_id, username=unquote(x_username), scopes=scopes)


def require_scopes(*required: str):
    """Factory that returns a scope-enforcing dependency."""

    async def _dep(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing = [s for s in required if s not in current_user.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scopes: {', '.join(missing)}",
            )
        return current_user

    return _dep


# Pre-built scope dependencies
can_read_payment = require_scopes(PaymentScope.READ)
can_admin_delete_payment = require_scopes(PaymentScope.ADMIN_DELETE)


def require_owner(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Allow only property owners (bookings:manage scope) and admins."""
    if "bookings:manage" not in current_user.scopes and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Property owner access required.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Stripe client — singleton, never re-created between requests
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_stripe_client() -> StripeClient:
    """
    Returns a cached Stripe client initialised with the secret key from settings.
    Override via app.dependency_overrides[get_stripe_client] in tests.
    """
    return StripeClient(settings.stripe_secret_key)


# ---------------------------------------------------------------------------
# BookingsClient — thin async wrapper around bookings-ms internal API
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_bookings_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.bookings_ms_url,
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


class BookingsClient:
    """
    Thin async wrapper around the bookings-ms internal API.
    Forwards caller headers so bookings-ms auth deps work normally.
    """

    @property
    def _client(self) -> httpx.AsyncClient:
        return _get_bookings_http_client()

    def _headers(self, user: CurrentUser) -> dict[str, str]:
        return {
            "X-User-Id": str(user.id),
            "X-Username": quote(user.username),
            "X-User-Scopes": " ".join(user.scopes),
        }

    async def get_booking(self, booking_id: UUID, user: CurrentUser) -> dict | None:
        """Return booking dict or None on 404. Raises HTTPException on 5xx."""
        resp = await self._client.get(
            f"/bookings/{booking_id}", headers=self._headers(user)
        )
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"bookings-ms returned {resp.status_code}",
            )
        return resp.json()

    async def cancel_booking(self, booking_id: UUID, caller: CurrentUser) -> bool:
        """
        Cancel a booking by ID.
        Used by the webhook handler when a Checkout Session expires.
        Caller should be _get_system_admin() so bookings-ms grants admin access.
        Silently returns False on any error — the webhook must not fail.
        """
        try:
            resp = await self._client.patch(
                f"/bookings/{booking_id}/status",
                json={"status": "cancelled"},
                headers=self._headers(caller),
            )
            return resp.status_code < 400
        except (httpx.RequestError, Exception):
            return False


_bookings_client = BookingsClient()


def get_bookings_client() -> BookingsClient:
    return _bookings_client
