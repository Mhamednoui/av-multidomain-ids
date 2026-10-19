# START HERE (every model, every session)

This folder is **AV-IDS v3**: a multi-domain intrusion detection system for autonomous
vehicles (network, CAN, GPS, LiDAR, V2X) in which every domain detector is built from several
independent layers (rules, physics, normal-behaviour models, supervised models) instead of one
model trained on one dataset. Several models (AI assistants) work on it in parallel, each on
one work package; the user supervises and approves every step.

## Read, in this order, before doing anything

1. `RULES.md`: how we work. Binding for every model. Read all of it.
2. `STATUS.md`: where every work package stands, and which step is yours.
3. `workpackages/WP<n>_<name>.md`: your work package: scope, folders you own, steps,
   acceptance criteria. Do only the step marked as yours in STATUS.md.
4. `ARCHITECTURE.md`: the system and the contracts (interfaces) every package must respect.
5. `DATASETS.md`: datasets, where they are, licences, what still has to be downloaded.
6. `notes/WP<n>_<name>.md`: the log of your work package so far (what was done, decided, found).
7. `ROADMAP.md`: the big picture and the order of the work packages.

## Then

- Do exactly one step. At the end of it: write the step report in `reports/`, append to your
  notes file, commit, set your row in STATUS.md to `REVIEW`, and STOP. Tell the user the step is
  ready for review. Do not start the next step until the user says so.
- If something is unclear, contradicts these files, or would need a change outside your
  folders: stop and ask (see RULES.md, section "Asking").

## Background

- v1 = the defended thesis code (`../codes`, git tag `thesis-v1`). Never modify.
- v2 = leak-free re-evaluation (`../codes_v2`, results in `../codes_v2/RESULTS_v2.md`, log in
  `../codes_v2/NOTES_v2.md`). Never modify; copy code from it when useful.
- v3 starts from what v2 proved: learned models do not transfer between vehicles; physics and
  protocol checks do (`ROADMAP.md`, section 1).
