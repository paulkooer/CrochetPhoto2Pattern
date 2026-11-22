# state-restore area — working notes (Fable reviewer)

Audited tree: <repo> @ 6c88b7df5d53c18d4c8190288419faeb02cc1b13
Scratch: eval_outputs/fable52-system-audit-20261117-fable-review/repro/state-restore/

## Log
- read REVIEW_BRIEF §2/§4/§5.A/§5.E/§5.F.
- read in full: services/{result_logic,progress_state,migrations,workspace,color_identity}.py,
  models/{result_metadata,trial_draft}.py, utils/{project,backup,share,history,provenance,exporters,
  pdf_export,output_files,trial_history,trial_bundle}.py, ui/{result_renderer,result_progress,edit_history,
  export_cache,project_save,backup_import,workspace,result_assembly,pattern_editor,sidebar,trial_editor,
  trial_review,tab_photo,tab_manual,photo_review}.py, main.py, schemas.py, docs/project-format.md
- ran q4_roundtrip.py (x2, identical), q1_q2_apptest.py, q3_q5.py, q2b_fresh_manual_noop.py; outputs in *.out
- finding F1: manual-tab result has top-level gauge=None -> revision changes on first import/normalisation;
  trial created on it immediately reports "pattern differs" and disables measured-gauge recalculation.
