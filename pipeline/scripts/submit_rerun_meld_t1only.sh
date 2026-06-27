#!/usr/bin/env bash
# Re-run MELD T1-only for subjects that previously used FLAIR, then downstream steps.
set -euo pipefail

WORK="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/work"
DATA="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/data"
PIPE="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/pipeline"
SIF="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/meld_graph_v2.2.4.sif"
FSL="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/freesurfer_license.txt"
ML="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/meld_license.txt"
MODELS="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/models"
PARAMS="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/meld_params"
MELD_SUBS=(sub-002 sub-036)
ALL_SUBS=(sub-002 sub-036 sub-065)

APPTAINER="apptainer exec \
  --bind ${WORK}:/data \
  --bind ${MODELS}:/data/models:ro \
  --bind ${PARAMS}:/data/meld_params:ro \
  --bind ${FSL}:/license.txt:ro \
  --bind ${ML}:/meld_license.txt:ro \
  --bind ${PIPE}:/pipeline:ro \
  --env FS_LICENSE=/license.txt \
  --env MELD_LICENSE=/meld_license.txt \
  --env FREESURFER_HOME=/opt/freesurfer-7.2.0 \
  --env PYTHONNOUSERSITE=1 \
  ${SIF} \
  /bin/bash -c"

echo "[t1only] removing staged FLAIR and stale MELD outputs"
for sub in "${MELD_SUBS[@]}"; do
  rm -rf "${WORK}/input/${sub}/FLAIR"
  rm -f "${DATA}/${sub}"/*/anat/*FLAIR*.nii.gz 2>/dev/null || true
  rm -rf "${WORK}/output/fs_outputs/${sub}"
  rm -rf "${WORK}/output/predictions_reports/${sub}"
  rm -rf "${WORK}/output/preprocessed_surf_data/${sub}" 2>/dev/null || true
done
rm -rf "${WORK}/output/preprocessed_surf_data/MELD_noHarmo"

printf '%s\n' "${MELD_SUBS[@]}" > "${WORK}/logs/t1only_rerun_ids.txt"

MELD_ID="$(sbatch --parsable \
  --job-name="meld_t1only" \
  --partition=general \
  --mem=64G --cpus-per-task=8 --time=24:00:00 \
  --output="${WORK}/logs/meld_t1only_slurm.log" \
  --wrap "${APPTAINER} 'cd /app && source /opt/freesurfer-7.2.0/FreeSurferEnv.sh && python scripts/new_patient_pipeline/new_pt_pipeline.py -id sub-002 && python scripts/new_patient_pipeline/new_pt_pipeline.py -id sub-036' > ${WORK}/logs/meld_t1only.log 2>&1")"
echo "meld (T1-only) -> ${MELD_ID}"

submit_register() {
  local sub="$1" dep="$2"
  local dep_arg=()
  [[ -n "$dep" ]] && dep_arg=(--dependency="afterok:${dep}")
  sbatch --parsable \
    --job-name="reg_${sub}" \
    --partition=general \
    --mem=16G --cpus-per-task=2 --time=2:00:00 \
    "${dep_arg[@]}" \
    --output="${WORK}/logs/register_${sub}_t1only_slurm.log" \
    --wrap "${APPTAINER} 'cd /app && source /opt/freesurfer-7.2.0/FreeSurferEnv.sh && bash /pipeline/pet_register_in_container.sh ${sub} deficit -1.5' > ${WORK}/logs/register_${sub}_t1only.log 2>&1"
}

submit_visualize() {
  local sub="$1" dep="$2"
  sbatch --parsable \
    --job-name="viz_${sub}" \
    --partition=general \
    --mem=8G --cpus-per-task=1 --time=0:30:00 \
    --dependency="afterok:${dep}" \
    --output="${WORK}/logs/visualize_${sub}_t1only_slurm.log" \
    --wrap "${APPTAINER} 'cd /app && source /opt/freesurfer-7.2.0/FreeSurferEnv.sh && python /pipeline/pet_visualize.py ${sub} /data/output/fs_outputs/${sub}/mri/T1.mgz /data/output/pet_aligned/${sub}/prediction_in_meld.nii.gz /data/output/pet_aligned/${sub}/pet_in_meld.nii.gz /data/output/pet_aligned/${sub}/figures' > ${WORK}/logs/visualize_${sub}_t1only.log 2>&1 && touch ${WORK}/output/pet_aligned/${sub}/figures/.done"
}

reg_ids=()
viz_ids=()
for sub in "${MELD_SUBS[@]}"; do
  reg_id="$(submit_register "${sub}" "${MELD_ID}")"
  echo "register ${sub} -> ${reg_id} (after ${MELD_ID})"
  reg_ids+=("${reg_id}")
  viz_id="$(submit_visualize "${sub}" "${reg_id}")"
  echo "visualize ${sub} -> ${viz_id} (after ${reg_id})"
  viz_ids+=("${viz_id}")
done

agg_dep="$(IFS=:; echo "afterok:${viz_ids[*]}")"
sbatch --parsable \
  --job-name="meldpet_agg_t1" \
  --partition=general \
  --mem=4G --cpus-per-task=1 --time=0:15:00 \
  --dependency="${agg_dep}" \
  --output="${WORK}/logs/aggregate_t1only_slurm.log" \
  --wrap "python3 - <<'PY'
import pandas as pd
from pathlib import Path
work = Path('${WORK}/output')
subs = ['sub-002','sub-036','sub-065']
asym_thr = -8.0
dice_thr = 0.10
frames = [pd.read_csv(work/'pet_aligned'/s/f'pet_in_clusters_{s}.csv') for s in subs]

def call_row(r):
    asym = pd.to_numeric(r.get('roi_asym_pct'), errors='coerce')
    dice = pd.to_numeric(r.get('dice_abnormal'), errors='coerce')
    tracer_ok = pd.notna(asym) and asym <= asym_thr
    spat = pd.notna(dice) and dice >= dice_thr
    return pd.Series({'tracer_concordant': bool(tracer_ok), 'spatial_concordant': bool(spat),
        'concordance_call': ('concordant' if (tracer_ok and spat) else 'partial' if (tracer_ok or spat) else 'discordant')})

cohort = pd.concat(frames, ignore_index=True)
cohort = pd.concat([cohort, cohort.apply(call_row, axis=1)], axis=1)
cohort['pipeline_version'] = 'meld_graph_v2.2.4'
out = work/'pet_cohort_stats.csv'
cohort.to_csv(out, index=False)
print(f'wrote {out}')
PY"

echo "aggregate submitted (${agg_dep})"
