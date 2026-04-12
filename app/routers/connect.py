from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
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
        requirements_outstanding=account.requirements_outstanding,
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
        stripe_account = stripe_client.v1.accounts.create(params={"type": "express"})
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


# ---------------------------------------------------------------------------
# POST /payments/connect/webhook  (PUBLIC — separate Stripe Connect destination)
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def connect_webhook(
    request: Request,
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> dict:
    """
    Webhook endpoint for the Stripe Connect / V2 event destination.

    This endpoint uses a *separate* signing secret from the standard payments
    webhook so that Connect events are verified against the correct destination.

    Handles:
      - v2.core.account.updated          — sync charges_enabled / verified flag
      - v2.core.account[requirements].updated — flag owners with outstanding
                                               requirements (expired ID, tax info, etc.)

    Security:
      - Must be declared PUBLIC in Traefik (no forwardAuth), same as /payments/webhook.
      - Verification is via parse_thin_event HMAC before any DB writes.
      - Raw request bytes are used for verification — never the parsed body.
    """
    raw_body = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        thin_event = stripe_client.parse_event_notification(
            raw_body, sig_header, settings.stripe_connect_webhook_secret
        )
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc

    print(thin_event.type.startswith("v2.core.account"), thin_event.type)

    if thin_event.type.startswith("v2.core.account"):
        account_id: str = thin_event.related_object.id  # type: ignore

        if thin_event.type == "v2.core.account.updated":
            # Fetch current account state and update charges_enabled / verified.
            account = stripe_client.v1.accounts.retrieve(account_id)
            await connect_crud.update_charges_enabled(
                account_id, bool(account.charges_enabled)
            )

        elif thin_event.type == "v2.core.account[requirements].updated":
            # Retrieve the account to inspect its requirements.
            account = stripe_client.v1.accounts.retrieve(account_id)
            reqs = account.requirements
            has_requirements = bool(
                (reqs and reqs.currently_due) or (reqs and reqs.past_due)
            )
            await connect_crud.update_requirements(account_id, has_requirements)

    return {"received": True}
