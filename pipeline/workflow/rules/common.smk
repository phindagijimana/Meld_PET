# common.smk — config, sample sheet, path templates, container command builders.
import os
import csv

WORK = config["work"]
DATA = config["data_dir"]
PIPELINE_DIR = config["pipeline_dir"]
LOG_DIR = os.path.join(WORK, "logs")
BIDS_ROOT = config["bids_root"]
PETPREP_OUT = config["petprep_out"]

SAMPLES = {}
with open(config["samples"]) as _fh:
    for _row in csv.DictReader(_fh, delimiter="\t"):
        SAMPLES[_row["bids_id"]] = _row
SUBJECTS = list(SAMPLES)

if not SUBJECTS:
    raise WorkflowError(
        f"No samples in {config['samples']}. Run `meldpet samples` first."
    )

wildcard_constraints:
    sub=r"sub-[A-Za-z0-9]+",


def meld_input_t1(sub):
    return os.path.join(WORK, "input", sub, "T1", f"{sub}_T1w.nii.gz")


def pet_staged(sub):
    return os.path.join(WORK, "pet", f"{sub}_pet.nii.gz")


def petprep_flag(sub):
    return os.path.join(WORK, "petprep_done", sub, ".done")


def meld_pred(sub):
    return os.path.join(WORK, "output", "predictions_reports", sub,
                        "predictions", "prediction.nii.gz")


def meld_t1mgz(sub):
    return os.path.join(WORK, "output", "fs_outputs", sub, "mri", "T1.mgz")


def pet_in_meld(sub):
    return os.path.join(WORK, "output", "pet_aligned", sub, "pet_in_meld.nii.gz")


def pet_stats_csv(sub):
    return os.path.join(WORK, "output", "pet_aligned", sub,
                        f"pet_in_clusters_{sub}.csv")


def viz_flag(sub):
    return os.path.join(WORK, "output", "pet_aligned", sub, "figures", ".done")


COHORT_CSV = os.path.join(WORK, "output", "pet_cohort_stats.csv")


def res(rule_name, key, default):
    return config.get("resources", {}).get(rule_name, {}).get(key, default)


def apptainer_cmd(inner):
    """Run a command inside the MELD apptainer image."""
    c = config
    binds = [
        f"{WORK}:/data",
        f'{c["models_src"]}:/data/models:ro',
        f'{c["meld_params_src"]}:/data/meld_params:ro',
        f'{c["fs_license"]}:/license.txt:ro',
        f'{c["meld_license"]}:/meld_license.txt:ro',
        f"{PIPELINE_DIR}:/pipeline:ro",
    ]
    bind_args = " ".join(f"--bind {b}" for b in binds)
    envs = (
        "--env FS_LICENSE=/license.txt "
        "--env MELD_LICENSE=/meld_license.txt "
        f'--env FREESURFER_HOME={c["freesurfer_home_in"]} '
        "--env PYTHONNOUSERSITE=1"
    )
    fsenv = f'source {c["freesurfer_home_in"]}/FreeSurferEnv.sh'
    return (
        f'{c["apptainer_bin"]} exec {bind_args} {envs} {c["sif"]} '
        f'/bin/bash -c "cd /app && {fsenv} && {inner}"'
    )


def petprep_cmd(sub):
    """Run PETPrep for one participant (BIDS App CLI inside PETPrep container)."""
    c = config
    work_pet = os.path.join(WORK, "petprep_work", sub)
    binds = [
        f"{BIDS_ROOT}:/data:ro",
        f"{PETPREP_OUT}:/out",
        f'{c["fs_license"]}:/license.txt:ro',
        f"{work_pet}:/work",
        f"{PIPELINE_DIR}:/pipeline:ro",
    ]
    bind_args = " ".join(f"--bind {b}" for b in binds)
    inner = (
        "petprep /data /out participant "
        f"--participant-label {sub} "
        "--fs-license-file /license.txt "
        "--work-dir /work "
        f"-v"
    )
    if c.get("petprep_use_apptainer", True):
        return (
            f'{c["apptainer_bin"]} exec {bind_args} '
            f'{c["petprep_sif"]} {inner}'
        )
    runner = c.get("petprep_container_bin", "docker")
    vol_args = " ".join(f"-v {b}" for b in binds)
    return (
        f"{runner} run --rm {vol_args} "
        f'{c.get("petprep_image", "ghcr.io/nipreps/petprep:0.0.6")} {inner}'
    )
