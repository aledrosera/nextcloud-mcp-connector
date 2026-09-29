"""Registration of the ChatGPT profile. The logic lives in :mod:`mcp_connector.tools.chatgpt`.

The two tools here are the only ones in this server **without**
``structured_output=False``. That is the documented exception to the schema diet (D-14):
returning a Pydantic model makes mcp 2.x emit the payload twice, as ``structuredContent``
and as JSON text in ``content``, which is exactly what the OpenAI connector reads.

Parameter names are contract and not style. OpenAI's own reference server declares
``search(query)`` and ``fetch(id)``, and a connector that renames either of them is simply
not recognised. ``id`` shadows a builtin, which is why the lint exception below is on the
parameter and nowhere else: inside the package the value travels as ``resource_id``.

The descriptions stay one line each, for the same reason the other thirteen tools have no
output schema: every byte here is paid for in every ``tools/list`` of every session.
"""

from mcp.server.mcpserver import Context

from .. import deps
from ..errors import ToolError
from ..models import FetchResult, SearchHit, SearchResults
from ..tools import chatgpt
from . import READ_ONLY, graceful, mcp


@mcp.tool(annotations=READ_ONLY)
@graceful
async def search(query: str, ctx: Context | None = None) -> SearchResults:
    """Search the user's Nextcloud for files, notes, cards and events."""
    clients = deps.resolve_clients(ctx)
    hits = await chatgpt.search(clients, query)
    return SearchResults(results=[SearchHit(**hit) for hit in hits])


@mcp.tool(annotations=READ_ONLY)
@graceful
async def fetch(id: str, ctx: Context | None = None) -> FetchResult:  # noqa: A002 - OpenAI contract
    """Fetch the full content of one search result by its id."""
    clients = deps.resolve_clients(ctx)
    try:
        owner = deps.resolve_ticket_owner(ctx)
    except ToolError:
        # A deployment without an ExApp owner (stdio, static bearer, the standalone OAuth
        # server) cannot serve a link a code execution environment could later redeem, so a
        # binary file falls back to the old refusal instead of failing every fetch call.
        owner = None
    return FetchResult(**await chatgpt.fetch(clients, id, owner=owner))
