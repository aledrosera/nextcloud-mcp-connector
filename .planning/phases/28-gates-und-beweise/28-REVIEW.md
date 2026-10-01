---
phase: 28-gates-und-beweise
reviewed: 2026-09-30T18:31:39Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - src/mcp_connector/tools/chatgpt.py
  - src/mcp_connector/tools/files.py
  - src/mcp_connector/tools/notes.py
  - src/mcp_connector/tools/search.py
  - src/mcp_connector/tools/tables.py
  - src/mcp_connector/tools/talk.py
  - .github/workflows/ci.yml
  - tests/contract/result_shapes.py
  - tests/contract/tool_classes.py
  - tests/contract/test_no_destructive_calls.py
  - tests/contract/test_result_shapes.py
  - tests/contract/test_tool_classes.py
  - tests/integration/canary_world.py
  - tests/integration/test_canary.py
  - tests/integration/test_canary_world.py
  - tests/integration/test_exclusion_live.py
  - tests/integration/test_live_questions_28.py
  - tests/integration/test_pair_equality_live.py
  - tests/unit/guard_routes.py
  - tests/unit/test_guard_routes.py
  - tests/unit/test_fetch_exclusion.py
  - tests/unit/test_fetch_message_exclusion.py
  - tests/unit/test_files_exclusion.py
  - tests/unit/test_files_upload_exclusion.py
  - tests/unit/test_notes_exclusion.py
  - tests/unit/test_search_exclusion.py
  - tests/unit/test_tables_exclusion.py
  - tests/unit/test_talk_exclusion.py
  - tests/unit/test_pair_equality_apps.py
  - tests/unit/test_pair_equality_files.py
findings:
  critical: 1
  warning: 6
  info: 3
  total: 10
status: issues_found
---

# Phase 28: Code Review Report

**Reviewed:** 2026-09-30T18:31:39Z
**Depth:** standard
**Files Reviewed:** 30 (plus the helper modules they import: `tools/withhold.py`, `nextcloud/exclusion.py`, `provider_map.py`, `clients/dav.py`, `clients/talk.py`)
**Status:** issues_found

## Summary

Reviewed the six `src/` fixes of phase 28 (D-28-14 Tables link cells, D-28-15 Talk outage, D-28-17 neighbour error order, D-28-19 files_search root, D-28-21 talk-conversations) plus the gate tests (GATE-01 freeze, GATE-02 canary, GATE-03 pairs, EXCL-07 AST needles) and the CI wiring.

The individual fixes are mostly correct and fail-closed. The main problem is the same class of leak that D-28-21 fixed, still open next door: the Talk message providers name the file conversation, and so the tagged file, in every hit title. They are kept unscreened in every state, and the canary world never builds the case that would show it. So a green GATE-02 does not prove "no tool answer shows anything tagged". The reason is a fail-open classification of search providers.

Other findings:
- `files_search` breaks the D-28-17 error-order rule that the same phase put into `fetch(file:)` and `notes_read`.
- The CI step can go green by skipping.
- The canary's write refusals can pass for the wrong reason.

## Fix Status

Fixed on 2026-09-30 by gsd-code-fixer, one commit per finding, local only (not pushed). Every commit passed `ruff check`, `ruff format --check`, pyright (latest), vulture and `pytest tests/unit tests/contract` (5100 passed, 33 skipped at the last commit); `tests/integration` still collects. The live gates (canary, pairs, provider freeze) were not run here, they need Docker and a Nextcloud.

| Finding | Status | Commit | Regression test |
|---------|--------|--------|-----------------|
| CR-01 | fixed | `1f9da6b` | `tests/unit/test_search_exclusion.py` (message in a tagged file room, unverifiable, failing room list); canary world posts a stem message into the file room |
| WR-01 | fixed | `e3da1de` | `test_files_search_answers_a_failing_search_alike` (500, 503, timeout) |
| WR-02 | fixed (gate only, owner decision open) | `338aa66` | `tests/contract/test_provider_classes.py`, live gate `tests/integration/test_provider_classes_live.py` |
| WR-03 | fixed | `097434c` | `tests/unit/test_tables_exclusion.py` (other providers with `/f/<id>`, conversation links) |
| WR-04 | fixed (NC version question open) | `51e6a4d` | `tests/unit/test_live_requirement.py` |
| WR-05 | fixed | `4675bdb` | `tests/unit/test_canary_refusals.py` |
| WR-06 | fixed | `36c08cf` | counter proofs in `tests/contract/test_no_destructive_calls.py` |
| IN-01..03 | not in scope | - | - |

Open owner decisions:
- **WR-02:** the runtime default stays fail-open (a provider without a readable file reference is kept). Inverting it withholds whole providers from users while anything is tagged, which is visible behaviour. Implemented instead: a provider freeze analogous to GATE-01 (every known provider has one class and a reason, the room class must equal what `search` screens) plus a live gate in the canary CI step that fails on every unclassified provider of the instance. Residual risk: a third-party provider on a user's instance that names files its own way still passes; the gate only sees the CI instance.
- **WR-04:** the CI step runs against the NC 34 topology of `compose.exapp.yml`, while every live proof so far was measured on nc35. Whether the gate step should target nc35 (or both) is an owner decision and was not changed. The first CI run of the step remains a required acceptance item before GATE-02/03 count as done.
- **WR-03 (note):** free text cells that contain a `/f/<id>` address stay untouched, as D-28-18 decided; only link objects are screened. Conversation link cells are all withheld in the `unverifiable` state and when the conversation list cannot be read, also those of plain rooms (fail-closed). Candidate for the phase 29 residual list.
- **CR-01 (note):** the conversation list is now also read when a search returns Talk message hits and something is tagged, one GET more in that case.

## Critical Issues

### CR-01: Talk message hits from a file conversation carry the tagged file name, unscreened in every state

**Status:** fixed in `1f9da6b`

**File:** `src/mcp_connector/tools/search.py:92`, `src/mcp_connector/tools/search.py:311-313`, `src/mcp_connector/tools/search.py:342-394`
**Issue:** `_FILE_SHARE_PROVIDERS = ("talk-message", "talk-message-current")` are kept unconditionally with `file_bearing=False`, in `untagged`, `active` and `unverifiable`. The comment above the constant documents the hit title as `"<actor> in <conversation>"`. Measurement 27-05 established that a file conversation's display name is the file name (`NAME_IST_DATEINAME=ja`). The 27-03 probe only tested a file *shared into* an ordinary room. It never tested a message *written in* the file conversation, which is what the Files sidebar chat produces.

`_screen_conversations` (D-28-21) screens only `talk-conversations` and leaves the message providers alone.

Failure scenario:
1. alice has the file `Gehaltsliste-2026.xlsx`, tagged `kein-ki`.
2. Someone writes "bitte prüfen" in its sidebar chat.
3. `unified_search("prüfen")`, `search("prüfen")` or `prepare_context("prüfen")` returns a `talk-message` hit titled `"bob in Gehaltsliste-2026.xlsx"` with `resourceUrl /call/<file_token>#message_<id>`.
4. The same happens in the outage state, where the family promises to withhold everything that could name a file.

GATE-02 cannot see this. `canary_world._build_talk` (`tests/integration/canary_world.py:981-1016`) creates the file conversation but never posts a message into it, so the stem search finds no message hit there.

**Fix:** Screen both message providers with the same room rule as `talk-conversations`. Read the token from `/call/<token>` (the `provider_map._message_target` cross-check already parses it) and decide it against `get_rooms` + `talk_tools.room_fileid` + `file_screen`. Withhold file rooms in `unverifiable`. Add a message containing the stem to the file room in the canary world, before tagging.
```python
_ROOM_SCREENED_PROVIDERS = ("talk-conversations", "talk-message", "talk-message-current")

async def _screen_conversations(...):
    parts = [part for provider_id, part in screened if provider_id in _ROOM_SCREENED_PROVIDERS]
    ...  # unchanged; _conversation_token already reads /call/<token> and ignores the #fragment
```
```python
# canary_world._build_talk, after the file room is listed:
harness.ocs_post(f"{TALK_CHAT}/{file_token}", {"message": f"{world.stamm} datei-raum-nachricht"})
```

## Warnings

### WR-01: files_search decides the tag before the SEARCH error, so tagged and invented roots differ during a SEARCH failure (breaks D-28-17)

**Status:** fixed in `e3da1de`

**File:** `src/mcp_connector/tools/files.py:168-173`
**Issue:** The D-28-19 check `if tags.excludes(path=target_folder): raise dav.not_found(search_scope)` runs *before* `if isinstance(first, BaseException): raise first`. The comment calls this ordering intentional ("before the SEARCH outcome is read"). If the SEARCH fails with 5xx, a timeout or 423:
- A tagged root answers `File not found: /files/<user>/<folder>`.
- An invented or ordinary root answers with the transport error.

An outage of the neighbour request therefore tells tagged apart from missing. This is exactly the defect D-28-17 fixed in `fetch(file:)` and `notes_read` in the same phase, and `_visible_stat` documents the correct order. `test_files_search_answers_a_tagged_folder_like_an_invented_one` (`tests/unit/test_pair_equality_files.py:437`) only mocks 207 and 404, never 5xx. The files_search counterpart of `test_fetch_file_answers_a_failing_lookup_alike` is missing.
**Fix:** Swap the two steps and add a 5xx pair case:
```python
if isinstance(first, BaseException):
    raise first
if tags.excludes(path=target_folder):
    raise dav.not_found(search_scope)
```
Swapping is safe: an invented root always yields a 404 from SEARCH itself, and a tagged root exists, so it reaches the tag step with a 207.

### WR-02: Search-provider classification is fail-open, so unknown file-bearing providers pass unscreened

**Status:** fixed in `338aa66` (see Fix Status for the open owner decision)

**File:** `src/mcp_connector/tools/withhold.py:103-105` (used by `search.py:311`)
**Issue:** A provider hit counts as file-bearing only if it has `attributes.fileId`, `attributes.path` or a `/f/<id>` URL. Every other provider is kept in all states, including `unverifiable`. `talk-conversations` (D-28-21) was only found because the canary instance happened to have Talk. CR-01 is a second instance of the same class. Any provider that names files through its own URL scheme passes the same way (for example Collectives pages, which are files, or third-party apps). GATE-01 freezes the *tool* registry but there is no equivalent freeze for the *provider* registry, so a newly installed app gets no gate.
**Fix:** Invert the default. Keep an explicit allowlist of providers proven to name no file (for example `calendar`, `contacts`, `deck`, `mail`, `settings`, `tables`), and treat any other provider without a readable file reference as file-bearing: withheld while anything is tagged, withheld in `unverifiable`. Add a live gate that lists `ocs.list_search_providers` on the canary instance and fails on an unclassified provider (the D-28-04 pattern).

### WR-03: Tables link cells of other providers and non-JSON link values bypass the screen

**Status:** fixed in `097434c`

**File:** `src/mcp_connector/tools/tables.py:513-537`
**Issue:** `_linked_fileid` returns `None` (not a file link) for:
- any `providerId` other than `"files"`
- any cell that is not a JSON object string

Three cases a user can produce through the normal Tables link picker:
- A `talk-conversations` link to the file conversation of a tagged file stores the file name as `title`, the case D-28-21 proved.
- A `url` link pasted as `https://host/f/<tagged id>`.
- A `fulltextsearch`/`comments` link whose value carries `/f/<id>`.

All three render the tagged file's name or id in `tables_browse` and `fetch(table:)`. D-28-18 covered only the measured `files` form ("andere providerIds unberührt"). That decision was taken before D-28-21 showed that another provider names files.
**Fix:** At minimum, treat any link object whose `value` carries a `/f/<digits>` segment as a file link, whatever its `providerId`. Also screen `talk-conversations` link values through the room rule, or withhold them while anything is tagged. Record the residual risk in phase 29 if the owner keeps the narrow form.

### WR-04: The CI step goes green when every live test skips

**Status:** fixed in `51e6a4d` (see Fix Status for the open owner decision)

**File:** `.github/workflows/ci.yml:129-139`, `tests/integration/canary_world.py:140-166`, `:1131-1132`
**Issue:** `live_env()` and `canary_world()` call `pytest.skip` in four cases:
- a required variable is missing
- `docker` is not on PATH
- `topology.NC_CONTAINER` is not running
- `NC_MCP_TEST_USER2` is empty

The step runs plain `pytest ... -m integration -s`, so a renamed container, a changed `.env.exapp` or a compose project rename turns GATE-02 and GATE-03 into 9 skips and a green check. The step has also never run (push pending). It targets the NC 34 topology of `compose.exapp.yml`, while every live proof so far was measured on nc35.
**Fix:** Make skipping fatal in CI, for example `env: NC_MCP_REQUIRE_LIVE: "1"`, with `live_env()` raising instead of skipping when that variable is set. Or run with `--junitxml=canary.xml` and fail on `skipped>0`. Treat the first CI run as a required acceptance item before calling GATE-02/03 done.

### WR-05: Canary write refusals pass for any error; the switches are not neutralised

**Status:** fixed in `4675bdb`

**File:** `tests/integration/test_canary.py:305-313`, `:419-450`
**Issue:** `ABWEISUNG` only asserts `all(r.is_error for r in pages)`. `talk_send` refused because `NC_MCP_TALK_SEND` switched the channel off, `files_upload` failing on a 5xx, or `notes_create` failing because the Notes app is missing all count as a correct refusal. Unlike `test_pair_equality_live.py:414-415`, the canary never calls `monkeypatch.delenv("NC_MCP_TALK_SEND")` or `delenv("NC_MCP_FILES_ROOT")`, so an environment with either set runs a different code path than the one the gate claims to prove.
**Fix:** Call `delenv` for both variables in both canary tests. In the normal mode, assert the refusal wording: `_unknown_token` for `talk_send`, `parent_missing` for `files_upload` and `notes_create`. That is the D-27-01 "does not exist" sentence and not just any error.

### WR-06: EXCL-07 method scan misses build_request plus send

**Status:** fixed in `36c08cf`

**File:** `tests/contract/test_no_destructive_calls.py:215`, `tag_writes` / `systemtags_module_writes`
**Issue:** `CALL_ATTRS` lacks `build_request`. `req = client.build_request("POST", f"{base}{TAGS_PATH}")` followed by `await client.send(req)` escapes both AST rules:
- `send(req)` names no tag target.
- `build_request` is never inspected.

The line needles cover only `systemtags-relations`, `tag:files` and the legacy Files route, not a POST, PUT or DELETE on `/systemtags/<id>`. Nothing uses this form today, but the gate claims to catch "every call on the tag collection".
**Fix:** Add `build_request` to `CALL_ATTRS` and add a counter proof that injects the two-line `build_request`/`send` form into `systemtags.py`.

## Info

### IN-01: Stale or wrong line anchors in the classification table

**File:** `tests/contract/tool_classes.py:102-105` (also `:58-61`)
**Issue:** The reason for `tables_create_row` cites `tools/tables.py:411-422`, which is the `degraded` line of `_rows`. `create_row` is at `tables.py:141-197`. The freeze checks length and full stop but never checks the anchors, so they drift silently. `tables.py` already grew by about 140 lines in this phase.
**Fix:** Correct the anchor. Optionally make `freeze_findings` check that each `file:line` exists and the file has that many lines.

### IN-02: Talk file-conversation existence shows through a failing path lookup

**File:** `src/mcp_connector/tools/talk.py:849-863`
**Issue:** In the `active` state with a tagged folder, a listed file conversation runs `file_screen` → `dav.paths_of_fileids`. If that lookup fails, the answer is `unavailable_error()`, while an invented token in the same state answers `_unknown_token`. During a DAV SEARCH failure, a caller can therefore tell that a token is a file conversation, even for a tagged file. This is a narrow neighbour-failure oracle of the D-28-17 kind.
**Fix:** Either document it for phase 29, or on a lookup failure also answer an unlisted token with `unavailable_error()` (the same shape as D-28-15).

### IN-03: Token key normalisation differs between one_room and _screen_conversations

**File:** `src/mcp_connector/tools/search.py:375-378`
**Issue:** `by_token` uses `str(room.get("token") or "")` without `.strip()`, while `talk.one_room` strips. The effect is fail-closed (an unmatched token becomes `"-"` and is withheld), but two spellings of the same rule invite drift.
**Fix:** Use one helper for "token of a room" in both places.

---

_Reviewed: 2026-09-30T18:31:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

## Owner decisions (2026-09-30)

- **WR-02:** the runtime default stays fail-open, as implemented. The residual risk (third-party search providers that name files without a file id, path or `/f/` link are not screened) is named in the phase 29 documentation. A strict admin option is a later candidate, off by default.
- **WR-04:** the canary and pair proofs move to NC 35 only, not to both versions. NC 34 stays covered by the other integration steps. Implemented as a follow-up task (CI job on the official `nextcloud:35.0.1-apache` image), because the `compose.exapp.yml` topology is pinned to 34.0.3 for EXAPP-06.
- **WR-03 note and IN-02:** free text cells with a `/f/<id>` address and the file-room oracle of IN-02 go to the phase 29 residual list and are named as limits in the documentation.
