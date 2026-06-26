#!/usr/bin/env bash
# Deploy GreenFlow backend changes to the VM + git push (Vercel picks up frontend).
# Idempotent / resumable: safe to re-run any time (e.g. if a session is cut off).
#
# Secrets are NOT hardcoded. Provide the VM password via env:
#   export VM_PASS='...'         # required
#   ./scripts/deploy_vm.sh            # code deploy + git push  (default, safe)
#   ./scripts/deploy_vm.sh seed      # ALSO load El Niño data into Postgres (GATED, destructive)
#
# Needs: sshpass (brew install hudochenkov/sshpass/sshpass).
set -uo pipefail

VM_HOST="${VM_HOST:-root@14.225.168.28}"
: "${VM_PASS:?set VM_PASS env (VM ssh password) — not hardcoded for security}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH="sshpass -p $VM_PASS ssh -o StrictHostKeyChecking=no -o ConnectTimeout=25 $VM_HOST"
SCP="sshpass -p $VM_PASS scp -o StrictHostKeyChecking=no -o ConnectTimeout=25"

# Backend files -> copied into the api container; scripts -> /app/scripts.
FILES=(
  "backend/greenflow/agent/nodes/prediction.py"
  "backend/greenflow/ml/forecast_lag.py"
  "backend/greenflow/ml/models/forecast_lag_total.txt"
  "backend/greenflow/ml/models/forecast_lag_total_meta.json"
  "scripts/load_real_data.py"
  "scripts/train_forecast_lag.py"
)

say() { printf '\n>> %s\n' "$*"; }

say "find greenflow api container"
API=$($SSH "docker ps --format '{{.Names}}' | grep -iE 'greenflow.*api|green-flow.*api' | head -1" | tr -d '\r')
[ -z "$API" ] && { echo "ERROR: api container not found"; exit 1; }
GF_PKG=$($SSH "docker exec $API python -c 'import greenflow,os;print(os.path.dirname(greenflow.__file__))'" | tr -d '\r')
[ -z "$GF_PKG" ] && { echo "ERROR: greenflow package dir not found in $API"; exit 1; }
echo "   API=$API  GF_PKG=$GF_PKG"

# map a repo path to its in-container target
target_path() {
  case "$1" in
    backend/greenflow/*) echo "$GF_PKG/${1#backend/greenflow/}";;
    scripts/*)           echo "/app/$1";;
    *)                   echo "/app/$1";;
  esac
}

say "copy files into container"
for f in "${FILES[@]}"; do
  [ -f "$ROOT/$f" ] || { echo "   skip (missing): $f"; continue; }
  tgt=$(target_path "$f"); base=$(basename "$f")
  $SCP "$ROOT/$f" "$VM_HOST:/tmp/$base" >/dev/null \
    && $SSH "docker exec $API mkdir -p \$(dirname $tgt); docker cp /tmp/$base $API:$tgt" >/dev/null \
    && echo "   -> $tgt" || echo "   FAILED: $f"
done

say "restart api + health"
$SSH "docker restart $API >/dev/null; sleep 5; docker exec $API python -c 'import greenflow.agent.nodes.prediction; from greenflow.ml import forecast_lag; print(\"  import OK, lag model:\", forecast_lag.available())'"

if [ "${PUSH_GIT:-1}" = "1" ]; then
  say "git commit + push (Vercel frontend + repo sync)"
  cd "$ROOT"
  git add "${FILES[@]}" 2>/dev/null
  if git diff --cached --quiet; then
    echo "   nothing to commit"
  else
    git commit -q -m "Phase 1-2: El Niño ingest crosswalk + lag-based forecaster wired into prediction

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KmGRjCNoeSQgNGSQuHqJxo" \
      && git push origin HEAD && echo "   pushed" || echo "   push FAILED (commit kept)"
  fi
fi

# ----- GATED: load El Niño data into Postgres (destructive: replaces telemetry) -----
if [ "${1:-}" = "seed" ]; then
  say "SEED: backup telemetry, upload DuckDB, load El Niño 2024"
  DUCK_LOCAL="${DUCK_LOCAL:-$ROOT/../Dataset/elnino_new/DATA MỚI TINH /DATA/1. Dạng duckdb/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb}"
  [ -f "$DUCK_LOCAL" ] || { echo "ERROR: DuckDB not found at $DUCK_LOCAL"; exit 1; }
  DB=$($SSH "docker ps --format '{{.Names}}' | grep -iE 'greenflow.*(db|postgres)' | grep -v mlflow | head -1" | tr -d '\r')
  echo "   DB=$DB"
  say "backup telemetry -> /root/telemetry_backup_\$(date +%F).sql.gz on VM"
  $SSH "docker exec $DB pg_dump -U greenflow -d greenflow -t telemetry_zone_15m | gzip > /root/telemetry_backup_\$(date +%F_%H%M).sql.gz && ls -lh /root/telemetry_backup_*.sql.gz | tail -1"
  say "upload DuckDB (~497MB) -> container /data/elnino_2024/"
  $SSH "docker exec $API mkdir -p /data/elnino_2024"
  $SCP "$DUCK_LOCAL" "$VM_HOST:/tmp/elnino.duckdb" \
    && $SSH "docker cp /tmp/elnino.duckdb $API:/data/elnino_2024/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb && rm -f /tmp/elnino.duckdb"
  say "run ingest (DATASET_SCHEMA=elnino2024)"
  $SSH "docker exec -e DATASET_SCHEMA=elnino2024 $API python /app/scripts/load_real_data.py"
  echo
  echo ">> Data loaded. FINAL manual step (no replay): point the dashboard 'now' at the 2024 window."
  echo "   On the VM, in the greenflow compose dir, set REPLAY_NOW='' (or '2024-04-30T15:00:00')"
  echo "   in .env then: docker compose up -d api    (anchor() then uses max(timestamp))."
fi

say "done"
