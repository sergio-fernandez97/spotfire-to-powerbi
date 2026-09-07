# Spotfire Library MCP — what exists, and why we're building our own

**Date:** 2026-09-04
**Question:** can we drive the Spotfire library from a coding assistant on macOS, via MCP,
as the first step of a Spotfire → Power BI migration?

**Short answer:** yes, but not with Spotfire's own MCP server. We need to write a thin one
ourselves, and we are blocked on one credential that only a Spotfire Server admin can issue.

---

## 1. The official `spotfire-lib` MCP server

Spotfire does publish an MCP server for the Library API. Source:
[MCP Server for Spotfire Library API — User Guide](https://community.spotfire.com/articles/spotfire/mcp-server-for-spotfire-library-api-user-guide-r3638/)
(Spotfire Community).

What the article documents:

| | |
|---|---|
| Internal name | `sflib` |
| Role | backend for the "Spotfire Library Metadata Agent" |
| Transport | `sse` (default), `stdio`, or `streamable-http` |
| Default port | 8062 |
| Health checks | `/healthz`, `/readyz` (`READYZ_TIMEOUT`, default 5.0s — `/readyz` validates connectivity to the Spotfire Server) |

Server environment contract:

```sh
TRANSPORT=sse          # or stdio, or streamable-http
HOST=0.0.0.0
PORT=8062

SF_URL=<https://spotfire-server/...>
SF_CLIENT_ID=<spotfire OAuth client id>
SF_CLIENT_SECRET=<spotfire OAuth client secret>

# Optional MCP-side auth for clients
# MCP_AUTH_ENABLED=true
# MCP_AUTH_ISSUER_URL=...
# MCP_AUTH_RESOURCE_SERVER_URL=...
# MCP_AUTH_JWKS_URL=...
# MCP_AUTH_REQUIRED_SCOPES=user
```

Its three tool categories:

1. **Connector discovery** — every data connector registered on the server, with type and properties.
2. **DXP discovery** — list DXPs with server-side filters by creator, title fragment, and
   library path prefix, plus a result limit.
3. **DXP metadata** — for one DXP: tables, columns, pages, bookmarks, embedded-data flags,
   permissions, versions.

Read access is whatever the configured client ID/secret can see. Responses are JSON-encoded strings.

---

## 2. Why we can't use it

### Blocker A — the code is not public

The article's only pointer to an implementation is
`https://github.com/spotfirefield/spot-mcp-and-agents/blob/develop/catalog/agents/spotfire-library-agent/USER_GUIDE.md`.

Checked on 2026-09-04:

- `GET https://api.github.com/repos/spotfirefield/spot-mcp-and-agents` → **404**
- Same URL loaded in the browser under our own logged-in GitHub session → **404**
- GitHub code search across `spotfiresoftware` and `spotfirefield` for `mcp` → **0 public repos**

It is a private Spotfire field/internal repository. There is no package, no container image,
and no public mirror. Getting access would mean going through a Spotfire account team, which
is a procurement conversation, not an afternoon.

### Blocker B — even with access, it doesn't do the thing we need

Every tool it exposes is **metadata**. There is no tool that returns the bytes of a DXP.

For a migration, metadata alone is not enough — we need the actual analysis file, because the
things that decide whether a dashboard can be rebuilt in Power BI (calculated column
expressions, custom expressions, IronPython scripts, data function definitions, connection
strings) live *inside* the file, not in the library's metadata index.

So even in the best case we would be running their server for discovery **and** hand-rolling
the download path anyway.

---

## 3. Why building our own is the right call

The thing the official server wraps is a documented, stable, public REST API:
[Library REST API v2](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html).

Everything we need is a handful of GETs:

| Endpoint | Purpose |
|---|---|
| `GET /rest/library/v2/info` | auth sanity check |
| `GET /rest/library/v2/items` | query items |
| `GET /rest/library/v2/items/{id}` | item metadata |
| `GET /rest/library/v2/items/{id}/children` | walk folders |
| `GET /rest/library/v2/items/{id}/versions` | version history |
| `GET /rest/library/v2/items/{id}/contents` | **download the .dxp bytes** |

Auth is standard OAuth2 client-credentials against the Spotfire Server itself:

- Metadata: `https://<host>/spotfire/.well-known/oauth-authorization-server`
- Token: `POST https://<host>/spotfire/oauth2/token`
- Scope needed: `api.library.read` (read-only; we do not need `api.library.write`)

That is a few hundred lines of Python on the official `mcp` SDK. Against that: an
indefinite wait on a private repo, for something that still wouldn't download files.

**We will reuse the official server's env-var names** (`SF_URL`, `SF_CLIENT_ID`,
`SF_CLIENT_SECRET`) so that if `spotfire-lib` ever goes public we can swap it in without
touching configuration.

Planned tools:

- `list_library_children(item_id)` — walk folders
- `search_dxps(path_prefix, title, creator, limit)` — DXP discovery
- `get_dxp_metadata(item_id)` — metadata + versions
- `download_dxp(item_id, dest)` — **the gap in the official server**

---

## 4. The one real blocker: credentials

Verified against Spotfire's own public demo server (`demo.spotfire.cloud.tibco.com`):

- `GET /spotfire/.well-known/oauth-authorization-server` → **200**, and it confirms
  `api.library.read` and the `client_credentials` grant are supported.
- `GET /spotfire/rest/library/v2/info` with no token → **401**
- `GET /spotfire/rest/library/v2/items` with no token → **401**

There is no anonymous read path, and the metadata advertises no `registration_endpoint`, so
dynamic client registration is out. A client ID and secret are mandatory, and they can only
be minted by an admin running one command in the Spotfire Server config tool **on the server
host**:

```sh
config register-api-client --name="spotfire-to-powerbi" \
    -Sapi.library.read \
    --client-profile=other \
    -Gclient_credentials
```

It prints a client ID and client secret. Notes for whoever approves it:

- **Read-only.** No write scope, so it cannot modify or delete anything in the library.
- `list-oauth2-clients` shows registered clients; `delete-oauth2-client` revokes this one
  when the evaluation is over.
- At least one server in the collective must be running for the command to succeed.

Reference:
[register-api-client](https://docs.tibco.com/pub/spotfire_server/12.0.6/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/register-api-client.html).

> **Update 2026-09-05 — we are on Spotfire Cloud, not a self-hosted server.**
> That makes the command above unavailable to us: there is no server host we control, and
> nothing in the Spotfire Cloud admin portal registers OAuth API clients (it covers users,
> groups, licenses, and library permissions only). Obtaining a client ID and secret becomes a
> **support request to Spotfire**, with an uncertain outcome depending on subscription tier.
> The workaround that needs no credentials at all is to go through an authenticated browser
> session. Both paths are written up in [`credential-request.md`](./credential-request.md).

---

## 5. What is *not* blocked

`.dxp` files are ZIP archives — `meta-data.xml` plus a GUID-named payload, which on Spotfire
12+ may carry a second layer of compression. They unpack with `unzip` on macOS; no Spotfire
Analyst and no Windows machine required. Prior art:
[emersonian/spotty](https://github.com/emersonian/spotty) extracts scripts from DXPs.

Practical consequence: **the DXP-parsing half of this project can be built and tested today**
against a single manually-exported `.dxp`, entirely in parallel with the credential request.
That half is also where the actual migration risk lives. The MCP server is only plumbing for
fetching files at scale.

---

## Sources

- [MCP Server for Spotfire Library API — User Guide](https://community.spotfire.com/articles/spotfire/mcp-server-for-spotfire-library-api-user-guide-r3638/)
- [Library REST API v2 | Spotfire Server](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html)
- [register-api-client | Spotfire Server admin help](https://docs.tibco.com/pub/spotfire_server/12.0.6/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/register-api-client.html)
- [Spotfire Server REST APIs overview](https://docs.tibco.com/pub/spotfire_server/12.0.0/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/spotfire_server_rest_apis.html)
- [emersonian/spotty — extract scripts from DXP files](https://github.com/emersonian/spotty)