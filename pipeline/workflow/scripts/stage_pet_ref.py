#!/usr/bin/env python3
"""
stage_pet_ref.py — locate a PETPrep derivative in T1w space and copy to work/pet/.

Runs on the HOST after PETPrep completes (not inside a container).

Selects *desc-preproc_pet* in T1w space (never brain_mask / petref). Prefers the
requested BIDS session; if PET lives in another session, falls back with a warning.
"""
import argparse
import glob
import os
import shutil
import sys


def _basename(path):
    return os.path.basename(path)


def _is_preproc_t1w_pet(path):
    name = _basename(path)
    if "desc-preproc_pet" not in name:
        return False
    if "space-T1w" not in name and "space-" not in name:
        return False
    if "brain_mask" in name or "_petref" in name:
        return False
    return True


def _collect_candidates(petprep_out, sub, session, glob_tpl):
    rel = glob_tpl.format(sub=sub, session=session)
    pattern = os.path.join(petprep_out, rel)
    hits = sorted(glob.glob(pattern))
    if hits:
        return hits

    # PETPrep inserts tracer/recording entities: sub-XXX_ses-N_trc-..._space-T1w_...
    session_pat = os.path.join(
        petprep_out, sub, session, "pet",
        f"{sub}_*_space-*T1w*desc-preproc_pet*.nii.gz",
    )
    hits = sorted(glob.glob(session_pat))
    if hits:
        return hits

    fallback = os.path.join(
        petprep_out, sub, "**", "pet", f"{sub}_*_space-*T1w*desc-preproc_pet*.nii.gz"
    )
    return sorted(glob.glob(fallback, recursive=True))


def pick_pet_ref(candidates, session):
    preproc = [p for p in candidates if _is_preproc_t1w_pet(p)]
    if not preproc:
        return None, "no desc-preproc_pet in T1w space among candidates"

    sess_tag = f"/{session}/"
    in_sess = [p for p in preproc if sess_tag in p.replace("\\", "/")]
    if in_sess:
        return sorted(in_sess)[0], ""

    chosen = sorted(preproc)[0]
    alt_ses = next(
        (p for p in chosen.replace("\\", "/").split("/") if p.startswith("ses-")),
        "",
    )
    note = f"PET found under {alt_ses}, requested {session}" if alt_ses else ""
    return chosen, note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--petprep-out", required=True)
    ap.add_argument("--glob-tpl", required=True)
    ap.add_argument("--dest", required=True)
    args = ap.parse_args()

    candidates = _collect_candidates(
        args.petprep_out, args.sub, args.session, args.glob_tpl
    )
    if not candidates:
        print(
            f"[stage_pet_ref][ERROR] no PET candidates for {args.sub} "
            f"(session {args.session}) under {args.petprep_out}",
            file=sys.stderr,
        )
        return 1

    src, note = pick_pet_ref(candidates, args.session)
    if not src:
        print(f"[stage_pet_ref][ERROR] {args.sub}: {note}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.dest)), exist_ok=True)
    shutil.copyfile(src, args.dest)
    print(f"[stage_pet_ref] {args.sub}: {src} -> {args.dest}")
    if note:
        print(f"[stage_pet_ref][WARN] {args.sub}: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
