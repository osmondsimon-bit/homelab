# ADR-024: Manual category-only AI insights for Actual Budget

**Date:** 2026-08-01

**Status:** Accepted; implementation codified, deployment disabled pending operator secrets and live acceptance

## Context

Actual Budget provides deterministic budget figures but does not produce a concise narrative about
which monthly category movements merit attention. The desired feature is a small overlay alongside
Actual, not a general finance chatbot and not an autonomous budgeting agent.

Actual does not expose a REST API. Its official `@actual-app/api` package downloads a budget to a
local client, decrypts E2EE data there, and exposes the same headless budget engine used by Actual.
The client is capable of writes as well as reads, and Actual does not provide a true read-only
service credential. That makes the extraction boundary and stored credentials the primary risks.

Sending raw finance data to a hosted model would be disproportionate. OpenAI states that API data is
not used for training by default, but ordinary Responses API requests can still be retained in abuse
monitoring logs for up to 30 days unless the organization has approved Zero Data Retention. Setting
`store: false` prevents response application-state storage; it is not itself Zero Data Retention.

The existing Actual VM already provides the required isolation, encrypted PBS protection,
loopback-only service pattern, and operator-only Tailscale ingress. A second VM would add lifecycle
and network complexity without creating a read-only Actual credential.

## Decision

Run an optional `actual-insights` companion container on **VM 127**, mounted at `/insights` on the
existing Actual Tailscale Serve hostname.

The overlay is **manually triggered once per completed month**. There is no cron job, timer,
background generation loop, webhook, or weekly memo.

### LLM data boundary

The model receives only this allowlisted data:

| Field | Purpose |
|---|---|
| Target month | Identifies the completed month being reviewed |
| Three-letter currency code | Lets the application interpret integer-cent values consistently |
| Synthetic category reference (`c001`, etc.) | Lets model findings refer to a category without sending Actual IDs |
| Category group name | Sent verbatim as category context |
| Category name | Sent verbatim as category context |
| Category type | `expense` or `income` |
| Target budgeted, actual, and balance amounts | Integer cents; unavailable values are `null` |
| Previous-month actual | Locally derived category comparison |
| Prior three- and twelve-month average actuals | Locally derived category comparisons |
| Target-versus-three-month-average basis points | Locally calculated; the model does no arithmetic |
| Budget variance | Locally calculated budgeted minus actual amount |
| Available history count | Prevents the model overstating thin comparisons |

The model does **not** receive Actual IDs, transactions, split details, payees, accounts, balances,
notes, imported descriptions, rules, tags, schedules, budget names, Sync ID, credentials, overall
net worth, or the decrypted Actual database. The extractor does not call APIs that return those
objects. Top-level totals returned by `getBudgetMonth` are discarded.

Historical category rows are used locally to calculate comparisons; the model receives the derived
category comparisons, not the full month-by-month history.

### Extraction

- Pin `@actual-app/api` to `26.7.0`, matching the pinned Actual server release.
- Permit only `init`, `downloadBudget`, `getBudgetMonths`, `getBudgetMonth`, and
  `shutdown` in the adapter.
- Create a new API cache for each manual run on container tmpfs, then recursively destroy it in a
  `finally` block after success or failure.
- Never call `sync`, arbitrary ActualQL, transaction/account/payee/schedule reads, or a mutation.
- Treat this as **read-only by implementation and tests**, not as server-enforced authorization.

### Deterministic analysis and model role

All amount normalization, averaging, variance, percentage, and evidence rendering happens locally.
Expense activity is normalized so positive integer cents means net spending; income activity remains
positive receipts.

Use the OpenAI Responses API with:

- configurable default model `gpt-5.6-terra`;
- low reasoning effort;
- `store: false`;
- no tools, retrieval, files, conversation, or model-managed state;
- strict JSON Schema output.

The model may prioritize up to five category findings and explain what to review. It returns only a
synthetic category reference and allowlisted evidence names. It may not put digits, currency symbols,
percentages, or numeric claims in prose. The application rejects unknown category references,
unavailable evidence, unexpected fields, and numeric prose, then locally rehydrates the category
label and exact amount evidence for the UI.

This separation makes the model a narrative ranking layer, not a calculator or financial authority.
The memo is informational and must not provide tax, investment, credit, or automated budget advice.

### Access and state

- Bind the container only to VM loopback at `127.0.0.1:5007`.
- Tailscale Serve mounts it at `/insights`; Funnel is not used.
- Require an exact allowlisted `Tailscale-User-Login` identity for every UI and asset request.
- Protect manual POSTs with an origin check and a constant-time CSRF token comparison.
- Use a strict CSP, same-site secure cookie, HTML escaping, and no client-side JavaScript.
- Store validated category snapshots, memo JSON, model/response identifiers, token usage, timestamp,
  and snapshot hash in `/opt/actual/insights-data/insights.sqlite` with mode `0600`.
- Store Actual/server/E2EE credentials, Sync ID, and a project-scoped OpenAI key in separate
  VM-local files mounted read-only into the container. Never put their values in Compose environment,
  git, logs, prompts, or model input.
- Keep the root filesystem read-only; use tmpfs for `/tmp`; drop all Linux capabilities; enable
  `no-new-privileges`; cap memory, CPU, and process count.

The SQLite file contains sensitive category totals and narrative finance observations. It remains
inside the existing encrypted PBS image and inherits VM 127's proven recovery path.

### Dependency handling

The application pins all direct dependencies and commits its npm lockfile. Actual `26.7.0` does not
export the currently documented `getPreferences` helper at its package top level, so the three-letter
currency code is an explicit deployment value rather than a runtime query. The Actual `26.7.0`
dependency tree originally resolved a vulnerable `adm-zip`; override it to patched `0.6.0`
(`CVE-2026-39244`). Explicitly approve only the pinned `better-sqlite3@12.11.1` native install script
required by Actual's local engine. A production dependency audit must remain clean before deployment.

## Consequences

- The operator gets a focused monthly memo without exposing granular purchases or enabling model
  access to Actual.
- Category and group names are disclosed to OpenAI; they can themselves be sensitive and must be
  named accordingly in Actual if this is unacceptable.
- Default OpenAI retention is still a cloud-processing trade-off. Do not enable the overlay if
  category-level disclosure is unacceptable; wait for suitable dedicated local inference instead.
- The model cannot explain why a category changed because it never sees transactions or payees.
  That limitation is intentional.
- The Actual password and E2EE password must exist on VM 127 for unattended extraction after the
  operator clicks Generate. Compromise of the companion container could therefore exceed its intended
  read-only behavior even though normal code paths cannot. Container hardening and the single-user,
  tailnet-only boundary reduce but do not eliminate this risk.
- A memo is never generated merely because a month ends. Missing a month has no operational impact.
- Local LLM inference remains deferred; `gpt-oss-20b` requires roughly 16 GB and does not fit the
  existing 2 GB Actual VM design.

## Rejected alternatives

- **Raw transactions to a hosted model:** unnecessary disclosure and a larger prompt-injection surface.
- **Model tools connected to Actual:** would turn full-capability credentials into an agent action path.
- **Interactive chat:** invites arbitrary queries and unclear data scope; not required for a monthly memo.
- **Automatic weekly/monthly generation:** the operator requested an explicit monthly review action.
- **Browser-side Actual API:** experimental, requires cross-origin isolation, and leaves decrypted data
  in browser IndexedDB.
- **Separate VM:** adds infrastructure without fixing Actual's lack of read-only credentials.
- **Local model on VM 127:** incompatible with the VM's resource envelope.

## References

- [Actual API](https://actualbudget.org/docs/api/)
- [Actual API reference](https://actualbudget.org/docs/api/reference/)
- [Actual release versioning](https://actualbudget.org/docs/contributing/releasing/)
- [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model.md)
- [Tailscale Serve identity headers](https://tailscale.com/docs/features/tailscale-serve#identity-headers)
- [CVE-2026-39244 advisory](https://github.com/advisories/GHSA-xcpc-8h2w-3j85)
- [gpt-oss hardware guidance](https://openai.com/index/introducing-gpt-oss/)
