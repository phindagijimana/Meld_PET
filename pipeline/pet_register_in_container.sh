#!/bin/bash
# ---------------------------------------------------------------------------
# pet_register_in_container.sh
#
# Runs INSIDE the MELD apptainer image. Registers PET into MELD conformed-T1
# space (T1.mgz grid), resamples prediction.nii.gz from native T1w space onto
# that same grid, then computes PET<->MELD stats.
#
# Usage:
#   pet_register_in_container.sh <subject_id> [tracer_mode] [abnormal_z]
#     tracer_mode: deficit (default) | excess
# ---------------------------------------------------------------------------
set -euo pipefail

SUBJECT="${1:?subject id required}"
TRACER_MODE="${2:-deficit}"
ABNORMAL_Z="${3:-}"

DATA=/data
FS_SUBJECTS="${DATA}/output/fs_outputs"
PRED_DIR="${DATA}/output/predictions_reports/${SUBJECT}/predictions"
PET_IN="${DATA}/pet/${SUBJECT}_pet.nii.gz"
OUT_DIR="${DATA}/output/pet_aligned/${SUBJECT}"

T1_MGZ="${FS_SUBJECTS}/${SUBJECT}/mri/T1.mgz"
PRED_NII="${PRED_DIR}/prediction.nii.gz"

REG_LTA="${OUT_DIR}/pet_to_meldT1.lta"
PET_OUT="${OUT_DIR}/pet_in_meld.nii.gz"
PRED_IN_MELD="${OUT_DIR}/prediction_in_meld.nii.gz"
STATS_CSV="${OUT_DIR}/pet_in_clusters_${SUBJECT}.csv"

echo "[register] subject=${SUBJECT} tracer_mode=${TRACER_MODE}"
echo "[register] PET in : ${PET_IN}"
echo "[register] T1 ref : ${T1_MGZ}"
echo "[register] pred   : ${PRED_NII}"

[[ -f "${PET_IN}" ]]  || { echo "[register][ERROR] missing PET: ${PET_IN}"; exit 2; }
[[ -f "${T1_MGZ}" ]]  || { echo "[register][ERROR] missing MELD T1: ${T1_MGZ}"; exit 2; }

mkdir -p "${OUT_DIR}"

echo "[register] mri_coreg (rigid, MI) ..."
mri_coreg \
    --mov "${PET_IN}" \
    --ref "${T1_MGZ}" \
    --reg "${REG_LTA}" \
    --dof 6

echo "[register] mri_vol2vol -> ${PET_OUT}"
mri_vol2vol \
    --mov "${PET_IN}" \
    --targ "${T1_MGZ}" \
    --lta "${REG_LTA}" \
    --o "${PET_OUT}" \
    --interp trilin

[[ -f "${PRED_NII}" ]] || { echo "[register][ERROR] no prediction.nii.gz — MELD must finish before stats"; exit 1; }

echo "[register] resample prediction -> ${PRED_IN_MELD} (native T1w -> T1.mgz)"
python - "$PRED_NII" "$T1_MGZ" "$PRED_IN_MELD" <<'PY'
import sys
import nibabel as nib
from nilearn.image import resample_to_img

pred_path, t1_path, out_path = sys.argv[1:4]
t1 = nib.load(t1_path)
pred = nib.load(pred_path)
out = resample_to_img(pred, t1, interpolation="nearest")
nib.save(out, out_path)
print(f"[register]   wrote {out_path} shape={out.shape[:3]}")
PY

if [[ -f "${PRED_IN_MELD}" ]]; then
    python - "$PET_OUT" "$PRED_IN_MELD" <<'PY'
import sys, numpy as np, nibabel as nib
a = nib.load(sys.argv[1]); b = nib.load(sys.argv[2])
same_shape = a.shape[:3] == b.shape[:3]
same_aff = np.allclose(a.affine, b.affine, atol=1e-3)
print(f"[register]   pet_in_meld shape={a.shape[:3]} prediction_in_meld shape={b.shape[:3]} -> shape_match={same_shape}")
print(f"[register]   affine_match={same_aff}")
if not (same_shape and same_aff):
    print("[register][WARNING] grids differ; overlay may be misaligned")
PY
else
    echo "[register][ERROR] no prediction_in_meld.nii.gz after resample"
    exit 1
fi

APARC="${FS_SUBJECTS}/${SUBJECT}/mri/aparc+aseg.mgz"
echo "[register] computing PET<->prediction stats -> ${STATS_CSV}"
python /pipeline/pet_stats.py "${SUBJECT}" "${PET_OUT}" "${PRED_IN_MELD}" "${APARC}" \
    "${STATS_CSV}" "${TRACER_MODE}" ${ABNORMAL_Z} \
    || { echo "[register][ERROR] pet_stats.py failed"; exit 1; }

echo "[register] DONE: ${PET_OUT}"
echo "[register] STATS: ${STATS_CSV}"
