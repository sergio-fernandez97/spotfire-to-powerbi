# Can we host Spotfire Server ourselves? — assessment

**Date:** 2026-09-10
**Asked:** what would it take to self-host, and **can we skip the licence** (e.g. open source)?

## Verdict

**No, and it is blocked at the download, not just in the contract.** Self-hosting requires a
Spotfire **Enterprise** entitlement. There is no open-source Spotfire and no unlicensed path.

| Fact | Source |
|---|---|
| The Cloud Deployment Kit is Apache-2.0 but **contains no Spotfire software** — only Makefiles, Helm charts and templates | [CDK README](https://github.com/spotfiresoftware/spotfire-cloud-deployment-kit) |
| *"Spotfire products are commercially licensed... You must have a valid license for each of the Spotfire applications you choose to build and run in a container."* | CDK README |
| Deploying to a cloud environment may incur **additional** per-Processor-Unit fees | [CCEL Policy](https://www.cloud.com/content/dam/cloud/documents/legal/tibco-cloud-computing-environment-licensing-policy.pdf) |
| **Trial and webstore accounts cannot download the installers** from the Spotfire Download site | [Downloads FAQ](https://www.spotfire.com/downloads/faq) |
| *"Enterprise features that require your own server are not included in the trial"* | [Trial FAQ](https://community.spotfire.com/articles/spotfire/spotfire-trial-faq/) |
| Only **Spotfire Enterprise** ships the Spotfire Server installers/components | Trial FAQ |
| On-prem server licence ~USD 20k/year (third-party estimate, not official) | [Modern DataTools](https://www.modern-datatools.com/tools/spotfire/pricing) |

So our trial account cannot even fetch the packages the CDK needs. The licence is not a formality
we could defer — it is the gate on the download itself.

## Can we skip it? Yes — but by dropping Spotfire, not by pirating it

We do not actually need Spotfire Server. We need **an endpoint that speaks Library REST API v2 +
OAuth2 client-credentials**, to build and test the MCP server against. That is fully specified in
public docs, so write a stub:

- `POST /spotfire/oauth2/token` → returns a fake bearer token for `client_credentials`
- `GET /spotfire/rest/library/v2/info` → 200 when the token is valid, 401 otherwise
- `GET /spotfire/rest/library/v2/items` → a canned folder tree
- `GET /spotfire/rest/library/v2/items/{id}/contents` → the bytes of a real `.dxp` on disk

~150 lines of FastAPI. It costs nothing, needs no licence, and exercises **every** call our MCP
server makes — token caching, 401-refresh, streaming `/contents` to disk. Swapping in a real
`SF_URL` later is a one-line change, which is exactly why we reuse the official env-var names.

Two things it cannot do, and both are fine:

1. **Confirm real payload shapes.** Mitigate by coding to the [published v2 reference](https://docs.tibco.com/pub/spotfire_server/latest/doc/api/TIB_sfire_server_REST_API_Reference/library-v2.html)
   and treating responses defensively.
2. **Give us real DXPs.** Irrelevant — **DXP parsing never needed a server at all.** `.dxp` files
   are ZIPs; we parse them on the Mac. Fixtures come from Demos/Samples in the installed trial
   (see [`api-authentication.md`](./api-authentication.md)) or from our colleague's exports.

**There is no open-source Spotfire, and nothing else implements its Library API.** Do not go
looking for one.

## If an Enterprise licence is granted anyway — the real path

The CDK is the supported route. Version 7.0.2 validates **Spotfire Server 15.0.0** and deployment
`15.0.0 HF-002` — the same build our trial Analyst reports, so versions line up.

1. **Obtain the Enterprise entitlement.** Everything below is gated on this.
2. **Download the packages** listed in [`containers/build-files.mk`](https://github.com/spotfiresoftware/spotfire-cloud-deployment-kit/blob/main/containers/build-files.mk)
   from the [Download site](https://www.spotfire.com/downloads), plus hotfixes from the
   [hotfix list](https://community.spotfire.com/articles/spotfire/list-of-hotfixes-for-spotfire-clients-analyst-web-player-consumer-business-author-and-automation-services/).
3. **Prepare the host:** Linux (bare metal, VM, or WSL2), `docker`/`podman`, GNU Make 3.82+,
   Kubernetes 1.24+, Helm 3+. Check [system requirements](https://spotfi.re/sr).
4. **Build images and charts** — `make` in `containers/`, then `helm/`.
   ([containers README](https://github.com/spotfiresoftware/spotfire-cloud-deployment-kit/tree/main/containers) ·
   [helm README](https://github.com/spotfiresoftware/spotfire-cloud-deployment-kit/tree/main/helm))
   *Skip this by using pre-built images and charts per the
   [Spotfire on Kubernetes guide](https://spotfi.re/sok) — still entitlement-gated.*
5. **Deploy:** Spotfire Server + Node Manager, a PostgreSQL (or supported DB) for the server
   schemas, HAProxy reverse proxy with session affinity, an Ingress, and Persistent Volumes for
   library import/export.
6. **Register the API client — the whole point.** On the server, as admin:

   ```sh
   config register-api-client --name="spotfire-to-powerbi" \
       -Sapi.library.read -Sapi.information-model.read -Soffline \
       --client-profile=other -Gclient_credentials -Grefresh_token
   ```

   It prints the client ID and secret. This is the one command the hosted trial can never run.
7. **Validate** with the four calls in [`api-authentication.md`](./api-authentication.md#step-5--prove-the-token-actually-opens-the-library),
   then build the MCP server.

**Honest effort:** a Kubernetes deployment with a database, reverse proxy, ingress and node
services — days of work for someone who knows K8s, on top of a procurement conversation. Steps 1–5
exist solely to reach step 6.

## Recommendation

**Don't self-host.** Build the stub (hours, free) and parse real `.dxp` files in parallel. Spend
the political capital on the one ask that actually reaches the analyses we must migrate: getting
our colleague's Spotfire Server admin to run step 6 on **their** server, where the DXPs already
live. Self-hosting only ever gets us a credential to an empty library of our own.
