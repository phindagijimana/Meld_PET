#!/usr/bin/env bash
# Rerun register -> visualize -> aggregate for all cohort subjects (grid-fix rerun).
set -euo pipefail

WORK="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/work"
PIPE="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/pipeline"
SIF="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/meld_graph_v2.2.4.sif"
FSL="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/freesurfer_license.txt"
ML="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/docker_version/meld_license.txt"
MODELS="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/models"
PARAMS="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_Graph/meld_graph/meld_data/meld_params"
CFG="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET/pipeline/config/config.yaml"

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

submit_register() {
  local sub="$1"
  sbatch --parsable \
    --job-name="reg_${sub}" \
    --partition=general \
    --mem=16G --cpus-per-task=2 --time=2:00:00 \
    --output="${WORK}/logs/register_${sub}_slurm.log" \
    --wrap "${APPTAINER} 'cd /app && source /opt/freesurfer-7.2.0/FreeSurferEnv.sh && bash /pipeline/pet_register_in_container.sh ${sub} deficit -1.5' > ${WORK}/logs/register_${sub}.log 2>&1"
}

submit_visualize() {
  local sub="$1" dep="$2"
  sbatch --parsable \
    --job-name="viz_${sub}" \
    --partition=general \
    --mem=8G --cpus-per-task=1 --time=0:30:00 \
    --dependency="afterok:${dep}" \
    --output="${WORK}/logs/visualize_${sub}_slurm.log" \
    --wrap "${APPTAINER} 'cd /app && source /opt/freesurfer-7.2.0/FreeSurferEnv.sh && python /pipeline/pet_visualize.py ${sub} /data/output/fs_outputs/${sub}/mri/T1.mgz /data/output/pet_aligned/${sub}/prediction_in_meld.nii.gz /data/output/pet_aligned/${sub}/pet_in_meld.nii.gz /data/output/pet_aligned/${sub}/figures' > ${WORK}/logs/visualize_${sub}.log 2>&1 && mkdir -p ${WORK}/output/pet_aligned/${sub}/figures && touch ${WORK}/output/pet_aligned/${sub}/figures/.done"
}

viz_ids=()
for sub in sub-002 sub-036 sub-065; do
  mkdir -p "${WORK}/output/pet_aligned/${sub}/figures"
  reg_id="$(submit_register "${sub}")"
  echo "register ${sub} -> ${reg_id}"
  viz_id="$(submit_visualize "${sub}" "${reg_id}")"
  echo "visualize ${sub} -> ${viz_id} (after ${reg_id})"
  viz_ids+=("${viz_id}")
done

agg_dep="$(IFS=:; echo "afterok:${viz_ids[*]}")"
sbatch --parsable \
  --job-name="meldpet_agg" \
  --partition=general \
  --mem=4G --cpus-per-task=1 --time=0:15:00 \
  --dependency="${agg_dep}" \
  --output="${WORK}/logs/aggregate_slurm.log" \
  --wrap "cd /mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/Meld_PET && export PATH=\$HOME/.local/bin:\$PATH && meldpet --configfile ${CFG} aggregate > ${WORK}/logs/aggregate.log 2>&1"

echo "aggregate submitted (${agg_dep})"
