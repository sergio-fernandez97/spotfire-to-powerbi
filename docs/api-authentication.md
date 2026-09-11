# Authenticating to the Spotfire API — from an installed Industry Pro seat

**Date:** 2026-09-10
**Situation:** we hold the licence ourselves — *Spotfire Industry Pro – Pro* — with the Spotfire
Windows Application installed.
**Server:** `https://update.spotfire.com` — **verified live and API-enabled**, see below.
**Question:** what are the exact steps to authenticate against the API?

---

## Verified against the actual server, 2026-09-10

Unauthenticated probes of `https://update.spotfire.com`. No credentials were used; every call
below is a public metadata or unauthenticated GET.

| Probe | Result | Reading |
|---|---|---|
| `/` | 302 → `/spotfire/ui/index.html`, title **"Administration Console"** | a real Spotfire Server, not just an update host |
| `/spotfire/.well-known/oauth-authorization-server` | **200**, full metadata | OAuth 2.0 authorization server is live |
| `/spotfire/rest/library/v2/info` | **401** | **Library REST API v2 is enabled** (401, not 404) |
| `/spotfire/rest/library/v1/info` | 401 | v1 also enabled |
| `/spotfire/rest/as/v1/job` | 401 | Automation Services API enabled |
| `/spotfire/rest/scim/v2/Users` | 401 | SCIM user-directory API enabled |
| `/spotfire/oauth2/auth` | 302 → error page for an unknown `client_id` | endpoint live, and it validates clients |
| `registration_endpoint` in metadata | **absent** | **dynamic client registration is off** — a client must be registered by an admin |

**The headline result: the API is switched on and reachable. The only missing piece is a
registered OAuth client** — exactly the conclusion of
[`credential-request.md`](./credential-request.md), now confirmed against our own server rather
than a demo instance. There is no `config-web-service-api` step needed.

### The metadata document, in full

```json
{
  "issuer": "https://update.spotfire.com/spotfire",
  "authorization_endpoint": "https://update.spotfire.com/spotfire/oauth2/auth",
  "token_endpoint": "https://update.spotfire.com/spotfire/oauth2/token",
  "revocation_endpoint": "https://update.spotfire.com/spotfire/oauth2/v1/revoke",
  "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
  "response_types_supported": ["code"],
  "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
  "code_challenge_methods_supported": ["S256"],
  "prompt_values_supported": ["none", "login", "consent"],
  "scopes_supported": [
    "api.deployment-report.generate",
    "api.information-model.read", "api.information-model.write",
    "api.js-api",
    "api.library.read", "api.library.write",
    "api.licenses.read", "api.licenses.write",
    "api.rest.automation-services-job.execute",
    "api.rest.health-metrics",
    "api.rest.library.upload",
    "api.web-player.load",
    "offline",
    "user-directory.read.all", "user-directory.write.all"
  ]
}
```

Five things in there matter to us:

1. **`api.library.read` is supported** — the scope we need exists on this server.
2. **The authorization endpoint is `/spotfire/oauth2/auth`**, *not* `/oauth2/authorize`. Easy to
   get wrong; it is hardcoded correctly in Path B below.
3. **`token_endpoint_auth_methods_supported` includes `"none"`** — the server accepts public
   clients, so the native + PKCE flow in Path B is viable here.
4. **`code_challenge_methods_supported` is `["S256"]` only** — `plain` will be rejected.
5. **There is an `offline` scope.** This is Spotfire's equivalent of `offline_access`: request it
   alongside `api.library.read` or the token response will contain no refresh token, and the MCP
   server will need a fresh browser login every time a token ages out.

Also worth noting for the migration itself: **`api.information-model.read`** is available. That
scope covers Information Links and data source definitions — precisely the mapping information
Power BI needs and which is *not* inside a `.dxp`. Add it to the same request; it costs nothing
extra to ask for both at once.

### The uncomfortable part: whose server this is

`update.spotfire.com` is **Spotfire's own shared hosted infrastructure**, not a tenant dedicated
to us. Evidence: the hostname is generic rather than per-customer, it doubles as the Windows
client's update/deployment host, the `JSESSIONID` names the backend `sha-production-tss-1-srv`,
and it sits behind an AWS load balancer.

That matches the webstore model exactly — Spotfire's webstore FAQ says webstore subscribers
"connect to a Spotfire Server hosted by us." And it lowers the odds on Paths A and B: Spotfire's
cloud operations team is being asked to register a bespoke OAuth client **on a shared production
server**, for one individual-use subscription. That is a materially harder request than the same
change on a dedicated Enterprise tenant, and it may simply be refused as a matter of policy.

**Plan accordingly: treat [Path C](#path-c--the-authentication-we-already-have) as the primary
route and Paths A/B as the parallel long shot,** rather than the other way round. If the request
is refused, that is a finding — it means the library is not automatable for us and the migration
runs off exports from the installed app.

### The admin-console check came back negative, 2026-09-10

We ran it. Logging in to the web UI with the Industry Pro credentials produced, in order:

1. **"The analysis could not be opened because no Web Player services are available. Contact your
   Spotfire administrator"** — with a log reference, and a Continue button.
2. After Continue: **the Library browser** at `/spotfire/library`, listing the library root.

Three conclusions, all of them load-bearing:

| Finding | Consequence |
|---|---|
| The login **succeeded** | the account authenticates against this server — the credential itself is fine |
| **No Administration Console** — we land on the library browser, not admin nodes | **not a server administrator, so there is no self-service OAuth client.** Paths A and B require the support case, on shared infrastructure |
| **No Web Player services** | no browser-based analysis viewing at all |

The Web Player result matches the licence rule exactly: Industry Pro's Web Application access
requires an Enterprise licence, and this webstore seat has none. It is *possible* this is instead
a transient node outage, so it is worth one retest — but do not plan around it changing.

Note that `/spotfire/ui` (Administration Console) and `/spotfire/library` (library browser) are
two separate registered applications on this server, not one SPA serving every path — a nonsense
path under `/spotfire/` returns 403, while both of those return their own HTML shell.

### The library is empty of anything we would migrate

This is the most consequential thing on either screen. The library root contains **five folders,
all of them Spotfire-shipped content**:

| Folder | Modified | What it is |
|---|---|---|
| `/Data Science Actions` | 2025-06-27 | shipped Data Science content |
| `/Data Science Mods` | 2025-06-27 | shipped Data Science content |
| `/GeoAnalytics` | 2026-08-24 | shipped premium content |
| `/Premium actions` | 2026-08-24 | shipped premium content |
| `/Premium Modules` | 2026-08-24 | shipped premium content |

No user analyses. No `.dxp` files. No company folders. No personal/`Users` folder visible at root.
The 2026-08-24 timestamps are a recent platform deployment, not our activity.

**So this environment is not an access path to the analyses we are migrating.** Those live in our
colleague's separate Spotfire environment, and an Industry Pro seat on `update.spotfire.com`
reaches none of it. What this licence actually buys the project is:

1. **An Analyst install** that can open any `.dxp` the colleague sends — the parsing half.
2. **A sandbox library** we control, to build and test the MCP server against once we can save our
   own DXPs into it.

Both are genuinely useful. Neither is "API access to the analyses in scope." If the credential
work is meant to reach the real library, it has to target **their** server, not this one — which
means [`credential-request.md`](./credential-request.md) is currently pointed at the wrong host.

### It is a Trial, not a purchased seat — 2026-09-10

The Analyst window title reads **"Spotfire® Industry Pro – Trial"**, with a red TRIAL badge on
the start page. This is the trial, not a webstore subscription.

That effectively closes Paths A and B for this environment. We would be asking Spotfire's cloud
operations team to register a bespoke OAuth client on their shared production server, for a
**trial** account, and the credential would outlive the trial window. Do not spend effort on the
support case against `update.spotfire.com`.

It also puts a clock on everything: trials are time-limited, so any work that depends on this
environment should happen now. Confirm the expiry from **Help → About**.

Revised standing:

| | Status |
|---|---|
| Library REST API v2 on this server | enabled, but unreachable without a client we cannot get |
| OAuth client via admin console | **closed** — not an admin |
| OAuth client via support case | **closed in practice** — trial on shared infra |
| Library UI cookie session | unknown, worth 30 seconds in DevTools |
| **Analyst app as an authenticated client** | **open — this is the route** |
| DXP parsing | open, and never needed authentication |

### The trial Analyst is not connected to a Spotfire Server — 2026-09-10

Two observations from the installed app:

- **Help → About**: `Spotfire® Industry Pro – Trial 15.0.0 HF-002`, build `15.0.0.94`,
  dated 2026-08-03, © Cloud Software Group. **No Spotfire Server URL is listed.**
- **The open panel** (`+` → Files and data): `Recent`, `Favorites`, `Samples`, `Connect to`,
  `Browse local file...`, `Other` are all live — but **`Spotfire library` is greyed out**, with
  only `Accelerators`, `Add-ons` and `Demos` under it. No recent files.

Read together, that says this Analyst is running **standalone/local**, not signed in to
`update.spotfire.com`. Confirm from the **User** menu in the menu bar before treating it as
settled — it should name the signed-in account and server, or offer a sign-in.

**Consequence: the scripted half of Path C is moot for now.** `LibraryManager` needs a live
server session; it cannot enumerate a library that is not attached. The IronPython discovery
script is worth running only after a library connection exists.

**What is unaffected:** DXP parsing. We parse `.dxp` files with Python on the Mac — Analyst is not
in that loop at all. So the trial's remaining value to the project is as a *fixture factory*.

Note the version: **15.0.0**. Our references so far cite 12.x and 14.x docs; the `update.spotfire.com`
server is presumably on the same 15.x line. Worth re-checking the DXP container layout against a
15.x file rather than assuming the Spotfire 12 behaviour.

### Free, rich test fixtures: Demos and Samples

The open panel offers **Demos**, **Samples** and **Accelerators**, and they are *not* greyed out —
they come from Spotfire's own hosted content, not from our library. These are professionally built
analyses containing exactly the constructs the migration has to handle: multiple pages,
calculated columns, custom expressions, and quite possibly data functions and IronPython.

Open one, then **File → Save As → File** to get a real `.dxp` on disk. That gives the parser a
serious test fixture today, with no credential, no admin, no library connection, and no dependency
on our colleague. It is the single most useful thing this trial provides.

### The one path worth chasing next: the library UI's own API

The library browser we just reached is authenticated by the `JSESSIONID` cookie the server hands
out at login. That is a **different surface** from `/rest/library/v2`, which the API reference says
does not use sessions at all. If the UI's internal endpoint can be driven with that cookie, we can
script everything our own login can already see — with no OAuth client, no admin, and no support
case.

This cannot be determined from outside: every path under `/spotfire/rest/*` answers **401
unauthenticated whether or not it exists**, including `/spotfire/rest/errors/report-csp-violation`,
which the server's own CSP header proves exists. Blind probing is therefore useless. It takes
thirty seconds in a logged-in browser instead:

1. On the library page, open **DevTools → Network**, filter to Fetch/XHR.
2. Click into a folder — e.g. `/GeoAnalytics`.
3. Read the request URL, method, and any headers beyond the cookie (expect an `X-XSRF-TOKEN`
   echoing the `XSRF-TOKEN` cookie the server sets).
4. Right-click the request → **Copy as cURL**, and paste it here.

Also worth checking on the same screen: the **⋮** menu on a library row, for a Download or Export
option. If it exists, that is a manual export route that needs neither Analyst nor the API.


---

## Read this first: what Industry Pro does and does not give us

`Spotfire Industry Pro` is the new name for **Spotfire Data Science** — renamed in a 2025 product
announcement to reflect its positioning for technical and subject-matter experts. It is one of
two licence tiers, alongside `Spotfire Analytics`.

What one Industry Pro licence includes, per Spotfire's own licence page:

| Included | Note |
|---|---|
| 1 named Industry Pro User | Windows Application, Web Application, or both |
| 1 named QuantumCast User | Upstream, Minerals, InventoryIQ |
| Web Application access | **only if an Enterprise licence also exists** |
| A Spotfire Server we administer | **not included** — that is the Enterprise licence |
| OAuth API client registration rights | **not included** |

**This is a named-user licence, not a server entitlement.** It is the strongest client tier
Spotfire sells and it changes nothing about API authentication, because API authentication is
granted at the *server*, not at the seat. There is no personal access token, no API key, and no
self-service credential anywhere in the Spotfire product.

So the blocker has not moved — it has only changed owner. It is ours to file now.

**But one real thing did unlock:** the installed application is itself an already-authenticated
client. See [Path C](#path-c--the-authentication-we-already-have).

---

## Step 1 — Server URL: done

`https://update.spotfire.com`, confirmed above. For the record, this is what
**Manage servers → Edit** in the Analyst login dialog would show. Note the version from
**Help → About** if you have the Windows machine to hand — useful for the support case, since
this server runs whatever the current release is.

> **Note on the Mac.** The Spotfire Analyst / Windows Application is Windows-only; the webstore
> sells "the Spotfire Analytics application for Windows". So the app is on a Windows machine or
> VM. Only Path C needs that machine. Every `curl` here runs from macOS — all the probes above
> did.

## Step 2 — Deployment: Spotfire-hosted

Confirmed by the probes: shared, Spotfire-operated, no host we control. `register-api-client`
runs only *on the Spotfire Server machine*, so we cannot run it.

The consequence is a support case. The case body is already written in
[`credential-request.md`](./credential-request.md#step-3--he-pastes-this-as-the-case-body) — file
it under our own subscription, amended with the facts from this document: the server is
`update.spotfire.com`, the API is already enabled, and the only ask is client registration.

## Step 3 — Metadata probe: done

Results above. Re-run it any time with:

```sh
SF_URL=https://update.spotfire.com
curl -s "$SF_URL/spotfire/.well-known/oauth-authorization-server" | jq
```

## Step 4 — Pick the grant type before asking for anything

All three grants are supported on this server, so this is a real choice — and one of these is a
much easier thing to ask for.

| | **Path A — `client_credentials`** | **Path B — `authorization_code` + PKCE** |
|---|---|---|
| Who the token acts as | a service account, no human | **you**, your Industry Pro user |
| Permissions | whatever the admin grants the client | exactly what your seat can already read |
| Secret to store | yes, a long-lived `client_secret` | none — public client, `auth_method: none` |
| Human in the loop | none — fully headless | browser login once, then refresh tokens |
| Right for | the MCP server running unattended | proving the path; approval-averse admins |
| Ask difficulty | higher — a standing credential on shared infra | **lower — grants no new access** |

**Lead with Path B.** A native client using `authorization_code` cannot read anything we cannot
already read by double-clicking the analysis in Analyst, which removes the main objection to
registering a client on shared production infrastructure. Path A is what we ultimately want for
unattended runs; a working Path B makes it a far easier follow-up.

Request `refresh_token` **and the `offline` scope** either way.

---

## Path A — client credentials (headless service account)

### A1. What to ask Spotfire support to run, on the server host

```sh
config register-api-client \
    --name="spotfire-to-powerbi" \
    -Sapi.library.read \
    -Sapi.information-model.read \
    -Soffline \
    --client-profile=other \
    -Gclient_credentials \
    -Grefresh_token
```

The command prints the **client ID and client secret** — the only time the secret is shown.
`--client-profile` accepts `web`, `user_agent`, `native`, or `other`; `other` is the headless
profile. `-G` defaults to `client_credentials` if omitted. At least one server in the collective
must be running for the command to succeed.

### A2. Store the credentials

```sh
# .env — gitignored, never committed
SF_URL=https://update.spotfire.com
SF_CLIENT_ID=<client id>
SF_CLIENT_SECRET=<client secret>
```

### A3. Get a token

The server accepts both `client_secret_basic` and `client_secret_post`. Basic first:

```sh
set -a; . ./.env; set +a

TOKEN=$(curl -s -u "$SF_CLIENT_ID:$SF_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' \
  -d 'scope=api.library.read offline' \
  "$SF_URL/spotfire/oauth2/token" | jq -r .access_token)
```

If that returns `invalid_client`, send the credentials in the body instead:

```sh
TOKEN=$(curl -s \
  -d "client_id=$SF_CLIENT_ID" -d "client_secret=$SF_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' -d 'scope=api.library.read offline' \
  "$SF_URL/spotfire/oauth2/token" | jq -r .access_token)
```

Then go to [Step 5](#step-5--prove-the-token-actually-opens-the-library).

---

## Path B — authorization code + PKCE (log in as ourselves)

### B1. What to ask support to run

```sh
config register-api-client \
    --name="spotfire-to-powerbi-cli" \
    -Sapi.library.read \
    -Sapi.information-model.read \
    -Soffline \
    --client-profile=native \
    -Gauthorization_code \
    -Grefresh_token \
    --require-end-user-consent=false
```

Public clients — which `native` is — **must** use PKCE (RFC 7636), and this server supports
`S256` only. `-R`/`--redirect-uri` is required for `authorization_code` *except* under the native
profile, which may use loopback redirection or a custom URI scheme per RFC 8252 §7. We use
loopback below; if support registers an explicit redirect URI anyway, use theirs verbatim.

### B2. Generate the PKCE pair

```sh
CODE_VERIFIER=$(openssl rand -base64 64 | tr -d '\n' | tr '+/' '-_' | tr -d '=' | cut -c1-64)
CODE_CHALLENGE=$(printf %s "$CODE_VERIFIER" \
  | openssl dgst -binary -sha256 \
  | openssl base64 | tr -d '\n' | tr '+/' '-_' | tr -d '=')
STATE=$(openssl rand -hex 12)
echo "verifier=$CODE_VERIFIER"   # keep this — B5 needs it
```

### B3. Start a one-shot listener for the redirect

In a second terminal:

```sh
printf 'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nDone - back to the terminal.\r\n' \
  | nc -l 8765
```

It prints the incoming `GET /callback?code=...&state=...` request line, then exits.

### B4. Open the authorization URL and log in

Note the endpoint path — `/oauth2/auth`, taken from this server's own metadata:

```sh
open "https://update.spotfire.com/spotfire/oauth2/auth?response_type=code\
&client_id=$SF_CLIENT_ID\
&redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback\
&scope=api.library.read%20offline\
&state=$STATE\
&code_challenge=$CODE_CHALLENGE\
&code_challenge_method=S256"
```

Log in with the **Industry Pro account** — the same one used in Analyst. Then read `code` and
`state` off the listener output, and verify `state` matches B2 before using the code.

An unrecognised `client_id` here redirects to `/spotfire/ui/error/errorAuthEndpoint` — that is
what the probe above hit, and it is the signature of a client that was never registered.

### B5. Exchange the code for a token

A native client has no secret, so `client_id` goes in the body:

```sh
CODE=<code from the listener>

RESP=$(curl -s \
  -d 'grant_type=authorization_code' \
  -d "code=$CODE" \
  -d "client_id=$SF_CLIENT_ID" \
  -d 'redirect_uri=http://127.0.0.1:8765/callback' \
  -d "code_verifier=$CODE_VERIFIER" \
  "https://update.spotfire.com/spotfire/oauth2/token")

TOKEN=$(echo "$RESP" | jq -r .access_token)
echo "$RESP" | jq -r .refresh_token   # empty means the 'offline' scope was not granted
```

The authorization code is single-use and short-lived. If B5 fails, redo from B2 with a fresh
verifier — reusing a spent code returns `invalid_grant`.

### B6. Refresh later instead of logging in again

```sh
TOKEN=$(curl -s \
  -d 'grant_type=refresh_token' \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=$SF_CLIENT_ID" \
  "https://update.spotfire.com/spotfire/oauth2/token" | jq -r .access_token)
```

Tokens can be revoked at `https://update.spotfire.com/spotfire/oauth2/v1/revoke`.

---

## Step 5 — Prove the token actually opens the library

Same acceptance test either path. Tokens go in an `Authorization: Bearer` header per
RFC 6750 §2.1.

```sh
curl -s -w '\nHTTP %{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" \
  "https://update.spotfire.com/spotfire/rest/library/v2/info"
```

**HTTP 200 is the moment authentication is proven.** We already know this endpoint answers 401
without a token, so a 200 means the credential is the only thing that changed.

| Response | Meaning |
|---|---|
| `200` | authenticated — done |
| `401` | token rejected: wrong scope, expired, or wrong token-endpoint auth method |
| `403` | authenticated, but this identity lacks library read permission |
| `404` | would mean v2 is off — **already ruled out**, it answers 401 today |

Then walk the library and pull one file:

```sh
SF=https://update.spotfire.com/spotfire/rest/library/v2
curl -s -H "Authorization: Bearer $TOKEN" "$SF/items?path=/" | jq
curl -s -H "Authorization: Bearer $TOKEN" "$SF/items/<itemId>/contents" -o sample.dxp
unzip -l sample.dxp
```

`meta-data.xml` plus a GUID-named entry in that listing means the end-to-end path works and the
MCP server is just a wrapper around these calls.

---

## Path C — the authentication we already have

Available right now: no credential, no admin, no support case. **The installed application is a
fully authenticated Spotfire client.** Logged into Analyst against `update.spotfire.com`, our
Industry Pro user can already read every library item it is permitted to read.

Two things follow:

1. **DXP bytes, today.** *File → Save As → Save to file* writes the `.dxp` locally. One
   representative file unblocks the entire parsing half of this project — data sources,
   calculated columns, custom expressions, IronPython, data functions. That is where the real
   migration risk lives, and none of it needs the REST API.
2. **Scripted enumeration inside the app.** IronPython in Analyst reaches the library through the
   `LibraryManager` service — `Search()` with expressions like `item_type: dxp`, and
   `TryGetItem()` by path. That covers discovery with no OAuth client at all.

   Gotcha: authoring IronPython requires the **Author Scripts** licence function — script authors
   must belong to the **Script Author** group. Industry Pro is the technical tier, so it is likely
   granted; confirm by checking whether **Edit → Document Properties → Scripts** is available. If
   it is missing, that is a licence-function request, a much smaller ask than an OAuth client on
   shared infrastructure.

### One earlier fallback is now definitively closed

"Drive an authenticated browser session" does **not** work against Library REST API v2. The API
reference is explicit: *"The API does not use HTTP sessions so there is no need to maintain
session cookies."* The server does hand out `JSESSIONID` and `XSRF-TOKEN` cookies for the
Administration Console, but those authenticate the console UI, not `/rest/library/v2`. On top of
that, Industry Pro's Web Application access requires an Enterprise licence, so there may be no
web analytics session to borrow at all.

For anything scripted and credential-free, Path C through the Windows application is the route —
not the browser.

---

## The short version

1. **Server confirmed:** `https://update.spotfire.com`, a live Spotfire Server with **Library REST
   API v2 already enabled** (401, not 404) and `api.library.read` in its supported scopes.
2. **The only missing piece is a registered OAuth client.** No dynamic registration, no API keys,
   and registration requires CLI access to a server host we do not have.
3. **The admin-console check failed:** our account is not a server admin, so there is no
   self-service OAuth client. Web Player is unavailable too, and the library holds only
   Spotfire-shipped content — **no analyses of ours to migrate live on this server.**
4. **Otherwise file the case**, asking for a **native + `authorization_code` + `refresh_token`**
   client with `api.library.read`, `api.information-model.read` and `offline` — the ask that
   grants no access beyond our own seat. `client_credentials` as the follow-up.
5. Temper expectations: this is Spotfire's shared hosted server, and we are an individual-use
   subscription. Refusal is a plausible outcome and is itself a finding. And settle first *which*
   server the analyses in scope actually live on — a credential here does not reach them.
6. **Meanwhile, export one `.dxp` from the installed app and start parsing.** That work never
   needed authentication, and it is where the migration risk actually lives.

---

## References

- [Spotfire® License Information](https://docs.tibco.com/spotfire-platform/license) — licence tiers, what Industry Pro includes
- [Product Announcement: Spotfire® Data Science Renamed to Spotfire® Industry Pro](https://support.tibco.com/external/article/138196/product-announcement-spotfire-data-scien.html)
- [Spotfire Industry Pro (product page)](https://www.spotfire.com/products/spotfire-industry-pro)
- [Spotfire webstore FAQ](https://community.spotfire.com/articles/spotfire/spotfire-webstore-faq/) — webstore connects to a Spotfire-hosted server; individual-use limitations
- [Library REST API v2](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html) — grants, scopes, PKCE, no session cookies, endpoints
- [`register-api-client` command reference](https://docs.tibco.com/pub/spotfire_server/14.0.6/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/register-api-client.html) — full option list, client profiles, examples
- [Registering an OAuth 2.0 API client](https://docs.tibco.com/pub/spotfire_server/latest/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/registering_an_oauth_2.0_api_client.html)
- [Registering the client](https://docs.tibco.com/pub/spotfire_server/latest/doc/html/TIB_sfire_server_tsas_admin_help/server/topics/registering_the_client.html) — native profile, PKCE, redirect URI rules
- [Downloading TIBCO Cloud™ Spotfire® Analyst](https://docs.tibco.com/pub/sfire-analyst/14.4.1/doc/html/en-US/TIB_sfire_client/client/topics/en-US/downloading_tibco_cloud_spotfire_analyst.html) — Manage servers dialog, regional server URLs
- [How to access and organize the Spotfire Library using IronPython](https://community.spotfire.com/articles/spotfire/how-access-and-organize-spotfire-library-spotfirer-using-ironpython-scripting/) — `LibraryManager.Search()`, `TryGetItem()`
- [Usage of Scripts and Data Functions](https://docs.tibco.com/pub/sfire-analyst/11.4.3/doc/html/en-US/TIB_sfire-analyst_UsersGuide/text/text_usage_of_scripts.htm) — Author Scripts licence function / Script Author group
- [`credential-request.md`](./credential-request.md) — the support-case body, ready to file
- [`spotfire-mcp-findings.md`](./spotfire-mcp-findings.md) — why we are building our own MCP server
