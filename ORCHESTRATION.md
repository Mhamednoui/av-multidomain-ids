# Orchestration: how the supervising session runs the workers

For the orchestrator (the Claude session the user talks to). The orchestrator does not write
code; it assigns steps to worker agents, reviews their results cheaply, keeps STATUS.md and
`notes/ORCHESTRATOR.md` current, and reports to the user in a few lines.

## 1. At the start of an orchestrator session

1. Read START_HERE.md, RULES.md, STATUS.md, ROADMAP.md, notes/ORCHESTRATOR.md. Skim
   ARCHITECTURE.md and the WP files only when needed (save context).
2. Ask the user (once, if not recorded in notes/ORCHESTRATOR.md): approval mode, i.e. does the
   user approve every step, or does the orchestrator approve routine steps and bring only
   milestones, downloads, failures and contract changes to the user?

## 2. Assigning a step

Launch one worker per step with the Agent tool: `subagent_type: "general-purpose"`,
`model: "sonnet"`, `effort: "medium"` (user decisions 2026-10-19: all workers run on Sonnet 5.5 at medium effort),
`run_in_background: true`, a short `description` like "WP1 S3 GPS EKF". No worktree needed
(folder ownership keeps workers apart, results stay in one place). Set the STATUS row to
`IN PROGRESS` and log the assignment in notes/ORCHESTRATOR.md.

Worker prompt template:

```
You are a worker on AV-IDS v3. Work package WP<n> (<name>), step S<k>.
Working directory: C:\Users\nouir\PFE\codes_v3
First read, in order: START_HERE.md, RULES.md, STATUS.md, workpackages/WP<n>_<name>.md,
ARCHITECTURE.md, DATASETS.md, notes/WP<n>_<name>.md (if it exists).
Then do step S<k> only, exactly as RULES.md says (acceptance rule written before results,
validation for choices, test once, report, notes, tests, commit of your own files only,
STATUS row to REVIEW, then stop).
Supervisor instructions for this step: <extra instructions or "none">.
Python: C:\Users\nouir\miniconda3\envs\tf\python.exe only.
Your final reply to me: at most 10 lines: what you did, key numbers vs the acceptance rule,
files written, problems / questions. Put everything else in your report and notes files.
```

Parallel workers: use several whenever the order allows (user decision 2026-10-19), at most 3 at a time; only one GPU-heavy step at a time (RULES 3.1). A step
that needs a download (S0) is covered by the user's pre-approval (RULES 3.4, 2026-10-19).

## 3. Reviewing a finished step (cheap, in this order)

1. Read the worker's 10-line reply and `reports/WP<n>_S<k>.md`.
2. Check the acceptance numbers against `results/WP<n>/*.json` (grep the exact keys).
3. Run `python tests/run_tests.py` (tf env).
4. `git log --stat -3` and `git status`: the worker changed only its own folders; nothing big
   (> 50 MB) committed; no files outside codes_v3 touched (check ../codes_v2 with git status there).
5. Protocol spot-check (one item): split by group? acceptance rule written before the result
   (timestamps in notes)? threshold from validation? attacks physically consistent?
6. Decide: `APPROVED` (set next step `TODO`), `CHANGES` (precise comment in the STATUS note
   and in notes/ORCHESTRATOR.md, then re-assign), or ask the user.
7. Tell the user in <= 5 lines.

Read code only when a check fails or a number looks too good (v2 lesson: suspiciously good =
leak or artefact until proven otherwise).

## 4. Context hygiene

- Keep only workers' short replies and your review notes in context; everything else is in files.
- Do not paste logs; grep the line you need.
- When context grows, write the state into notes/ORCHESTRATOR.md and STATUS.md, then compact.

## 5. Order (see ROADMAP.md, section 3)

WP0 S1 -> S2 -> S3 (M0) -> wave 1: WP1, WP2, WP5 in parallel -> wave 2: WP3, WP4 ->
WP6 -> WP7. Each WP's steps are sequential.

## 6. Model / effort per task (user decision 2026-10-20: save usage WITHOUT lowering quality)

Pick the cheapest tier that does the task correctly. When in doubt, go one tier up.

| Tier | Model / effort | Use for |
|---|---|---|
| T1 | haiku / medium | downloads, inventory and integrity checks, doc fixes, rerunning an existing script unchanged |
| T2 | sonnet / medium | data layers / adapters, rule and physics layers with a clear spec, unit tests |
| T3 | sonnet / high | learned models, calibration-sensitive evaluation, combiners, ablations, milestone reports, any step with leakage risk |
| T4 | opus / medium | a step that failed review twice; cross-domain / contract design (WP6, fusion) |

Escalation: a step sent back with CHANGES goes one tier up. A step whose numbers look too good
gets a T3 re-check before approval.

Token savings that do not change quality:
- Each WP keeps `notes/WP<n>_brief.md` (max ~60 lines): current state, binding decisions,
  pitfalls, file map. The worker updates it at the end of each step. The next worker reads the
  brief + the WP file + RULES.md + the previous report's summary section instead of the full
  notes log, ARCHITECTURE and DATASETS (it opens those only for the sections it needs).
- Reports: a summary section (<= 40 lines) first; long tables go to results/*.md.
- Max 3 workers in parallel (user 2026-10-21; was 2).

## 7. Progress percentage (user request 2026-10-22)

At every approval, update the "Overall progress" table in STATUS.md (approved steps / total
counted steps, per WP and overall, with date and time) and mention the overall % to the user.
Optional steps are not counted; a new fix step (e.g. S1b) adds to the total when assigned.
