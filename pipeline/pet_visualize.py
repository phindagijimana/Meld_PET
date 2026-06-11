#!/usr/bin/env python3
"""
pet_visualize.py — runs INSIDE the MELD container (nilearn + matplotlib).

Headless overlay PNGs after MELD + PET registration:
  1. prediction_on_T1.png
  2. pet_on_T1.png
  3. pet_with_pred.png

Usage:
  pet_visualize.py <subject> <T1.mgz> <prediction.nii.gz> <pet_in_meld.nii.gz> <out_dir>
"""
import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import nibabel as nib
from nilearn import plotting, image


def lesion_cut_coords(pred_img):
    data = np.asarray(pred_img.get_fdata())
    mask = data > 0
    if not mask.any():
        return None
    ijk = np.array(np.where(mask)).mean(axis=1)
    xyz = nib.affines.apply_affine(pred_img.affine, ijk)
    return tuple(xyz)


def require_file(path, label):
    if not os.path.isfile(path):
        print(f"[viz][ERROR] missing {label}: {path}", file=sys.stderr)
        return False
    return True


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        return 1
    subject, t1_path, pred_path, pet_path, out_dir = sys.argv[1:6]
    os.makedirs(out_dir, exist_ok=True)

    if not require_file(t1_path, "T1"):
        return 1

    written = []
    t1 = image.load_img(t1_path)
    has_pred = require_file(pred_path, "prediction")
    has_pet = require_file(pet_path, "PET")
    pred = image.load_img(pred_path) if has_pred else None
    cut = lesion_cut_coords(pred) if has_pred else None
    disp_mode = "ortho"

    if has_pred:
        out = os.path.join(out_dir, f"{subject}_prediction_on_T1.png")
        d = plotting.plot_roi(
            image.math_img("img > 0", img=pred), bg_img=t1,
            cut_coords=cut, display_mode=disp_mode, title=f"{subject}: MELD prediction",
            cmap="autumn", alpha=0.7, black_bg=True)
        d.savefig(out, dpi=150)
        d.close()
        written.append(out)
        print(f"[viz] wrote {out}")

    if has_pet:
        pet = image.load_img(pet_path)
        out = os.path.join(out_dir, f"{subject}_pet_on_T1.png")
        d = plotting.plot_stat_map(
            pet, bg_img=t1, cut_coords=cut, display_mode=disp_mode,
            title=f"{subject}: PET in MELD space", cmap="hot",
            colorbar=True, black_bg=True)
        if has_pred and cut is not None:
            d.add_contours(image.math_img("img > 0", img=pred),
                           levels=[0.5], colors="lime", linewidths=1.5)
        d.savefig(out, dpi=150)
        d.close()
        written.append(out)
        print(f"[viz] wrote {out}")

        if has_pred and cut is not None:
            out = os.path.join(out_dir, f"{subject}_pet_with_pred.png")
            d = plotting.plot_stat_map(
                pet, bg_img=t1, display_mode="z", cut_coords=6,
                title=f"{subject}: PET @ lesion", cmap="hot",
                colorbar=True, black_bg=True)
            d.add_contours(image.math_img("img > 0", img=pred),
                           levels=[0.5], colors="lime", linewidths=1.5)
            d.savefig(out, dpi=150)
            d.close()
            written.append(out)
            print(f"[viz] wrote {out}")
    elif has_pred:
        print("[viz] no pet_in_meld.nii.gz — prediction figure only")

    if not written:
        print("[viz][ERROR] no figures produced", file=sys.stderr)
        return 1

    print(f"[viz] DONE: {len(written)} figure(s) in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
