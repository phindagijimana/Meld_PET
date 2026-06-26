#!/usr/bin/env bash
# Run Meld_PET inside an interactive SLURM allocation (no batch Snakemake/SLURM executor).
#
# Quick start (from a login node):
#
#   # PETPrep / register / visualize (≤12 h) — often starts faster than batch on general
#   salloc --partition=interactive --mem=32G --cpus-per-task=4 --time=12:00:00 --job-name=meldpet
#
#   # Long PETPrep or MELD (>12 h)
#   salloc --partition=general --mem=64G --cpus-per-task=8 --time=24:00:00 --job-name=meldpet
#
# Then inside the allocation:
#
#   cd /path/to/Meld_PET
#   pipeline/scripts/run_interactive.sh run sub-002
#   pipeline/scripts/run_interactive.sh run --aggregate sub-002 sub-036 sub-065
#   pipeline/scripts/run_interactive.sh register sub-002
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"
export TMPDIR="${ROOT}/work/tmp"
export APPTAINER_TMPDIR="${TMPDIR}"
mkdir -p "${TMPDIR}" "${ROOT}/work/logs"

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "[run_interactive] ERROR: not inside an SLURM allocation (SLURM_JOB_ID unset)." >&2
  echo "Request one first, e.g.:" >&2
  echo "  salloc --partition=interactive --mem=32G --cpus-per-task=4 --time=12:00:00" >&2
  exit 1
fi

echo "[run_interactive] node=${SLURMD_NODENAME:-?} job=${SLURM_JOB_ID} partition=${SLURM_JOB_PARTITION:-?}"

cd "${ROOT}"
exec meldpet --configfile pipeline/config/config.yaml --profile interactive --cores "${MELDPET_CORES:-4}" "$@"
