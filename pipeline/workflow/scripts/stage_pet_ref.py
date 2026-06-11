#!/usr/bin/env python3
"""
stage_pet_ref.py — locate a PETPrep derivative in T1w space and copy to work/pet/.

Runs on the HOST after PETPrep completes (not inside a container).
"""
import argparse
import glob
import os
import shutil
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--petprep-out", required=True)
    ap.add_argument("--glob-tpl", required=True)
    ap.add_argument("--dest", required=True)
    args = ap.parse_args()

    rel = args.glob_tpl.format(sub=args.sub, session=args.session)
    pattern = os.path.join(args.petprep_out, rel)
    hits = sorted(glob.glob(pattern))
    if not hits:
        # broader fallback: any T1w-space preproc PET for this subject
        fallback = os.path.join(
            args.petprep_out, args.sub, "**", "pet", f"{args.sub}_*space*T1w*.nii.gz"
        )
        hits = sorted(glob.glob(fallback, recursive=True))
    if not hits:
        print(f"[stage_pet_ref][ERROR] no PET reference matched: {pattern}", file=sys.stderr)
        return 1

    src = hits[0]
    os.makedirs(os.path.dirname(os.path.abspath(args.dest)), exist_ok=True)
    shutil.copyfile(src, args.dest)
    print(f"[stage_pet_ref] {args.sub}: {src} -> {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
