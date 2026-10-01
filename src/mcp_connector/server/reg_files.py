"""Registration of the file tools. The logic lives in :mod:`mcp_connector.tools.files`.

No tool takes a user name: the identity comes from the auth channel through
``deps.resolve_clients`` only (threat T-01-12, confused deputy).
"""

from typing import Annotated, Any

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..downloads import issue, upload
from ..tools import files as files_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp

#: Largest tool answer claude.ai and Claude Desktop accept (Anthropic connector docs).
TOOL_RESULT_CHAR_LIMIT = 150_000
_SMALLEST_CHUNK = 4 * 1024


async def read_within_budget(clients: Any, path: str, offset: int) -> str:
    """Read one slice and shrink it until the serialised answer fits the client limit."""
    budget = files_tools.DEFAULT_MAX_BYTES
    text = compact(await files_tools.read(clients, path=path, offset=offset, max_bytes=budget))
    while len(text) > TOOL_RESULT_CHAR_LIMIT and budget > _SMALLEST_CHUNK:
        budget //= 2
        text = compact(await files_tools.read(clients, path=path, offset=offset, max_bytes=budget))
    return text


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_search(
    query: Annotated[str, Field(description="Part of a file or folder name, e.g. budget")],
    folder: Annotated[str, Field(description="Folder to search in, e.g. /Docs")] = "/",
    limit: Annotated[
        int, Field(ge=1, le=files_tools.MAX_SEARCH_LIMIT, description="Maximum number of hits")
    ] = files_tools.DEFAULT_SEARCH_LIMIT,
    cursor: Annotated[str, Field(description="'next' value of the previous answer")] = "",
    ctx: Context | None = None,
) -> str:
    """Search files and folders by name (matches names, not file contents)."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await files_tools.search(
            clients, query=query, folder=folder, limit=limit, cursor=cursor or None
        )
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_list(
    path: Annotated[str, Field(description="Folder path, e.g. /Docs")] = "/",
    limit: Annotated[
        int, Field(ge=1, le=files_tools.MAX_LIST_LIMIT, description="Maximum number of entries")
    ] = files_tools.DEFAULT_LIST_LIMIT,
    cursor: Annotated[str, Field(description="'next' value of the previous answer")] = "",
    ctx: Context | None = None,
) -> str:
    """List the direct children of a folder."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await files_tools.list_dir(clients, path=path, limit=limit, cursor=cursor or None)
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_read(
    path: Annotated[str, Field(description="Path inside the user's files, e.g. /Docs/notes.md")],
    offset: Annotated[int, Field(ge=0, description="Byte offset for a continued read")] = 0,
    ctx: Context | None = None,
) -> str:
    """Read a text file from Nextcloud; large files come back truncated with a next offset."""
    return await read_within_budget(deps.resolve_clients(ctx), path, offset)


# files_read_as_markdown (upstream 0.4.0, TOOL-14) is deliberately not registered in the
# olivia fork: Office and PDF files go out as a download link (files_download). The code in
# tools/files.py and the documents package stays as upstream ships it, so merges stay cheap.


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_download(
    path: Annotated[str, Field(description="Path of the file, e.g. /Docs/scan.pdf")],
    ctx: Context | None = None,
) -> str:
    """Get a single-use download_url for any file; download it from code execution,
    not web_fetch."""
    clients = deps.resolve_clients(ctx)
    owner = deps.resolve_ticket_owner(ctx)
    return compact(await issue.issue_link(clients, owner, path))


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def files_upload(
    path: Annotated[str, Field(description="New file path; must not exist")],
    content: Annotated[
        str | None,
        Field(description="UTF-8 text to write now; omit to get an upload_url for any file"),
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Create a new file; never overwrites. Text: pass content. Any other file: omit content,
    then PUT it to upload_url from code execution (curl -T)."""
    clients = deps.resolve_clients(ctx)
    if content is None:
        owner = deps.resolve_ticket_owner(ctx)
        return compact(await upload.issue_upload_link(clients, owner, path))
    return compact(await files_tools.upload(clients, path=path, content=content))
