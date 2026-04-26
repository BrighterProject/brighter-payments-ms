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
        transfers_active: bool = False,
    ) -> OwnerStripeAccount:
        existing = await OwnerStripeAccount.get_or_none(owner_id=owner_id)
        if existing is not None:
            existing.stripe_account_id = stripe_account_id
            existing.verified = verified
            existing.transfers_active = transfers_active
            await existing.save(
                update_fields=["stripe_account_id", "verified", "transfers_active"]
            )
            return existing
        return await OwnerStripeAccount.create(
            owner_id=owner_id,
            stripe_account_id=stripe_account_id,
            verified=verified,
            transfers_active=transfers_active,
        )

    async def update_transfers_active(
        self, stripe_account_id: str, transfers_active: bool
    ) -> None:
        """Called by the v2.core.account.updated webhook to flip transfers_active and verified."""
        await OwnerStripeAccount.filter(stripe_account_id=stripe_account_id).update(
            transfers_active=transfers_active,
            verified=transfers_active,
        )

    async def update_requirements(
        self,
        stripe_account_id: str,
        has_requirements: bool,
        requirements_eventually_due: bool,
    ) -> None:
        """Called by the v2.core.account[requirements].updated webhook.

        Flags owners who have outstanding requirements (expired ID, missing tax info, etc.)
        so the frontend can prompt them to update their information.
        """
        await OwnerStripeAccount.filter(stripe_account_id=stripe_account_id).update(
            requirements_outstanding=has_requirements,
            requirements_eventually_due=requirements_eventually_due,
        )

    async def delete_by_owner(self, owner_id: UUID) -> bool:
        deleted = await OwnerStripeAccount.filter(owner_id=owner_id).delete()
        return deleted > 0


connect_crud = ConnectCRUD()
