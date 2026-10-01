<!--
SPDX-FileCopyrightText: 2026 street1983nk
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Dependency audit

**Audited:** 2026-08-14 (slopcheck 0.6.1 against PyPI)
**Last addendum:** 2026-09-19, PyJWT raised to 2.14 for the 2026-09-11 security release (plan 20-01)
**Scope:** all direct dependencies of `nextcloud-mcp-connector` plus the notable transitive ones.
**Owner sign-off:** the package legitimacy gate for the first `uv sync` was approved by the
repository owner on 2026-08-14 after independent verification (see "The httpx2 finding").

## Audit table

| Package | Registry | Age | Downloads | Source repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| mcp | PyPI | 2.0.0 since 2026-07-28, project since 2024 | very high | github.com/modelcontextprotocol/python-sdk | [OK] | Approved (direct) |
| mcp-types | PyPI | 2.0.0, lock-step with mcp | via mcp | github.com/modelcontextprotocol/python-sdk | [OK] | Approved (transitive, never pinned directly) |
| httpx | PyPI | 0.28.1 since 2024-12-06 | very high | github.com/encode/httpx | [OK] | Approved (direct) |
| httpx2 | PyPI | first release 2026-05-11, 2.10.0 on 2026-08-09 | new | github.com/pydantic/httpx2 | [SUS] | Keep transitive, never a direct dependency |
| lxml | PyPI | 6.1.1 since 2026-05-18 | very high | github.com/lxml/lxml | [OK] | Approved (direct) |
| icalendar | PyPI | 7.2.2 since 2026-07-20 | high | github.com/collective/icalendar | [OK] | Approved (direct) |
| vobject | PyPI | 0.9.9 since 2024-12-16 | high | github.com/py-vobject/vobject | [OK] | Approved (direct) |
| pydantic | PyPI | 2.13.4 since 2026-05-06 | very high | github.com/pydantic/pydantic | [OK] | Approved (direct) |
| respx | PyPI | 0.23.1 since 2026-04-08 | high | github.com/lundberg/respx | [OK] | Approved (dev) |
| pytest | PyPI | 9.1.1 | very high | github.com/pytest-dev/pytest | [OK] | Approved (dev) |
| anyio | PyPI | 4.14.2 | very high | github.com/agronholm/anyio | [OK] | Approved (transitive, also the async test plugin) |
| ruff | PyPI | 0.16.3 | very high | github.com/astral-sh/ruff | [OK] | Approved (dev) |
| tzdata | PyPI | 2025.2, IANA data repackaged by the CPython community | very high | github.com/python/tzdata | [OK] | Approved (direct) 2026-08-14, owner sign-off: zoneinfo is used directly and Windows has no system tz database |
| pyright | PyPI | 1.1.411 | very high | github.com/microsoft/pyright | [OK] | Approved (dev) 2026-08-14, owner sign-off for the quality gate |
| nodeenv | PyPI | 1.10.0 | very high | github.com/ekalinin/nodeenv | [OK] | Approved (transitive of pyright, never pinned directly) |
| vulture | PyPI | 2.16 | high | github.com/jendrikseipp/vulture | [OK] | Approved (dev) 2026-08-14, owner sign-off for the quality gate |
| lxml-stubs | PyPI | 0.5.1, official stubs from the lxml org | high | github.com/lxml/lxml-stubs | [OK] | Approved (dev) 2026-08-14, typing support for pyright |
| cryptography | PyPI | 158 releases, 50.0.0 since 2026-07-31 | very high (top 20 on PyPI) | github.com/pyca/cryptography | not runnable here, verified by hand | Approved (direct) 2026-08-16, owner sign-off (see "Promoting cryptography") |
| pyjwt | PyPI | 2.14.0 since 2026-09-11, project since 2011 (56 releases) | very high | github.com/jpadilla/pyjwt | not runnable here, verified by hand | Approved (direct) 2026-09-19, security release raise (see "Raising PyJWT to 2.14") |

Packages removed due to a `[SLOP]` verdict: none.
Packages flagged as suspicious: `httpx2`.

## The httpx2 finding

slopcheck flags `httpx2` with "Suspiciously close to 'httpx'. Could be a typosquat." That signal is
expected for this name. Counter-evidence, verified directly against PyPI and GitHub:

- `mcp` 2.0.0 `requires_dist` contains `httpx2>=2.5.0`, so the dependency is genuinely pulled in by
  the official MCP SDK, not by our own code.
- `httpx2` is published with `author_email: Tom Christie <tom@tomchristie.com>` (the author of
  `httpx`), maintainer `Pydantic Services Inc. <engineering@pydantic.dev>`, homepage and source
  `github.com/pydantic/httpx2` (the real pydantic organisation, 914 stars, not a fork, first
  release 2026-05-11), classifier `Development Status :: 5 - Production/Stable`.
- The official SDK release notes for v2.0.0b2 name the switch explicitly: "httpx is replaced by
  httpx2 (#2972) ... the next-generation httpx fork with SSE support built in".
- `encode/httpx` has been inactive since March 2026, which makes the successor story consistent.

**Consequence for this repository:** `httpx2` is legitimate but young. It stays a transitive
dependency of `mcp` and is never listed in `pyproject.toml`. Our own HTTP code uses `httpx`
(`>=0.28,<0.29`), because `respx` mocks `httpx` and not `httpx2`.

Secondary observation, no action needed in phase 1: `httpx2` verifies TLS against the operating
system trust store (via `truststore`) instead of `certifi`. That becomes relevant only when an
integration test talks to a self-signed Nextcloud certificate; the Docker test setup uses plain
HTTP.

## Promoting cryptography from transitive to direct (2026-08-16, plan 03-02)

Phase 3 stores a Nextcloud app password per authorization, encrypted at rest. The
encryption lives in `src/mcp_connector/oauth/crypto.py` and imports the package directly:

```python
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
```

The policy of this file says a package we import directly is declared directly, so the
entry in `pyproject.toml` is `cryptography>=50,<51`.

**What the promotion changes and what it does not.** Nothing is installed by it. The
package was already resolved through `mcp` to `pyjwt[crypto]` and is pinned at 50.0.0 in
`uv.lock`; the diff of the lock is two lines, both of them declarations. What changes is
that the project now says out loud what it relies on, so a future upstream change in `mcp`
cannot remove our encryption without a resolution failure that names it.

**Verification.** `slopcheck` was not runnable in this environment: it shells out to `pip`
and there is no `pip` on the PATH of this uv setup (`uv tool run --from slopcheck slopcheck
install cryptography` ends in a `FileNotFoundError`). The check was therefore done by hand
against the PyPI JSON API and the installed distribution:

- project URLs point at `github.com/pyca/cryptography`, the Python Cryptographic Authority,
- 158 releases, current version 50.0.0 uploaded 2026-07-31,
- one of the twenty most downloaded packages on PyPI, and a dependency of `pyjwt[crypto]`,
  which the official MCP SDK itself pulls in,
- `uv run --no-sync python -c "import cryptography; print(cryptography.__version__)"`
  answers `50.0.0`, the version in the lock.

**Owner decision.** Approved by the repository owner on 2026-08-16 after the question was
put explicitly, together with the constraint that the lock step must not touch the virtual
environment. `uv lock` was used instead of `uv add`, which writes `uv.lock` only.

**Why an alternative was not taken.** Leaving the package transitive was the other option.
It would have meant that the encryption of every stored app password depends on a decision
in someone else's dependency list: the day `mcp` drops `pyjwt[crypto]`, the next clean
install of this project fails at import time, in production, with no warning in between.

## Resolved tree (`uv tree --depth 2`, 2026-08-14)

```
nextcloud-mcp-connector v0.1.0
├── httpx v0.28.1
│   ├── anyio v4.14.2
│   ├── certifi v2026.7.22
│   ├── httpcore v1.0.9
│   └── idna v3.18
├── icalendar v7.2.2
│   ├── python-dateutil v2.9.0.post0
│   └── tzdata v2026.3
├── lxml v6.1.1
├── mcp[cli] v2.0.0
│   ├── anyio v4.14.2
│   ├── httpx2 v2.10.0
│   ├── jsonschema v4.26.0
│   ├── mcp-types v2.0.0
│   ├── opentelemetry-api v1.44.0
│   ├── pydantic v2.13.4
│   ├── pyjwt[crypto] v2.13.0
│   ├── python-multipart v0.0.32
│   ├── pywin32 v312
│   ├── sse-starlette v3.4.8
│   ├── starlette v1.6.0
│   ├── typing-extensions v4.16.0
│   ├── typing-inspection v0.4.4
│   ├── uvicorn v0.52.3
│   ├── python-dotenv v1.2.2 (extra: cli)
│   └── typer v0.27.1 (extra: cli)
├── pydantic v2.13.4
│   ├── annotated-types v0.8.0
│   ├── pydantic-core v2.46.4
│   ├── typing-extensions v4.16.0
│   └── typing-inspection v0.4.4
├── vobject v0.9.9
│   ├── python-dateutil v2.9.0.post0
│   ├── pytz v2026.3.post1
│   └── six v1.17.0
├── pytest v9.1.1 (group: dev)
│   ├── colorama v0.4.6
│   ├── iniconfig v2.3.0
│   ├── packaging v26.3
│   ├── pluggy v1.6.0
│   └── pygments v2.20.0
├── respx v0.23.1 (group: dev)
│   └── httpx v0.28.1 (*)
└── ruff v0.16.3 (group: dev)
(*) Package tree already displayed
```

**Finding:** `httpx2 v2.10.0` appears exclusively as a child of `mcp[cli] v2.0.0`. It is not a
top-level entry, which is the machine-checkable form of the policy above. The unit test
`tests/unit/test_project_layout.py` asserts that no direct dependency starts with `httpx2`.

## Supply chain controls in force

- `uv.lock` is committed; CI installs with `uv sync --frozen` (no silent resolution drift).
- The SDK pin is `mcp[cli]>=2.0,<3`. Documented fallback pin if v2 turns out to be a blocker:
  `mcp>=1.29,<2` (1.x is in maintenance mode, security fixes only).
- No `npx --yes` and no auto-substitution of packages: a failing install is a human checkpoint,
  never a "try a similar name" retry.
- Re-run the audit whenever a direct dependency is added or a major version bumps.

## Upgrade check at phase 1 closing (T-01-SC, plan 14)

Executed on 2026-08-15 as required by the plan 14 threat register:

```
$ uv lock --upgrade-package mcp --dry-run
Resolved 60 packages in 591ms
No lockfile changes detected
```

Result: `mcp` 2.0.0 is current, no pending upstream release, the lockfile stays frozen.
The check is repeated at every phase closing; the lockfile is tracked and CI installs
with `uv sync --frozen`, so any drift fails the build instead of slipping in silently.

## Raising PyJWT to 2.14 (security release 2026-09-11, plan 20-01)

**What changed and how.** One line in `pyproject.toml`: `pyjwt[crypto]>=2.13,<3` became
`pyjwt[crypto]>=2.14,<3`. The lock was re-resolved with
`uv lock --upgrade-package pyjwt --upgrade-package cryptography` (never a blanket
`uv lock --upgrade`), followed by `uv sync`. Exactly three entries moved: `pyjwt` 2.13.0 to
2.14.0, `cryptography` 50.0.0 to 50.0.1, and the project's own lock entry from the stale
0.2.0 to 0.2.1. The number of package names in `uv.lock` is 60 before and after the run;
no package was added and none was removed.

**Why.** PyJWT 2.14.0 (released 2026-09-11) is a security release. Five advisories touch
the JWKS path, one sentence each:

- `GHSA-2gx3-rcp4-g85q`: an unknown `kid` in the unverified header forced a fresh JWKS
  fetch on every request, even against a fresh cache; 2.14 adds a cooldown and serializes
  concurrent refresh decisions.
- `GHSA-w6j9-cwv2-h6wq`: malformed JWK set entries let `AttributeError`/`TypeError` escape
  instead of a library error, so a broken entry could kill the whole set.
- `GHSA-8wjv-2p76-3863`: deeply nested JWS/JWK input caused unhandled recursion errors
  instead of a clean rejection.
- `GHSA-9v7f-9g4p-ffgj`: `PyJWKClient` followed redirects when fetching a JWKS, so a
  redirected target counted as a trusted key source.
- `GHSA-r6x4-923q-g947`: hardening of the HMAC key check against public key material
  passed as JWK, JWKS, array, DER or PEM.

Three of the five hit the inherited code in `src/mcp_connector/oauth/oidc.py` directly:
`GHSA-2gx3-rcp4-g85q` describes exactly the refetch behaviour of our `OidcClient._key`
(`if not fresh or kid not in self._keys.keys: await self._refresh_keys(now)`), and
`GHSA-w6j9-cwv2-h6wq` plus `GHSA-8wjv-2p76-3863` matter because `_usable_key` catches only
`jwt.PyJWTError` around `jwt.PyJWK(entry)` and `jwt.get_unverified_header(token)` is
guarded the same way, so on 2.13 a hostile token or a broken JWKS entry became an unhandled
exception at the transport boundary instead of a refusal. The other two do not hit our
code: our fetch path already refuses redirects and checks same-origin against the issuer
(`GHSA-9v7f-9g4p-ffgj` confirms that design rather than changing it), and the HMAC
hardening (`GHSA-r6x4-923q-g947`) is indirect at most because `HS*` algorithms are not in
the allowlist.

**Correction 2026-09-19 (phase 20 review, WR-01).** The paragraph above says the raise to
2.14 settles `GHSA-w6j9-cwv2-h6wq` for this code. It does not. The 2.14 corrections harden
`PyJWKClient`, not `PyJWK` against every input shape: measured against the installed
2.14.0, `jwt.PyJWK({"kty": "RSA", "n": None, "e": "AQAB", "kid": "x"})` still raises
`TypeError: Expected a string value`, and so do a numeric or list `n` and a numeric `x` on
an `OKP` entry. `TypeError` is not a `jwt.PyJWTError`, so `_usable_key` did not catch it.
The raise to 2.14 stands on its own merits (the other four advisories, and the template
`PyJWKClient` now validates); the escaping exception is closed in `oauth/jwks.py`, which
now catches `TypeError`, `ValueError` and `AttributeError` next to `jwt.PyJWTError`.
`get_unverified_header` was re-checked at the same time and needs nothing: on 2.14 it
raises `PyJWTError` for empty, non-object, deeply nested and base64-broken tokens.

**Why `jwt.PyJWKClient` is still not used, despite the fixes it received.** It is
synchronous on `urllib.request`, so in the ASGI server every fetch would block the event
loop or need a thread-pool detour. It also lacks a same-origin check against the issuer, a
size limit on the response, a key type allowlist, and the handling of a `kid` claimed by
more than one usable key. Its value for this project is the template it validates
(a cooldown after a failed refresh, serialized refresh decisions, never clearing the cache
on errors), not the code itself.

**cryptography moved in the same lock step.** The range in `pyproject.toml` stays
`>=50,<51`; 50.0.1 is a rebuilt wheel inside the already approved range, not an API
change, so the 2026-08-16 approval above continues to cover it.

**Resolved tree excerpt (`uv tree --depth 2`, 2026-09-19), pyjwt and cryptography lines
only.** The full snapshot from the original audit above is left untouched; it describes a past
state.

```
nextcloud-mcp-connector v0.2.1
├── cryptography v50.0.1
├── mcp[cli] v2.0.0
│   ├── pyjwt[crypto] v2.14.0
├── pyjwt[crypto] v2.14.0
│   └── cryptography v50.0.1 (extra: crypto) (*)
```

## The documents extra

Four parsers behind `files_read_as_markdown`, installed only with the extra `documents`:

| Package | Version | Licence | Reads |
|---|---|---|---|
| python-docx | >=1.2,<2 | MIT | DOCX through lxml |
| openpyxl | >=3.1,<4 | MIT | XLSX: parts through lxml, sheets and shared strings through expat |
| python-pptx | >=1.0,<2 | MIT | PPTX through lxml; pulls Pillow and XlsxWriter |
| pypdf | >=6.19,<7 | BSD-3 | PDF, pure Python |

openpyxl parses the workbook parts with lxml and `resolve_entities=False` when lxml is
installed. It reads sheets and shared strings with `iterparse` from the standard library
(expat). et_xmlfile is its writer and reads nothing here.

The guards come before and after the parsers. The DAV stat must show at most 25 MiB before
the download. The download itself stops one byte after 25 MiB, and a longer body is refused.
The three Office formats are zip containers. The guard reads their central directory before it
inflates anything. It allows at most 2000 entries and at most 50 MiB declared in total. It
also refuses an entry above 10 MiB that is compressed beyond 100:1.

lxml's default parser limits nesting depth and the size of one text node. It does not limit
the size of the document, and `huge_tree` is never enabled. A DOM costs several times the size
of its XML. For this reason the declared total is 50 MiB, and the converters have their own
caps. A sheet gives at most 256 columns and 10000 rows. A Word table gives at most 256 columns
and 10000 rows. The Markdown of one file stops at 8388608 characters with a note.

pypdf's own limits default to 75 MB per decoded stream. The converter lowers them to 4 MiB per
stream and 1000 form XObjects per page, because pypdf parses a content stream operator by
operator at tens of times its decoded size, and a page of drawing operators produces no text,
so the output cap never sees it. A stream above the limit is a guard refusal.

These guards bound what a file declares, not what a parser does with it. The conversion
therefore runs in a worker process per document, started with a minimal environment that
carries none of the server's secrets. The worker sets an address-space limit of 512 MiB on
itself before it imports a parser (RLIMIT_AS, enforced on Linux), so a file that inflates past
that gets a MemoryError and one refusal, not an out-of-memory server. The parent kills the
worker after 30 seconds of wall clock. At most two conversions run at once, and the slot is
taken before the download, so the bytes held for conversion are bounded as well.

No converter touches the network. Every parser exception becomes one refusal that names the
file and the format. Only the exception class is logged, at DEBUG, never the file name.

Pillow arrives through python-pptx and is not used by this server; it is imported by
python-pptx and decodes nothing here, because images are dropped without being opened. It is
listed so the next audit does not have to find out why it is in the lock.
