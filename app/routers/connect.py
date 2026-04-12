from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from stripe import StripeClient

from app import settings
from app.crud_connect import connect_crud
from app.deps import CurrentUser, get_current_user, get_stripe_client, require_owner
from app.schemas import ConnectStatusResponse, OnboardResponse

router = APIRouter(prefix="/payments/connect", tags=["stripe-connect"])


@router.get("/status", response_model=ConnectStatusResponse)
async def connect_status(
    current_user: CurrentUser = Depends(require_owner),
) -> ConnectStatusResponse:
    """Return the Stripe Connect status for the authenticated owner."""
    account = await connect_crud.get_by_owner(current_user.id)
    if account is None:
        return ConnectStatusResponse(connected=False, verified=False, stripe_account_id=None)
    return ConnectStatusResponse(
        connected=True,
        verified=account.verified,
        stripe_account_id=account.stripe_account_id,
    )


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_connect(
    current_user: CurrentUser = Depends(require_owner),
) -> OnboardResponse:
    """Generate the Stripe Connect OAuth URL for this owner."""
    from urllib.parse import urlencode

    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.stripe_connect_client_id,
            "scope": "read_write",
            "redirect_uri": settings.stripe_connect_redirect_uri,
            "state": str(current_user.id),
        }
    )
    return OnboardResponse(redirect_url=f"https://connect.stripe.com/oauth/authorize?{params}")


@router.get("/callback")
async def connect_callback(
    code: str,
    state: str,
    current_user: CurrentUser = Depends(get_current_user),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> RedirectResponse:
    """
    Stripe OAuth callback. Stripe redirects the owner's browser here after
    they approve the Connect flow. The `state` param must match the
    authenticated user's ID (CSRF protection).
    """
    if state != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter.",
        )

    oauth_response = stripe.OAuth.token(
        code=code,
        grant_type="authorization_code",
        client_secret=settings.stripe_secret_key,
    )
    stripe_account_id: str = oauth_response.stripe_user_id

    account = stripe_client.v1.accounts.retrieve(stripe_account_id)
    verified = bool(account.details_submitted) and not account.requirements.disabled_reason

    await connect_crud.upsert(current_user.id, stripe_account_id, verified=verified)

    return RedirectResponse(url=settings.stripe_connect_success_url)
