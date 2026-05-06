from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.crud import owner_bank_account_crud
from app.deps import CurrentUser, get_current_user, require_owner
from app.schemas import OwnerBankAccountResponse, OwnerBankAccountUpsert

router = APIRouter(prefix="/payments/bank-account", tags=["bank-account"])


@router.put("/", response_model=OwnerBankAccountResponse)
async def upsert_bank_account(
    payload: OwnerBankAccountUpsert,
    current_user: CurrentUser = Depends(require_owner),
) -> OwnerBankAccountResponse:
    """Create or update the calling owner's bank account details."""
    return await owner_bank_account_crud.upsert(
        owner_id=current_user.id,
        iban=payload.iban,
        account_holder=payload.account_holder,
        bic=payload.bic,
        bank_name=payload.bank_name,
    )


@router.get("/", response_model=OwnerBankAccountResponse)
async def get_my_bank_account(
    current_user: CurrentUser = Depends(require_owner),
) -> OwnerBankAccountResponse:
    """Return the calling owner's bank account details."""
    account = await owner_bank_account_crud.get_by_owner(current_user.id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No bank account configured.")
    return account


@router.get("/{owner_id}", response_model=OwnerBankAccountResponse)
async def get_owner_bank_account(
    owner_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> OwnerBankAccountResponse:
    """Return a specific owner's bank account — admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    account = await owner_bank_account_crud.get_by_owner(owner_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No bank account configured.")
    return account
