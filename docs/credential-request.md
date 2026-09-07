# Getting API access to the Spotfire library — Spotfire Cloud

**Deployment:** Spotfire Cloud (SaaS, hosted by Spotfire). Not a self-hosted server.
**Subscription owner:** our colleague — he can raise the request himself, no third party needed.

**Goal:** a `client_id` + `client_secret` with scope `api.library.read`, so our own MCP
server can authenticate against the Library REST API v2 and download DXPs.

---

## First: which Spotfire Cloud product is it?

This matters, because part of the Spotfire Cloud line was shut down.

| Product | Status |
|---|---|
| Spotfire Cloud Analyst | **retired 30 Nov 2025** |
| Spotfire Cloud Business Author | **retired 30 Nov 2025** |
| Spotfire Cloud Consumer | **retired 30 Nov 2025** |
| Spotfire Cloud - Additional Storage | **retired 30 Nov 2025** |
| **Spotfire Cloud Enterprise** | **not retired — current offering** |

Source: [Support Policy (Retirement Notice) for TIBCO Cloud Spotfire/Spotfire Cloud](https://support.tibco.com/external/article/135585/support-policy-retirement-notice-for-tib.html).

Since he's still using it in September 2026, he is on **Spotfire Cloud Enterprise** (or the
company was migrated onto it). Worth confirming, because Enterprise is the tier that gets a
managed Spotfire Server instance and a real support relationship — which is exactly what
this request depends on.

> Platform confirmed live: `demo.spotfire-cloud.com` returned HTTP 200 on its OAuth metadata
> endpoint and 401 (not 404) on `/rest/library/v2/info` when probed on 2026-09-07.

---

## Step 0 — confirm the tenant URL and that the API is reachable

Get the exact URL he logs into (`https://<tenant>.spotfire-cloud.com` or similar), then run
this yourself. No credentials needed — it's a public metadata endpoint:

```sh
curl -s https://<tenant>/spotfire/.well-known/oauth-authorization-server | jq
```

Check for:

- `"api.library.read"` in `scopes_supported`
- `"client_credentials"` in `grant_types_supported`
- the `token_endpoint` URL (note it — the MCP server needs it)

If both appear, the REST API is enabled on the tenant and the **only** missing piece is a
registered client. If they don't, say so in the ticket — Spotfire may need to run
`config-web-service-api` to turn the API on.

---

## Track A — requesting the OAuth client, step by step

On Spotfire Cloud there is no server host we control. `register-api-client` is a
command-line tool that only exists on the Spotfire Server machine, and nothing in the Cloud
admin portal registers OAuth clients (it covers users, groups, licenses, and library
permissions only). So **Spotfire's cloud operations team has to run it for us.** That means
a support case.

### Step 1 — he logs in to the support portal

<https://support.tibco.com/s/>

He needs the account tied to the Spotfire subscription. As subscription owner he should
already have it; if not, there's a registration flow on that page, and entitlement is keyed
to the support contract.

### Step 2 — he creates a new case

- **Product:** Spotfire Cloud Enterprise (or whatever the subscription actually says)
- **Environment:** the tenant URL from Step 0
- **Severity:** low / general request — this is a configuration change, not an outage
- **Subject:** `Register OAuth 2.0 API client with api.library.read scope on our tenant`

### Step 3 — he pastes this as the case body

> We need programmatic read-only access to our Spotfire library for an internal migration
> assessment (evaluating a move of some analyses to Power BI). Please register an OAuth 2.0
> API client on our tenant.
>
> Requested client configuration — this corresponds to the `register-api-client` command:
>
> ```
> config register-api-client \
>     --name="spotfire-to-powerbi" \
>     -Sapi.library.read \
>     --client-profile=other \
>     -Gclient_credentials
> ```
>
> | Setting | Value |
> |---|---|
> | Name | `spotfire-to-powerbi` |
> | Scope | `api.library.read` **only** — we do not need `api.library.write` |
> | Grant type | `client_credentials` |
> | Client profile | `other` (headless / non-interactive) |
>
> Please also confirm:
>
> 1. That the **Library REST API v2** (`/spotfire/rest/library/v2/...`) is enabled on our
>    tenant. If it is not, please enable the public Web Services API
>    (`config-web-service-api`).
> 2. Which **token endpoint authentication method** the client is registered with
>    (`client_secret_basic` or `client_secret_post`).
> 3. Whether any **rate limits** apply to the Library REST API on our tenant.
>
> Please return the **client ID** and **client secret** through a secure channel.
>
> Scope justification: this credential is read-only and limited to the library. It cannot
> create, modify, or delete library content, and it grants no access to the user directory,
> licensing, information model, automation services, or the web player. It is visible via
> `list-oauth2-clients` and can be revoked at any time with `delete-oauth2-client`.

### Step 4 — receiving the credentials

Ask for them **through the support portal case itself or a vault entry, not email or chat.**
What we need:

- `client_id`
- `client_secret`
- confirmation of the tenant base URL
- the answers to the three questions above

### Step 5 — if support pushes back

Two things usually unstick it:

- **Point out it's a standard, documented feature.** Reference
  [Registering an OAuth 2.0 API client](https://docs.tibco.com/pub/spotfire_server/12.0.5/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/registering_an_oauth_2.0_api_client.html)
  and the [Library REST API v2](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html)
  reference. This is the intended way integrations talk to the library.
- **Escalate through the account representative,** not support. As subscription owner he has
  one. Configuration requests on managed tenants often move faster through the account team.

If it's still refused, that is itself a finding — it means the tenant is not automatable and
the migration has to run off manual exports. Fall back to Track B and record the outcome.

### Realistic timeline

Days, not hours. Start this **first**, then do Track B while it's in flight.

---

## Track B — unblock the work today (do this in parallel)

He has a licensed login that can already reach every DXP he's permitted to read.

Ask him to export the DXPs in scope and send them:

- **From Analyst:** open the analysis → *File → Save As → Save to file*
- **From the web client:** open the library, select the analysis, download/export

**Even one representative `.dxp` unblocks the entire parsing half of the project** — data
sources, tables, calculated columns, expressions, embedded scripts. That's where the real
migration risk lives, and none of it needs an API. `.dxp` files are ZIP archives; they open
fine on macOS.

If the library turns out to hold too many analyses to export by hand, we can drive his
authenticated browser session instead — it reads exactly what he can already read.

---

## Verifying the connection is correct

This is the acceptance test for the whole credential exercise. Run it before writing any
MCP server code — if these four commands work, the MCP server is guaranteed to work,
because it does nothing else.

```sh
# .env (gitignored)
SF_URL=https://<tenant>
SF_CLIENT_ID=<client id>
SF_CLIENT_SECRET=<client secret>
```

### 1. Discover the token endpoint

```sh
set -a; . ./.env; set +a
curl -s "$SF_URL/spotfire/.well-known/oauth-authorization-server" | jq -r '.token_endpoint, .scopes_supported'
```

### 2. Get an access token

`client_secret_basic` — client ID and secret as HTTP Basic auth (try this first):

```sh
TOKEN=$(curl -s -u "$SF_CLIENT_ID:$SF_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' \
  -d 'scope=api.library.read' \
  "$SF_URL/spotfire/oauth2/token" | jq -r .access_token)
echo "${TOKEN:0:24}..."
```

If that returns `invalid_client`, the client was registered for `client_secret_post` instead
— send the credentials in the body:

```sh
TOKEN=$(curl -s \
  -d "client_id=$SF_CLIENT_ID" \
  -d "client_secret=$SF_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' \
  -d 'scope=api.library.read' \
  "$SF_URL/spotfire/oauth2/token" | jq -r .access_token)
```

### 3. Confirm the token actually opens the library

```sh
curl -s -w '\nHTTP %{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" \
  "$SF_URL/spotfire/rest/library/v2/info"
```

**200 = the connection is correct.** This is the moment the credential is proven.

Failure modes worth distinguishing:

| Response | Meaning |
|---|---|
| `401` | token rejected — wrong scope, expired, or wrong auth method |
| `403` | authenticated but the client lacks library read permission |
| `404` | Library REST API v2 not enabled on the tenant — go back to support |

### 4. Walk the library and download one DXP

```sh
# list the root's children
curl -s -H "Authorization: Bearer $TOKEN" \
  "$SF_URL/spotfire/rest/library/v2/items?path=/" | jq

# download a DXP by item id and confirm it's a real ZIP
curl -s -H "Authorization: Bearer $TOKEN" \
  "$SF_URL/spotfire/rest/library/v2/items/<itemId>/contents" -o sample.dxp
unzip -l sample.dxp
```

If `unzip -l` lists `meta-data.xml` and a GUID-named entry, the end-to-end path works and
the MCP server is just a wrapper around these calls.

### Notes for the MCP server implementation

- Tokens expire. Cache the token in memory, and refresh on any `401` rather than on a timer.
- Request `scope=api.library.read` explicitly at token time; don't rely on a default.
- Record which auth method worked (basic vs post) — hardcoding the wrong one is the most
  common failure here.
- `/contents` returns opaque bytes. Stream to disk; don't try to decode it as JSON.

---

## What to ask your colleague — the full list

1. **The exact Spotfire Cloud URL** he logs into.
2. **Which Spotfire Cloud product** the subscription is (expected: Cloud Enterprise).
3. **Raise the support case** in Track A — he owns the subscription, so it's his to file.
4. **One representative `.dxp` exported and sent over.** Highest value per minute of his
   time; ask for this first, it doesn't wait on anything.
5. **Which library folders** hold the analyses in scope, and **how many DXPs** roughly.
6. **What the analyses connect to:** Information Links, direct Oracle / SQL Server
   connections, embedded in-memory data, or external data functions.
7. **Do they use IronPython scripts, custom expressions, or data functions?**
   These have no Power BI equivalent and are the main thing that could sink the migration.

---

## References

- [Support Policy (Retirement Notice) for TIBCO Cloud Spotfire/Spotfire Cloud](https://support.tibco.com/external/article/135585/support-policy-retirement-notice-for-tib.html)
- [Spotfire Support Portal](https://support.tibco.com/s/)
- [Library REST API v2](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html)
- [`register-api-client` command reference](https://docs.tibco.com/pub/spotfire_server/14.0.6/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/register-api-client.html)
- [Registering an OAuth 2.0 API client](https://docs.tibco.com/pub/spotfire_server/12.0.5/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/registering_an_oauth_2.0_api_client.html)
- [Configuring Spotfire Server Web Services APIs](https://docs.tibco.com/pub/spotfire_server/12.0.2/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/configuring_spotfire_server_web_services_apis.html)
