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
        charges_enabled: bool = False,
    ) -> OwnerStripeAccount:
        existing = await OwnerStripeAccount.get_or_none(owner_id=owner_id)
        if existing is not None:
            existing.stripe_account_id = stripe_account_id
            existing.verified = verified
            existing.charges_enabled = charges_enabled
            await existing.save(update_fields=["stripe_account_id", "verified", "charges_enabled"])
            return existing
        return await OwnerStripeAccount.create(
            owner_id=owner_id,
            stripe_account_id=stripe_account_id,
            verified=verified,
            charges_enabled=charges_enabled,
        )

    async def update_charges_enabled(
        self, stripe_account_id: str, charges_enabled: bool
    ) -> None:
        """Called by the account.updated webhook to flip charges_enabled and verified."""
        await OwnerStripeAccount.filter(stripe_account_id=stripe_account_id).update(
            charges_enabled=charges_enabled,
            verified=charges_enabled,
        )

    async def delete_by_owner(self, owner_id: UUID) -> bool:
        deleted = await OwnerStripeAccount.filter(owner_id=owner_id).delete()
        return deleted > 0


connect_crud = ConnectCRUD()
