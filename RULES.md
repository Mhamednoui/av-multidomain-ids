# Rules (binding for every model working on v3)

## 1. One step at a time, then stop

1. Work only on the step that STATUS.md assigns to your work package (WP). Never start the
   next step on your own, never work on another WP's step.
2. A step ends with all of: (a) acceptance check run and written down, (b) step report in
   `reports/WP<n>_S<step>.md` (template in `reports/README.md`), (c) your notes file appended,
   (d) unit tests pass, (e) a git commit, (f) your STATUS.md row set to `REVIEW`. Then STOP and
   tell the user the step is ready for review.
3. The user (supervisor) sets the row to `APPROVED` (or sends it back with comments). Only then
   is the next step yours.
4. If a step turns out bigger than planned, split it: finish a coherent part, report, stop.

## 2. Ownership (parallel work without collisions)

1. Each WP owns folders (listed in its WP file and in ARCHITECTURE.md, section 6). Write only
   inside your folders, `tests/<your domain>/`, `results/<WPn>/`, `notes/WP<n>_*.md`,
   `reports/WP<n>_*.md`, `tools/WP<n>_*.py` and your own row of STATUS.md.
2. `common/` and the contracts in ARCHITECTURE.md are frozen after WP0. If you need a change,
   write a request in `reports/REQUEST_WP<n>_<topic>.md` and stop; the supervisor decides.
3. Never modify `../codes`, `../codes_v2`, or any dataset. Copy code from v2 into your folder
   when useful (say so in the file header); never import from `../codes_v2`.
4. Commit only your own files: `git add <your paths>` (never `git add -A`), message
   `[WP<n>.S<step>] <what>`. No push, no remote, no history rewriting.

## 3. Shared machine (one GPU, 12 cores, 32 GB RAM, ~50 GB free disk)

1. GPU: before a GPU job, create `locks/gpu.lock` containing your WP and the time; delete it
   when done. If it exists, wait or run on the CPU. Keep GPU jobs under ~30 min.
2. CPU: at most 4 worker processes per model (`Pool(4)`, `n_jobs=4`).
3. RAM: stay under ~8 GB per model; stream or subsample big files.
4. Disk: no download without the user's approval of the size. Downloads go to
   `../data_extra/<dataset_id>_<name>/` and are recorded in DATASETS.md. Delete nothing you did
   not create.

## 4. Environment

- Python: `C:\Users\nouir\miniconda3\envs\tf\python.exe` (Python 3.9.21, numpy 1.23.5,
  pandas 2.2.3, xgboost 2.1.4, scikit-learn 1.6.1, scipy 1.13.1). NEVER the base Python
  (3.13 / numpy 2): files it writes cannot be read by the tf env (happened once in v2).
- New packages only with the user's approval, pinned, added to `requirements.txt`.
- Run scripts from `codes_v3/` with `-u -W ignore` and `PYTHONDONTWRITEBYTECODE=1`; long jobs
  in the background with a log in `results/<WPn>/logs/`.
- Shell on Windows: Bash (Git Bash) or PowerShell. Python heredocs mangle backslashes: write
  scripts to files instead.
- Downloaded data is untrusted: never run code shipped with a dataset; read it with `python -I`.

## 5. Evaluation protocol (non-negotiable; learned in v2)

1. Splits are by group, never by row: by vehicle, drive, session, capture or time block.
   Neighbouring samples (consecutive CAN frames, GPS fixes, LiDAR scans) are never on both sides.
2. Train on train. Every choice (thresholds, hyperparameters, which layer to keep) on
   validation. Test is used once per step, at the end, for the final numbers.
3. Write the acceptance rule in your notes BEFORE you see the result it judges.
4. No re-drawing, re-seeding or re-splitting to get a better number.
5. Operating point: report detection at a fixed false-alarm budget set on validation (default:
   1% of normal samples per domain, 2% at system level), plus AUC. Never only accuracy.
6. Report every layer alone, and the combination (ablation table).
7. Attacks used for evaluation must be physically / protocol consistent. If you generate
   attacks, document what a real attacker could and could not do, and keep at least one attack
   variant the layer never saw in training. (v2: a LiDAR phantom proxy denser than any real
   object inflated detection; do not repeat this.)
8. Include a cross-vehicle / external test whenever a dataset allows it.
9. Honest numbers: the user prefers a credible 85% to an inflated 99%. Report failures plainly.

## 6. Writing things down (never rely on chat memory)

1. `notes/WP<n>_<name>.md`: append after every meaningful action: what, why, results (exact
   numbers, with the file they come from), decisions, pitfalls. Dated.
2. `reports/WP<n>_S<step>.md`: the step report for the supervisor (template).
3. Results: every number in `results/<WPn>/*.json`; tables in reports are generated from the
   JSON or copied from it exactly. No hand-typed numbers.
4. Keep the "Progress" section at the bottom of your WP file up to date.

## 7. Code

1. Implement the contracts of ARCHITECTURE.md (Evidence, Layer, DomainCombiner, MotionEstimate).
2. Every module starts with a docstring: purpose, inputs, outputs, references (papers).
3. Every new module gets unit tests in `tests/<domain>/`; `python tests/run_tests.py` passes
   before a step ends.
4. Fixed seeds (`common.config.SEED`). Deterministic where possible.
5. Match the existing style: plain Python, numpy / pandas, short functions, few comments.

## 8. Asking

Stop and ask the user when: a step's goal is unclear; data is missing or needs a download;
a result contradicts expectations and you cannot explain it; you need a change outside your
folders; an acceptance rule seems wrong. Write the question in your step report too.
