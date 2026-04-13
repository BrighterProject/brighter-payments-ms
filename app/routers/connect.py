from __future__ import annotations

import contextlib
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from stripe import StripeClient

from app import settings
from app.crud_connect import connect_crud
from app.deps import CurrentUser, get_stripe_client, require_owner
from app.schemas import ConnectStatusResponse, OnboardResponse

router = APIRouter(prefix="/payments/connect", tags=["stripe-connect"])


def _has_outstanding_requirements(requirements: Any) -> bool:
    """
    Best-effort v2 requirements check.

    In Accounts v2, requirements are exposed as entries with per-entry deadlines.
    We treat the account as having outstanding requirements when any entry is
    currently_due or past_due.
    """
    if requirements is None:
        return False

    entries = getattr(requirements, "entries", None) or []
    for entry in entries:
        minimum_deadline = getattr(entry, "minimum_deadline", None)
        status_value = getattr(minimum_deadline, "status", None)
        if status_value in {"currently_due", "past_due"}:
            return True

    summary = getattr(requirements, "summary", None)
    minimum_deadline = getattr(summary, "minimum_deadline", None)
    return getattr(minimum_deadline, "status", None) in {"currently_due", "past_due"}


def _merchant_card_payments_active(account: Any) -> bool:
    """
    Merchant capability status in Accounts v2.

    The v2 merchant configuration exposes capability status directly.
    """
    configuration = getattr(account, "configuration", None)
    merchant = getattr(configuration, "merchant", None)
    capabilities = getattr(merchant, "capabilities", None)
    card_payments = getattr(capabilities, "card_payments", None)
    return getattr(card_payments, "status", None) == "active"


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
    Create (or resume) a Stripe Connect onboarding session using Accounts v2.

    If the owner has no connected account yet, create an Accounts v2 merchant
    account first. A fresh Account Link URL is generated every time.
    """
    account = await connect_crud.get_by_owner(current_user.id)

    if account is None:
        stripe_account = stripe_client.v2.core.accounts.create(
            {
                "configuration": {
                    "merchant": {
                        "capabilities": {"card_payments": {"requested": True}},
                    }
                },
                "dashboard": "express",
            }
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

    account_link = stripe_client.v2.core.account_links.create(
        {
            "account": stripe_account_id,
            "use_case": {
                "type": "account_onboarding",
                "account_onboarding": {
                    "return_url": settings.stripe_connect_success_url,
                    "refresh_url": settings.stripe_connect_refresh_uri,
                    "configurations": ["merchant"],
                },
            },
        }
    )
    return OnboardResponse(redirect_url=account_link.url)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_connect(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> None:
    """
    Close the owner's Stripe v2 account and remove the local record.

    The Stripe operation is best-effort — local cleanup always happens.
    """
    account = await connect_crud.get_by_owner(current_user.id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected Stripe account found.",
        )

    with contextlib.suppress(Exception):
        stripe_client.v2.core.accounts.close(account.stripe_account_id)

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
    Webhook endpoint for the Stripe Connect / v2 event destination.

    Handles:
      - v2.core.account.updated
      - v2.core.account[requirements].updated

    Uses parse_event_notification HMAC verification before any DB writes.
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

    if thin_event.type in {
        "v2.core.account.updated",
        "v2.core.account[requirements].updated",
    }:
        account_id: str = thin_event.related_object.id  # type: ignore[assignment]

        # Fetch the latest account state so we always sync from Stripe's source
        # of truth. v2 retrieval supports include for requirement and
        # configuration fields.
        account = stripe_client.v2.core.accounts.retrieve(
            account_id,
            params={"include": ["requirements", "configuration.merchant"]},
        )

        charges_enabled = _merchant_card_payments_active(account)
        requirements_outstanding = _has_outstanding_requirements(
            getattr(account, "requirements", None)
        )

        await connect_crud.update_charges_enabled(account_id, charges_enabled)
        await connect_crud.update_requirements(account_id, requirements_outstanding)

    return {"received": True}
