from __future__ import annotations

from uuid import UUID

from app.models import OwnerStripeAccount


class ConnectCRUD:
    async def get_by_owner(self, owner_id: UUID) -> OwnerStripeAccount | None:
        return await OwnerStripeAccount.get_or_none(owner_id=owner_id)

    async def upsert(
        self,
        owner_id: UUID,
        stripe_account_id: str,
        *,
        verified: bool,
    ) -> OwnerStripeAccount:
        existing = await OwnerStripeAccount.get_or_none(owner_id=owner_id)
        if existing is not None:
            existing.stripe_account_id = stripe_account_id
            existing.verified = verified
            await existing.save(update_fields=["stripe_account_id", "verified"])
            return existing
        return await OwnerStripeAccount.create(
            owner_id=owner_id,
            stripe_account_id=stripe_account_id,
            verified=verified,
        )

    async def delete_by_owner(self, owner_id: UUID) -> bool:
        deleted = await OwnerStripeAccount.filter(owner_id=owner_id).delete()
        return deleted > 0


connect_crud = ConnectCRUD()
