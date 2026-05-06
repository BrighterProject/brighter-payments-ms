from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.crud import bank_transfer_crud, owner_bank_account_crud
from app.deps import BookingsClient, CurrentUser, get_bookings_client, get_current_user
from app.schemas import BankTransferRequest, BankTransferResponse

router = APIRouter(prefix="/payments/bank-transfer", tags=["bank-transfer"])


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


@router.post("/{intent_id}/confirm", response_model=BankTransferResponse)
async def confirm_bank_transfer(
    intent_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> BankTransferResponse:
    """Confirm receipt of a bank transfer — only the property owner or admin may call this."""
    intent = await bank_transfer_crud.get_by_id(intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank transfer not found.")

    is_owner = current_user.id == intent.property_owner_id
    if not (is_owner or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner or admin can confirm.",
        )

    updated = await bank_transfer_crud.confirm_intent(intent_id)
    return BankTransferResponse.model_validate(updated)
