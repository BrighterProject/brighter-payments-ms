"""Regression tests for the Stripe Connect (v2) client API version.

The Connect onboarding flow calls the Stripe v2 Core Accounts API
(``/v2/core/accounts``), which is not exposed on the older ``2025-04-30.basil``
train the v1 checkout client is pinned to. Calling it with basil returns
``404 not_found`` ("you must explicitly specify a .preview Stripe-Version"),
crashing ``POST /payments/connect/onboard`` with a 500. The Connect client must
therefore use a v2-capable (dahlia) train.
"""

from __future__ import annotations

from app import settings
from app.deps import get_stripe_client, get_stripe_connect_client

BASIL_VERSION = "2025-04-30.basil"


def _client_version(client: object) -> str:
    """Extract the configured Stripe-Version from a StripeClient."""
    return client._requestor._options.stripe_version  # type: ignore[attr-defined]


def test_connect_client_uses_v2_capable_version() -> None:
    get_stripe_connect_client.cache_clear()
    version = _client_version(get_stripe_connect_client())

    assert version == settings.stripe_connect_api_version
    assert version != BASIL_VERSION
    # The dahlia train is the first to expose /v2/core/accounts.
    assert version.endswith(".dahlia")


def test_v1_client_stays_on_basil() -> None:
    get_stripe_client.cache_clear()
    assert _client_version(get_stripe_client()) == BASIL_VERSION
