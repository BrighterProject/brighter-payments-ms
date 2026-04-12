from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from stripe import StripeClient

from app import settings
from app.crud_connect import connect_crud
from app.deps import CurrentUser, get_stripe_client, require_owner
from app.schemas import ConnectStatusResponse, OnboardResponse

router = APIRouter(prefix="/payments/connect", tags=["stripe-connect"])


@router.get("/status", response_model=ConnectStatusResponse)
async def connect_status(
    current_user: CurrentUser = Depends(require_owner),
) -> ConnectStatusResponse:
    """Return the Stripe Connect status for the authenticated owner."""
    account = await connect_crud.get_by_owner(current_user.id)
    if account is None:
        return ConnectStatusResponse(
            connected=False,
            verified=False,
            charges_enabled=False,
            stripe_account_id=None,
        )
    return ConnectStatusResponse(
        connected=True,
        verified=account.verified,
        charges_enabled=account.charges_enabled,
        stripe_account_id=account.stripe_account_id,
    )


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_connect(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> OnboardResponse:
    """
    Create (or resume) a Stripe Connect Account Links onboarding session.

    If the owner has no connected account yet, an Express account is created
    first.  A one-time Account Link URL is always freshly generated so that
    expired links can be refreshed by calling this endpoint again.
    """
    account = await connect_crud.get_by_owner(current_user.id)

    if account is None:
        stripe_account = stripe_client.v1.accounts.create(
            params={"type": "express"}
        )
        stripe_account_id = stripe_account.id
        await connect_crud.upsert(
            current_user.id,
            stripe_account_id,
            verified=False,
            charges_enabled=False,
        )
    else:
        stripe_account_id = account.stripe_account_id

    account_link = stripe_client.v1.account_links.create(
        params={
            "account": stripe_account_id,
            "type": "account_onboarding",
            "return_url": settings.stripe_connect_success_url,
            "refresh_url": settings.stripe_connect_refresh_uri,
        }
    )
    return OnboardResponse(redirect_url=account_link.url)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_connect(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> None:
    """
    Delete the owner's Stripe Express account and remove the local record.

    The Stripe account deletion is best-effort — the local record is removed
    regardless of whether Stripe responds with an error.
    """
    account = await connect_crud.get_by_owner(current_user.id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected Stripe account found.",
        )

    try:
        stripe_client.v1.accounts.delete(account.stripe_account_id)
    except Exception:
        pass  # Stripe failure must not block local cleanup

    await connect_crud.delete_by_owner(current_user.id)
