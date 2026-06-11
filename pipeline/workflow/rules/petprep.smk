# petprep.smk — run PETPrep per subject, then stage the T1w-space PET reference.
rule petprep:
    input:
        t1=meld_input_t1("{sub}"),
    output:
        pet=pet_staged("{sub}"),
        flag=petprep_flag("{sub}"),
    params:
        ses=lambda wc: SAMPLES[wc.sub]["session"],
        cmd=lambda wc: petprep_cmd(wc.sub),
        glob_tpl=config.get(
            "petprep_ref_glob",
            "{sub}/{session}/pet/{sub}_{session}_space-*T1w*desc-*pet*.nii.gz",
        ),
        petprep_out=PETPREP_OUT,
        stage_script=os.path.join(PIPELINE_DIR, "workflow", "scripts", "stage_pet_ref.py"),
    log:
        os.path.join(LOG_DIR, "petprep_{sub}.log"),
    resources:
        mem_mb=res("petprep", "mem_mb", 32000),
        runtime=res("petprep", "runtime", 480),
        cpus_per_task=res("petprep", "cpus_per_task", 4),
    shell:
        """
        set -euo pipefail
        mkdir -p "$(dirname {output.flag})" "$(dirname {output.pet})"
        {params.cmd} > {log} 2>&1
        python {params.stage_script} \
            --sub {wildcards.sub} \
            --session {params.ses} \
            --petprep-out {params.petprep_out} \
            --glob-tpl '{params.glob_tpl}' \
            --dest {output.pet}
        touch {output.flag}
        """
