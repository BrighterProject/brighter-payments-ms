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
