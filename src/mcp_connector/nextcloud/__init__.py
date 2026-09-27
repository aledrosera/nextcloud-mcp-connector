"""Nextcloud client layer: credentials, HTTP pool and one module per API family.

``NcClients`` is the single parameter object every tool function receives. It is the seam
where phase 2 hooks in the AppAPI impersonation without touching tool code.
"""

from dataclasses import dataclass, field

import httpx

from .credentials import Credentials
from .exclusion import ExclusionGuard

__all__ = ["Credentials", "NcClients"]


@dataclass(frozen=True, slots=True)
class NcClients:
    """The HTTP client of the current event loop plus the credentials of this call.

    ``exclusion`` is the ``kein-ki`` guard of this call. Every construction gets a fresh
    one, and the bundle is built once per tool call, so the tagged set never outlives the
    call (E3) while every part of one answer shares a single flight.
    """

    client: httpx.AsyncClient
    creds: Credentials
    # one guard per tool call (E3); compare/repr off so equality of two bundles stays what it was
    exclusion: ExclusionGuard = field(default_factory=ExclusionGuard, compare=False, repr=False)
