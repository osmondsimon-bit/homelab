# Actual Budget category AI insights

Manual category-only long-term and monthly narrative overlay for Actual Budget on VM 127. The
implementation remains opt-in in the example inventory; the real deployment requires its four local
secret files and the live acceptance checks below.

| | |
|---|---|
| Placement | companion container in Actual VM 127 on Carter |
| URL | `https://actual.<tailnet>.ts.net:8443/insights` |
| Triggers | operator explicitly generates the 24-month baseline or a completed-month memo |
| Schedule | none; no timer, cron, webhook, or background generation |
| Actual access | official `@actual-app/api` `26.7.0`; category budget reads only |
| Model | OpenAI Responses API, default `gpt-5.6-terra`, low reasoning, `store: false`, no tools |
| Model input | category/group labels and locally derived category aggregates/trends only |
| Local state | `/opt/actual/insights-data/insights.sqlite` |
| Decrypted cache | per-run `/tmp` directory on container tmpfs; always destroyed |
| Authentication | exact operator `Tailscale-User-Login` through Tailscale Serve |
| Backup | inherited encrypted PBS image for VM 127 |

## Exactly what leaves VM 127

The monthly request contains the completed target month, currency code, a synthetic category
reference, category group/name, income/expense type, target budgeted/actual/balance integer-cent
amounts, available-history count, previous-month actual, prior three/twelve/twenty-four-month
category averages, target-versus-three/twenty-four-month basis points, and budget variance.
Each category also includes an `available_evidence` list derived from its non-null local metrics so
the model cannot assume that a comparison exists for a short-history category.

The initial baseline covers the latest 24 completed months available locally and sends one derived
row per category observed anywhere in that window. That row contains observation coverage, whether
the category is still active, full-period total/average, first/latest six-month and latest
twelve-month averages, locally calculated direction and variability basis points, budgeted and
over-budget month counts, and the largest category month/amount.
The baseline category row carries the same locally derived evidence-availability allowlist.

Category and group names are sent verbatim. No Actual identifier is sent. The request contains no
transactions, payees, accounts, notes, imported descriptions, rules, schedules, tags, budget name,
Sync ID, credential, raw database, net worth, or account balance. Historical budget months are read
locally only to calculate category metrics. The full month-by-month series is not sent.

OpenAI states that API input is not used for training by default, but ordinary API requests may be
retained in abuse-monitoring logs for up to 30 days. `store: false` disables Responses application
state; it does not grant Zero Data Retention. If category-level disclosure is not acceptable, leave
`actual_insights_enabled: false`.

## Enable

1. Create a dedicated OpenAI project and project-scoped API key. Configure a conservative project
   spend limit and alerts. Do not reuse a personal or broad automation key.
2. In Actual, copy the Sync ID from advanced settings. Retrieve the server and separate E2EE
   passwords from Vaultwarden without displaying them in terminal history.
3. On mgmt-vm, create the four paths configured by:
   `actual_insights_server_password_file`, `actual_insights_sync_id_file`,
   `actual_insights_e2ee_password_file`, and `actual_insights_openai_api_key_file`. Each file contains
   one value and must be mode `0600`. Never commit or place them under the repository.
4. In the real gitignored `inventory/group_vars/all.yml`, set the exact Tailscale login and opt in:

   ```yaml
   actual_insights_operator_login: YOUR_TAILSCALE_LOGIN
   actual_insights_currency: AUD
   actual_insights_timezone: Australia/Sydney
   actual_insights_history_months: 24
   actual_insights_enabled: true
   ```

5. Run the application tests and dependency audit from `apps/actual-insights`, then deploy from
   `ansible/`:

   ```bash
   npm test
   npm audit --omit=dev
   ansible-playbook playbooks/provision-actual.yml
   ```

The playbook builds the local companion image, stages mode-`0400` read-only secret mounts, retains
Actual at the root URL, resets stale routes on this dedicated Tailscale node, exposes `/insights` on
HTTPS 8443 as a separate browser origin, and verifies both loopback ports. Deploying does not call
the model; only either UI button does. State-changing requests require a short-lived, one-time
server-side synchronizer token and never depend on reverse-proxy Host or Origin rewriting.

## First live acceptance

Before treating the overlay as available:

1. Confirm `docker compose ps` shows both containers healthy.
2. Confirm `ss -tlnp` shows ports 5006 and 5007 only on `127.0.0.1`.
3. Confirm port 443 still opens Actual and `:8443/insights` returns `403` without a Tailscale identity
   but opens for the configured operator. The separate port prevents Actual's root-scoped browser
   state from redirecting the companion route.
4. Generate the 24-month baseline manually, then close and sync a completed month and generate its
   monthly memo.
5. Inspect the stored snapshot using a local SQLite/JSON view and confirm it matches the allowlist
   above. Specifically search for known account and payee labels and confirm they are absent.
6. Confirm model prose contains no numeric claims and that exact evidence amounts are rendered by the
   local UI.
7. Confirm `/tmp` inside the container has no retained Actual budget directory after the request.
8. Run `npm audit --omit=dev` again if the image was built from a refreshed lockfile.

This repository cannot perform the live checks because the private VM and credentials are outside
the agent's network boundary.

## Initial baseline workflow

1. Reconcile and categorize the available completed history in Actual and let it sync.
2. Open `:8443/insights` from the configured operator device.
3. Click **Generate twenty-four-month trend analysis** once.
4. Review the locally rendered evidence. Repeat only after material historical category corrections.

The baseline requires at least 12 completed months and uses at most the latest 24. It never sends the
raw monthly category series to the model.

## Monthly workflow

1. Finish reconciliation and categorization in Actual for the previous month and let Actual sync.
2. Open `:8443/insights` from an operator device.
3. Select the completed month and click **Generate monthly memo** once.
4. Review the category evidence in Actual before acting. The memo is an observation layer, not
   financial advice and not an automatic budget edit.

The monthly comparison uses up to 24 prior months. The application refuses the current or a future
month and rejects concurrent generation across both actions. Repeating an analysis creates another
audit record, which is useful after category corrections.

## Operations

- Health inside VM 127: `curl -fsS http://127.0.0.1:5007/healthz`
- Container state: `cd /opt/actual && sudo docker compose ps insights`
- Redacted application logs: `cd /opt/actual && sudo docker compose logs --tail=100 insights`
- Tailscale routing: `sudo tailscale serve status`
- Local database: `/opt/actual/insights-data/insights.sqlite` (mode `0600`)

Application errors deliberately omit upstream details because Actual and model errors can contain
sensitive context. Diagnose credentials by checking file existence/mode and rotating the individual
secret rather than enabling verbose logs.

`OpenAI API quota unavailable` means the request passed the local extraction and OpenAI request
validation boundaries, but the API project returned `insufficient_quota`. Confirm that API billing
is active and that the dedicated project has usable spend limits before retrying. The failed run is
not persisted as a memo. Strict response schemas must remain within OpenAI's supported Structured
Outputs subset; prose lengths and duplicate evidence are enforced again by the application after
generation.

If a structurally valid model response fails the stricter local memo contract, the application makes
one fresh model request with the same category-only payload. It never applies this retry to API,
authentication, quota, or transport errors. A second validation failure returns a safe
`model_output_invalid` diagnostic without logging unvalidated model prose, and no memo is stored.

To disable, set `actual_insights_enabled: false` and rerun the playbook. The container is removed as
an orphan, Tailscale Serve is rebuilt with only Actual on 443, and the SQLite audit and secret files
are retained deliberately. Do not delete state or credentials as part of an ordinary disable.

## Upgrade and recovery

- Keep `@actual-app/api` exactly aligned with `actual_image` before upgrading Actual.
- Review Actual and OpenAI release notes, run tests/audit, then rebuild during the maintenance window.
- Preserve the `adm-zip: 0.6.0` security override until upstream Actual resolves to an equal or newer
  patched release; do not downgrade it to satisfy an automated package suggestion.
- The model pin is a deliberate behavior contract. Evaluate prompt/schema behavior with category-only
  fixtures before changing it.
- VM 127's encrypted PBS image includes the SQLite audit database and VM-local secret files. The
  existing isolated VM restore procedure applies. The Actual API cache is intentionally unrecoverable
  because it exists only on tmpfs during a request.

Related: ADR-024, ADR-023, ADR-018, and `docs/components/actual-budget.md`.
