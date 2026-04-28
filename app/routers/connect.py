from __future__ import annotations

import contextlib
from typing import Any, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic_extra_types.country import CountryAlpha2
from starlette.responses import RedirectResponse
from stripe import StripeClient

from app import settings
from app.crud_connect import connect_crud
from app.deps import CurrentUser, get_stripe_client, require_owner
from app.schemas import ConnectStatusResponse, OnboardResponse, UpdateResponse

router = APIRouter(prefix="/payments-connect", tags=["stripe-connect"])


def _requirements_summary(requirements: Any) -> tuple[bool, bool]:
    """
    Returns (has_currently_or_past_due, has_eventually_due).
    Scans v2 requirements entries by minimum_deadline.status.
    """
    if requirements is None:
        return False, False

    currently_due = False
    eventually_due = False

    entries = getattr(requirements, "entries", None) or []
    for entry in entries:
        minimum_deadline = getattr(entry, "minimum_deadline", None)
        status_value = getattr(minimum_deadline, "status", None)
        if status_value in {"currently_due", "past_due"}:
            currently_due = True
        elif status_value == "eventually_due":
            eventually_due = True

    # Also check the summary for a quick short-circuit
    summary = getattr(requirements, "summary", None)
    minimum_deadline = getattr(summary, "minimum_deadline", None)
    summary_status = getattr(minimum_deadline, "status", None)
    if summary_status in {"currently_due", "past_due"}:
        currently_due = True
    elif summary_status == "eventually_due":
        eventually_due = True

    return currently_due, eventually_due


def _recipient_transfers_active(account: Any) -> bool:
    configuration = getattr(account, "configuration", None)
    recipient = getattr(configuration, "recipient", None)
    capabilities = getattr(recipient, "capabilities", None)
    stripe_transfers = getattr(capabilities, "stripe_balance", None)
    stripe_transfers = getattr(stripe_transfers, "stripe_transfers", None)
    return getattr(stripe_transfers, "status", None) == "active"


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
            transfers_active=False,
            stripe_account_id=None,
        )

    return ConnectStatusResponse(
        connected=True,
        verified=account.verified,
        transfers_active=account.transfers_active,
        stripe_account_id=account.stripe_account_id,
        requirements_outstanding=account.requirements_outstanding,
        requirements_eventually_due=account.requirements_eventually_due,
    )


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_connect(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
    entity_type: Literal[
        "company", "government_entity", "individual", "non_profit"
    ] = "individual",
    country: CountryAlpha2 = CountryAlpha2("BG"),
    upfront: bool = False,  # whether to collect eventually_due
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
                "identity": {
                    "country": country,
                    "entity_type": entity_type,
                },
                "contact_email": current_user.username,
                "defaults": {
                    "responsibilities": {
                        "fees_collector": "application",
                        "losses_collector": "application",
                    }
                },
                "configuration": {
                    "recipient": {
                        "capabilities": {
                            "stripe_balance": {"stripe_transfers": {"requested": True}}
                        }
                    },
                },
                "dashboard": "express",
            }
        )
        stripe_account_id = stripe_account.id
        await connect_crud.upsert(
            current_user.id,
            stripe_account_id,
            verified=False,
            transfers_active=False,
        )
    else:
        stripe_account_id = account.stripe_account_id

    fields = "eventually_due" if upfront else "currently_due"

    account_link = stripe_client.v2.core.account_links.create(
        {
            "account": stripe_account_id,
            "use_case": {
                "type": "account_onboarding",
                "account_onboarding": {
                    "collection_options": {"fields": fields},
                    "return_url": settings.stripe_connect_settings_url,
                    "refresh_url": settings.stripe_connect_refresh_uri,
                    "configurations": ["recipient"],
                },
            },
        }
    )
    return OnboardResponse(redirect_url=account_link.url)


@router.get("/refresh")
async def refresh_stripe_onboarding(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
):
    account = await connect_crud.get_by_owner(current_user.id)

    if not account:
        return RedirectResponse(
            url=settings.stripe_connect_settings_url, status_code=303
        )

    account_link = stripe_client.v2.core.account_links.create(
        {
            "account": account.stripe_account_id,
            "use_case": {
                "type": "account_onboarding",
                "account_onboarding": {
                    "return_url": settings.stripe_connect_settings_url,
                    "refresh_url": settings.stripe_connect_refresh_uri,
                    "configurations": ["recipient"],
                },
            },
        }
    )

    return RedirectResponse(url=account_link.url, status_code=303)


@router.get("/update")
async def update_stripe_account(
    current_user: CurrentUser = Depends(require_owner),
    stripe_client: StripeClient = Depends(get_stripe_client),
):
    account = await connect_crud.get_by_owner(current_user.id)

    if not account:
        return UpdateResponse(redirect_url=settings.stripe_connect_settings_url)

    account_link = stripe_client.v2.core.account_links.create(
        {
            "account": account.stripe_account_id,
            "use_case": {
                "type": "account_update",
                "account_update": {
                    "collection_options": {"fields": "currently_due"},
                    "return_url": settings.stripe_connect_settings_url,
                    "refresh_url": settings.stripe_connect_refresh_uri,
                    "configurations": ["recipient"],
                },
            },
        }
    )

    return UpdateResponse(redirect_url=account_link.url)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
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
            params={"include": ["requirements", "configuration.recipient"]},
        )

        transfers_active = _recipient_transfers_active(account)
        requirements_outstanding, requirements_eventually_due = _requirements_summary(
            getattr(account, "requirements", None)
        )

        await connect_crud.update_transfers_active(account_id, transfers_active)
        await connect_crud.update_requirements(
            account_id,
            requirements_outstanding,
            requirements_eventually_due,
        )

    return {"received": True}
