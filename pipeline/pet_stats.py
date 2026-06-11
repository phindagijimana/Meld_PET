#!/usr/bin/env python3
"""
pet_stats.py — runs INSIDE the MELD container (numpy + nibabel).

Quantitative PET ↔ MELD-prediction statistics in MELD's conformed grid:

  per cluster (and 'all_clusters'):
    - raw PET       : mean / std / median, volume
    - gm_z          : GM-normalized z-score
    - host_roi      : dominant FreeSurfer region
    - roi_asym_pct  : ROI-level L↔R asymmetry
    - cluster_mirror_* : lesion-shape mirror asymmetry
    - frac_abnormal : fraction of cluster voxels abnormal vs GM (tracer-aware)
    - dice_abnormal : Dice(cluster, abnormal cortical GM) [concordance]

tracer_mode:
  deficit — lower uptake is abnormal (e.g. FDG hypometabolism); z < abnormal_z
  excess  — higher uptake is abnormal; z > |abnormal_z|

Usage:
  pet_stats.py <subject> <pet_in_meld.nii.gz> <prediction.nii.gz> <aparc+aseg.mgz> \\
               <out_csv> [tracer_mode] [abnormal_z]
"""
import sys
import os
import csv
import numpy as np
import nibabel as nib

ABNORMAL_Z_DEFAULT = -1.5


def load_like(path, ref_img):
    img = nib.load(path)
    if img.shape[:3] == ref_img.shape[:3] and np.allclose(img.affine, ref_img.affine, atol=1e-3):
        return np.asarray(img.get_fdata())
    try:
        from nilearn.image import resample_to_img
        resampled = resample_to_img(img, ref_img, interpolation="nearest")
    except Exception as exc:
        raise RuntimeError(
            f"could not resample {os.path.basename(path)} onto PET grid: {exc}"
        ) from exc
    out = resampled if hasattr(resampled, "get_fdata") else resampled
    data = np.asarray(out.get_fdata() if hasattr(out, "get_fdata") else out)
    if data.shape[:3] != ref_img.shape[:3]:
        raise RuntimeError(
            f"{os.path.basename(path)} shape {data.shape[:3]} != PET {ref_img.shape[:3]}"
        )
    return data


def is_cortical(lbl):
    lbl = int(lbl)
    return (1000 <= lbl <= 1035) or (2000 <= lbl <= 2035) or \
           (11100 <= lbl <= 11175) or (12100 <= lbl <= 12175)


def homologue(lbl):
    lbl = int(lbl)
    if (1000 <= lbl <= 1035) or (11100 <= lbl <= 11175):
        return lbl + 1000
    if (2000 <= lbl <= 2035) or (12100 <= lbl <= 12175):
        return lbl - 1000
    return None


def load_lut():
    fs = os.environ.get("FREESURFER_HOME", "")
    path = os.path.join(fs, "FreeSurferColorLUT.txt")
    lut = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    lut[int(parts[0])] = parts[1]
    except Exception:
        pass
    return lut


def pct_asym(a, b):
    if a is None or b is None:
        return ""
    denom = (a + b) / 2.0
    if denom == 0:
        return ""
    return round((a - b) / denom * 100.0, 2)


def lr_axis(affine):
    cosines = np.abs(affine[:3, :3] @ np.array([1.0, 0.0, 0.0]))
    return int(np.argmax(cosines))


def mirror_asym_index(a, b):
    if a is None or b is None:
        return ""
    denom = a + b
    if denom == 0:
        return ""
    return round((a - b) / denom, 4)


def abnormal_mask(gm_mask, z, tracer_mode, abnormal_z):
    if tracer_mode == "excess":
        thr = abs(abnormal_z)
        return gm_mask & (z > thr)
    return gm_mask & (z < abnormal_z)


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        return 1
    subject, pet_path, pred_path, aparc_path, out_csv = sys.argv[1:6]
    tracer_mode = sys.argv[6] if len(sys.argv) > 6 else "deficit"
    abnormal_z = float(sys.argv[7]) if len(sys.argv) > 7 else ABNORMAL_Z_DEFAULT
    if tracer_mode not in ("deficit", "excess"):
        print(f"[stats][ERROR] unknown tracer_mode: {tracer_mode}", file=sys.stderr)
        return 1

    pet_img = nib.load(pet_path)
    pet = np.asarray(pet_img.get_fdata())
    pred = load_like(pred_path, pet_img)
    if not np.any(pred > 0):
        print(f"[stats] no lesion voxels in {os.path.basename(pred_path)}")
    vox = float(abs(np.linalg.det(pet_img.affine[:3, :3])))

    have_aparc = os.path.isfile(aparc_path)
    if have_aparc:
        aparc = load_like(aparc_path, pet_img).astype(int)
        cortical = np.vectorize(is_cortical)(aparc) if aparc.size else np.zeros_like(aparc, bool)
        gm_mask = cortical & np.isfinite(pet)
        gm_vals = pet[gm_mask]
        gm_mean = float(np.mean(gm_vals)) if gm_vals.size else float("nan")
        gm_sd = float(np.std(gm_vals)) if gm_vals.size else float("nan")
        abn_gm = np.zeros_like(pet, bool)
        if gm_sd and np.isfinite(gm_sd) and gm_sd > 0:
            z = (pet - gm_mean) / gm_sd
            abn_gm = abnormal_mask(gm_mask, z, tracer_mode, abnormal_z)
        lut = load_lut()
    else:
        print(f"[stats][WARN] aparc+aseg not found ({aparc_path}); ROI/GM metrics skipped")
        gm_mean = gm_sd = float("nan")
        abn_gm = np.zeros_like(pet, bool)
        aparc = None
        lut = {}

    labels = np.unique(pred[pred > 0]).astype(int)
    lr_ax = lr_axis(pet_img.affine)
    rows = []

    def roi_mean(lbl):
        if aparc is None or lbl is None:
            return None
        m = (aparc == int(lbl)) & np.isfinite(pet)
        return float(np.mean(pet[m])) if m.any() else None

    def summarize(name, mask):
        vals = pet[mask & np.isfinite(pet)]
        n = int(vals.size)
        row = {"subject": subject, "cluster": name, "n_voxels": n,
               "volume_mm3": round(n * vox, 1), "tracer_mode": tracer_mode}
        if n:
            pmean = float(np.mean(vals))
            row.update({
                "pet_mean": round(pmean, 4),
                "pet_std": round(float(np.std(vals)), 4),
                "pet_median": round(float(np.median(vals)), 4),
                "gm_z": round((pmean - gm_mean) / gm_sd, 3) if (gm_sd and np.isfinite(gm_sd) and gm_sd > 0) else "",
            })
            host = host_name = ipsi = contra = ""
            roi_asym = clus_vs_contra = ""
            if aparc is not None:
                labs = aparc[mask]
                labs = labs[np.vectorize(is_cortical)(labs)] if labs.size else labs
                if labs.size:
                    host = int(np.bincount(labs).argmax())
                    host_name = lut.get(host, str(host))
                    h = homologue(host)
                    ipsi = roi_mean(host)
                    contra = roi_mean(h)
                    roi_asym = pct_asym(ipsi, contra)
                    clus_vs_contra = pct_asym(pmean, contra)
            mirror_mask = np.flip(mask, axis=lr_ax)
            mirror_vals = pet[mirror_mask & np.isfinite(pet)]
            mirror_contra = float(np.mean(mirror_vals)) if mirror_vals.size else None
            mirror_ai = mirror_asym_index(pmean, mirror_contra)
            frac_abn = round(float(np.mean(abn_gm[mask])), 3) if mask.any() else ""
            inter = int(np.sum(mask & abn_gm))
            dice = round(2 * inter / (int(mask.sum()) + int(abn_gm.sum())), 3) if (mask.sum() + abn_gm.sum()) else ""
            row.update({
                "host_roi": host, "host_roi_name": host_name,
                "ipsi_roi_pet": round(ipsi, 4) if isinstance(ipsi, float) else "",
                "contra_roi_pet": round(contra, 4) if isinstance(contra, float) else "",
                "roi_asym_pct": roi_asym,
                "cluster_vs_contra_pct": clus_vs_contra,
                "cluster_mirror_ipsi_pet": round(pmean, 4),
                "cluster_mirror_contra_pet": round(mirror_contra, 4) if isinstance(mirror_contra, float) else "",
                "cluster_mirror_ai": mirror_ai,
                "frac_abnormal": frac_abn, "dice_abnormal": dice,
            })
        return row

    if labels.size:
        rows.append(summarize("all_clusters", pred > 0))
        for lab in labels:
            rows.append(summarize(f"cluster_{lab}", pred == lab))
    else:
        rows.append({"subject": subject, "cluster": "none", "n_voxels": 0,
                     "volume_mm3": 0, "tracer_mode": tracer_mode})

    fields = ["subject", "cluster", "n_voxels", "volume_mm3", "tracer_mode",
              "pet_mean", "pet_std", "pet_median", "gm_z",
              "host_roi", "host_roi_name", "ipsi_roi_pet", "contra_roi_pet",
              "roi_asym_pct", "cluster_vs_contra_pct",
              "cluster_mirror_ipsi_pet", "cluster_mirror_contra_pet", "cluster_mirror_ai",
              "frac_abnormal", "dice_abnormal"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"[stats] GM mean={gm_mean:.4f} sd={gm_sd:.4f} mode={tracer_mode} | "
          f"{len(labels)} cluster(s); wrote {out_csv}")
    for r in rows:
        print("[stats]  ", {k: r.get(k, "") for k in
                            ("cluster", "n_voxels", "pet_mean", "gm_z", "roi_asym_pct",
                             "cluster_mirror_ai", "frac_abnormal", "dice_abnormal")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
