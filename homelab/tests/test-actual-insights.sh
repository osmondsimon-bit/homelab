#!/usr/bin/env bash
# Regression contract for the manual, category-only Actual Budget AI overlay.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_dir="${repo_root}/homelab/apps/actual-insights"
playbook="${repo_root}/homelab/ansible/playbooks/provision-actual.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
component_doc="${repo_root}/homelab/docs/components/actual-ai-insights.md"
adr="${repo_root}/homelab/decisions/024-actual-ai-insights.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -f "${app_dir}/package.json" ]] || fail 'Actual insights application must exist'
[[ -f "$component_doc" ]] || fail 'Actual insights component documentation must exist'
[[ -f "$adr" ]] || fail 'Actual insights ADR must exist'

grep -Fq '@actual-app/api' "${app_dir}/package.json" \
  || fail 'the application must use the official Actual API package'
grep -Fq '"@actual-app/api": "26.7.0"' "${app_dir}/package.json" \
  || fail 'the Actual API package must match the pinned server release'
grep -Fq '"openai":' "${app_dir}/package.json" \
  || fail 'the model client must use the official OpenAI SDK'
grep -Fq 'gpt-5.6-terra' "$example_vars" \
  || fail 'the balanced insight model must be explicit and configurable'
grep -Fq 'actual_insights_enabled: false' "$example_vars" \
  || fail 'the overlay must be opt-in until its secrets are staged'
grep -Fq '127.0.0.1:5007:5007' "$playbook" \
  || fail 'the overlay must bind only to VM loopback'
grep -Fq -- '--set-path=/insights http://127.0.0.1:5007' "$playbook" \
  || fail 'Tailscale Serve must expose the overlay only at /insights'
grep -Fq 'Tailscale-User-Login' "${app_dir}/src/server.mjs" \
  || fail 'the overlay must authenticate the operator through Tailscale identity'
grep -Fq 'tmpfs:' "$playbook" \
  || fail 'the decrypted Actual API cache must use ephemeral tmpfs'
grep -Fq 'read_only: true' "$playbook" \
  || fail 'the overlay container root filesystem must be read-only'
grep -Fq 'no-new-privileges:true' "$playbook" \
  || fail 'the overlay container must enable no-new-privileges'
grep -Fq 'cap_drop:' "$playbook" \
  || fail 'the overlay container must drop Linux capabilities'

if rg -n -i 'cron|systemd.*timer|setInterval|weekly|schedule' "${app_dir}/src"; then
  fail 'memo generation must remain manually triggered with no scheduler'
fi
if rg -n -i '(cron|systemd.*timer|weekly|schedule).*insights|insights.*(cron|systemd.*timer|weekly|schedule)' \
  "$playbook"; then
  fail 'memo generation must remain manually triggered with no scheduler'
fi

if rg -n 'getTransactions|getAccounts|getPayees|getSchedules|runQuery|aqlQuery' \
  "${app_dir}/src"; then
  fail 'the extractor must not query transaction, account, payee, schedule, or arbitrary data'
fi

printf 'PASS: Actual insights regression contract\n'
