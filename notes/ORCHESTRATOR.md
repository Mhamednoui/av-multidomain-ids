# Orchestrator log (supervisor decisions, assignments, approvals)

## 2026-10-20: v3 set up (by the session that built v2)

Context for the next orchestrator session:
- User: Mhamed Nouira (EPT, thesis defended 17 Oct 2026). Works in VS Code on Windows.
- User preferences (keep): honest, non-overfitted numbers ("a credible 85% beats an inflated
  99%"); write everything down in files, never rely on chat memory; one step at a time with a
  stop for review; save the orchestrator's context (workers do the work, orchestrator monitors,
  assigns, evaluates); no GitHub push without explicit approval; ask before downloads (sizes).
- User's request for v3 (20 Oct): make each domain detector smarter with logic, physics and
  parallel models, because any model is only as good as its dataset; add a real V2X dataset;
  full system re-programming / retraining if needed; detailed roadmap so any model knows where
  it is and what to do; multi-agent work supervised by the orchestrator.
- History: v1 = thesis code (../codes). v2 = leak-free re-evaluation (../codes_v2;
  NOTES_v2.md = full log; RESULTS_v2.md = numbers). v2 is committed on a LOCAL branch `v2` in
  C:\Users\nouir\PFE_github\av-multidomain-ids (commits 24c7d75, a381336, abf7579, 2525467;
  tag thesis-v1), NOT pushed.
- Written today: START_HERE, RULES, ROADMAP, ARCHITECTURE, DATASETS, STATUS, ORCHESTRATION,
  workpackages/WP0-WP7, reports/README. Folders created (empty): common, gps, can, lidar,
  network, v2x, crossdomain, fusion, system, tools, tests, results, locks, notes, reports.
  NOT done yet (WP0 S1): git init, requirements.txt, any code.
- Dataset research done (20 Oct, web): see DATASETS.md. No download made for v3 yet.
  Disk free 51.9 GB.

Open questions for the user at the start of the next session:
1. Approval mode: user approves every step, or orchestrator approves routine steps?
2. Go for WP0 S1.

## Assignments and approvals
(orchestrator appends: date, WP, step, worker, decision, comment)

2026-10-19, user decisions (orchestrator session):
- Approval mode: orchestrator approves routine steps (after the ORCHESTRATION.md section 3
  checklist); the user is consulted for milestones, downloads, failures and contract changes.
- WP0 S1: on hold. Do not assign until the user says go.
- Workers: model Sonnet 5.5 (`model: "sonnet"` in the Agent call). Run several workers in
  parallel whenever the dependency order allows (max 3, one GPU-heavy at a time).
  ORCHESTRATION.md section 2 updated accordingly.
- 2026-10-19 user: "start, let the workers do all the work: downloads, programming, everything;
  I want results." => Downloads are pre-approved (orchestrator checks size/licence and keeps
  >= 15 GB disk free; logs each one here). Orchestrator approves steps and chains them without
  waiting for the user; user is told about milestones and real failures only.
  No GitHub push (still needs explicit approval).

| Date | WP | Step | Model | Decision | Comment |
|---|---|---|---|---|---|
| 2026-10-19 | WP0 | S1 | sonnet | ASSIGNED | first step |
