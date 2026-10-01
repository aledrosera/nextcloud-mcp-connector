"""The live half of the provider freeze (review WR-02 of phase 28, the D-28-04 pattern).

The search providers of the live instance are listed as the test user sees them, and every
id that ``provider_classes`` does not know fails the run: an app that brings a provider
naming files in its own way turns this red instead of passing ``unified_search`` unscreened.
"""

import canary_world as cw
import httpx
import pytest
from provider_classes import provider_findings

from mcp_connector.nextcloud.clients import ocs

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_every_live_search_provider_is_classified() -> None:
    env = cw.live_env()
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        listed = await ocs.list_search_providers(client, cw.credentials(env))
    installed = sorted(str(item.get("id")) for item in listed if item.get("id"))
    print(f"# providers={installed}")
    assert installed, "the instance lists no search provider at all"
    findings = provider_findings(installed)
    assert findings == [], "\n".join(findings)
