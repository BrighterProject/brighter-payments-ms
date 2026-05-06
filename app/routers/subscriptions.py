from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from stripe import StripeClient

from app import settings
from app.crud import subscription_crud
from app.deps import CurrentUser, get_current_user, get_stripe_client, require_scopes
from app.schemas import (
    OwnerSubscriptionResponse,
    PortalResponse,
    SubscriptionCheckoutResponse,
    SubscriptionPlanResponse,
)
from app.scopes import PaymentScope

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/", response_model=list[OwnerSubscriptionResponse])
async def list_all_subscriptions(
    _: CurrentUser = Depends(require_scopes(PaymentScope.ADMIN_READ)),
) -> list[OwnerSubscriptionResponse]:
    subs = await subscription_crud.list_all()
    return [OwnerSubscriptionResponse.model_validate(s) for s in subs]


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def list_plans() -> list[SubscriptionPlanResponse]:
    plans = await subscription_crud.list_plans()
    return [SubscriptionPlanResponse.model_validate(p) for p in plans]


@router.get("/me", response_model=OwnerSubscriptionResponse)
async def get_my_subscription(
    current_user: CurrentUser = Depends(get_current_user),
) -> OwnerSubscriptionResponse:
    sub = await subscription_crud.get_owner_subscription(current_user.id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found.")
    return OwnerSubscriptionResponse.model_validate(sub)


@router.post(
    "/checkout",
    response_model=SubscriptionCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe(
    plan_slug: str,
    current_user: CurrentUser = Depends(get_current_user),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> SubscriptionCheckoutResponse:
    plan = await subscription_crud.get_plan_by_slug(plan_slug)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    if plan.stripe_price_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enterprise plans require manual activation. Please contact us.",
        )

    session = stripe_client.v1.checkout.sessions.create(params={
        "mode": "subscription",
        "line_items": [{"price": plan.stripe_price_id, "quantity": 1}],
        "customer_email": current_user.username,
        "metadata": {"owner_id": str(current_user.id), "plan_slug": plan_slug},
        "client_reference_id": str(current_user.id),
        "success_url": settings.stripe_subscription_success_url + "&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": settings.stripe_subscription_cancel_url,
    })
    return SubscriptionCheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.post("/portal", response_model=PortalResponse)
async def customer_portal(
    current_user: CurrentUser = Depends(get_current_user),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> PortalResponse:
    sub = await subscription_crud.get_owner_subscription(current_user.id)
    if sub is None or sub.stripe_customer_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Stripe customer on record.")
    session = stripe_client.v1.billing_portal.sessions.create(params={
        "customer": sub.stripe_customer_id,
        "return_url": settings.stripe_portal_return_url,
    })
    return PortalResponse(portal_url=session.url)


@router.get("/can-add-listing")
async def can_add_listing(
    owner_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Internal endpoint called by properties-ms to enforce listing quota."""
    if current_user.id != owner_id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    allowed = await subscription_crud.can_add_listing(owner_id)
    return {"allowed": allowed}
