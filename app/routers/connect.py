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
