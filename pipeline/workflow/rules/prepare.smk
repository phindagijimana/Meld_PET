# prepare.smk — stage T1w into MELD input tree (and BIDS-style data/ layout).
# FLAIR is never staged when meld_t1_only is true (default).
rule prepare:
    input:
        t1=lambda wc: SAMPLES[wc.sub]["t1w"],
    output:
        t1=meld_input_t1("{sub}"),
    params:
        ses=lambda wc: SAMPLES[wc.sub]["session"],
        flair=lambda wc: SAMPLES[wc.sub].get("flair", ""),
        data=DATA,
        work=WORK,
    resources:
        mem_mb=res("prepare", "mem_mb", 4000),
        runtime=res("prepare", "runtime", 20),
        cpus_per_task=res("prepare", "cpus_per_task", 1),
    run:
        import os
        import shutil

        sub, ses = wildcards.sub, params.ses
        anat = os.path.join(params.data, sub, ses, "anat")
        os.makedirs(anat, exist_ok=True)
        os.makedirs(os.path.dirname(output.t1), exist_ok=True)

        shutil.copyfile(input.t1, output.t1)
        shutil.copyfile(input.t1, os.path.join(anat, f"{sub}_{ses}_T1w.nii.gz"))

        flair_dir = os.path.join(params.work, "input", sub, "FLAIR")
        flair_anat = os.path.join(anat, f"{sub}_{ses}_FLAIR.nii.gz")
        if config.get("meld_t1_only", True):
            if os.path.isdir(flair_dir):
                shutil.rmtree(flair_dir)
            if os.path.isfile(flair_anat):
                os.remove(flair_anat)
        elif params.flair and os.path.isfile(params.flair):
            os.makedirs(flair_dir, exist_ok=True)
            shutil.copyfile(params.flair, os.path.join(flair_dir, f"{sub}_FLAIR.nii.gz"))
            shutil.copyfile(params.flair, flair_anat)
