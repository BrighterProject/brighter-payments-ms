from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.crud import bank_transfer_crud, owner_bank_account_crud
from app.deps import (
    BookingsClient,
    CurrentUser,
    _get_system_admin,
    get_bookings_client,
    get_current_user,
)
from app.models import BankTransferStatus
from app.schemas import BankTransferRequest, BankTransferResponse
from app.scopes import PaymentScope

router = APIRouter(prefix="/payments/bank-transfer", tags=["bank-transfer"])


@router.get("/", response_model=list[BankTransferResponse])
async def list_bank_transfers(
    transfer_status: BankTransferStatus | None = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BankTransferResponse]:
    """List bank transfer intents. Admins see all; owners see only their own."""
    is_admin = (
        PaymentScope.ADMIN in current_user.scopes
        or PaymentScope.ADMIN_READ in current_user.scopes
    )
    results = await bank_transfer_crud.list_by_status(
        status=transfer_status,
        owner_id=None if is_admin else current_user.id,
        page=page,
        page_size=page_size,
    )
    return [BankTransferResponse.model_validate(r) for r in results]


@router.post("/", response_model=BankTransferResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_transfer_intent(
    payload: BankTransferRequest,
    current_user: CurrentUser = Depends(get_current_user),
    bookings_client: BookingsClient = Depends(get_bookings_client),
) -> BankTransferResponse:
    """Create a bank transfer intent; guest pays the owner's personal bank account directly."""
    booking = await bookings_client.get_booking(payload.booking_id, current_user)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if UUID(booking["user_id"]) != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    if booking["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot initiate payment for booking with status '{booking['status']}'.",
        )

    owner_id = UUID(booking["property_owner_id"])
    owner_bank = await owner_bank_account_crud.get_by_owner(owner_id)
    if owner_bank is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Property owner has no bank account configured.",
        )

    intent = await bank_transfer_crud.create_intent(
        booking_id=payload.booking_id,
        user_id=current_user.id,
        property_owner_id=owner_id,
        amount=Decimal(str(booking["total_price"])),
        currency=booking.get("currency", "EUR"),
        bank_iban=owner_bank.iban,
        bank_bic=owner_bank.bic or "",
        bank_name=owner_bank.bank_name or "",
        account_holder=owner_bank.account_holder,
    )
    return BankTransferResponse.model_validate(intent)


@router.get("/{intent_id}", response_model=BankTransferResponse)
async def get_bank_transfer(
    intent_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> BankTransferResponse:
    """Return a single bank transfer intent (guest, owner, or admin)."""
    intent = await bank_transfer_crud.get_by_id(intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank transfer not found.")

    is_admin = (
        PaymentScope.ADMIN in current_user.scopes
        or PaymentScope.ADMIN_READ in current_user.scopes
    )
    if not is_admin and current_user.id not in (intent.user_id, intent.property_owner_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    return BankTransferResponse.model_validate(intent)


@router.post("/{intent_id}/confirm", response_model=BankTransferResponse)
async def confirm_bank_transfer(
    intent_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    bookings_client: BookingsClient = Depends(get_bookings_client),
) -> BankTransferResponse:
    """
    Confirm receipt of a bank transfer — property owner or admin only.
    Also transitions the associated booking to 'confirmed'.
    """
    intent = await bank_transfer_crud.get_by_id(intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank transfer not found.")

    if intent.status != BankTransferStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot confirm a transfer with status '{intent.status}'.",
        )

    is_owner = current_user.id == intent.property_owner_id
    if not (is_owner or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner or admin can confirm.",
        )

    updated = await bank_transfer_crud.confirm_intent(intent_id)
    ok = await bookings_client.confirm_booking(intent.booking_id, _get_system_admin())
    if not ok:
        logger.error(
            "bank_transfer.confirm: could not confirm booking {} after transfer {} confirmed",
            intent.booking_id,
            intent_id,
        )
    return BankTransferResponse.model_validate(updated)


@router.post("/{intent_id}/cancel", response_model=BankTransferResponse)
async def cancel_bank_transfer(
    intent_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    bookings_client: BookingsClient = Depends(get_bookings_client),
) -> BankTransferResponse:
    """
    Cancel a pending bank transfer — property owner or admin only.
    Also cancels the associated booking.
    """
    intent = await bank_transfer_crud.get_by_id(intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank transfer not found.")

    if intent.status != BankTransferStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a transfer with status '{intent.status}'.",
        )

    is_owner = current_user.id == intent.property_owner_id
    if not (is_owner or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner or admin can cancel.",
        )

    updated = await bank_transfer_crud.cancel_intent(intent_id)
    ok = await bookings_client.cancel_booking(intent.booking_id, _get_system_admin())
    if not ok:
        logger.error(
            "bank_transfer.cancel: could not cancel booking {} after transfer {} cancelled",
            intent.booking_id,
            intent_id,
        )
    return BankTransferResponse.model_validate(updated)
