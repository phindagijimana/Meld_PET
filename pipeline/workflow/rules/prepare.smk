# prepare.smk — stage T1w/FLAIR into MELD input tree and BIDS-style data/ layout.
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

        if params.flair and os.path.isfile(params.flair):
            fdir = os.path.join(params.work, "input", sub, "FLAIR")
            os.makedirs(fdir, exist_ok=True)
            shutil.copyfile(params.flair, os.path.join(fdir, f"{sub}_FLAIR.nii.gz"))
            shutil.copyfile(params.flair, os.path.join(anat, f"{sub}_{ses}_FLAIR.nii.gz"))
