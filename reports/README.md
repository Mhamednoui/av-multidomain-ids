# Step reports

One file per step: `reports/WP<n>_S<k>.md`. Requests to change shared files:
`reports/REQUEST_WP<n>_<topic>.md`. Template:

```
# WP<n> S<k>: <title>

Date: YYYY-MM-DD    Worker: <session / agent id>

## Goal of the step
(one or two sentences, from the WP file)

## Acceptance rule (as written in the notes BEFORE the result, with its timestamp)

## What was done
- files created / changed (paths)
- data used (dataset ids, splits)

## Results (copied exactly from results/WP<n>/<file>.json)
| ... | ... |
Acceptance: MET / NOT MET (why)

## Ablation row(s) for the layer(s) of this step

## Problems, surprises, open questions

## Proposed next step (or changes to the plan)
```
