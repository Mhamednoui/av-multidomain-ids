## What is a fair bar for a leak-free, seen-attack evaluation

1. **Almost every published headline is leaky or unstated.** Car-Hacking: F1 0.998-1.0 per attack under random 7:3 splits of overlapping
   frames (Hoang & Kim 2022) or an 80/20 split of unstated kind (Guerra et al. 2024). CICIDS2017: RF F1 0.94-0.998 per day (Pekar & Jozsa).
   VeReMi Extension: F1 0.93-0.998 on DoS-family types with a 70/30 split inside each dataset (Baharlouei et al. 2024; Asensio-Garriga as cited).
   GPS (AV-GPS): MLP mean F1 0.944 with stratified 5-fold (Abrar et al.). None of these is a bar we should claim to beat; they are the
   numbers a reader will have in mind, and our leak-free numbers will be lower. Say so in B5.
2. **The only protocols at least as strict as ours that we could read:**
   - can-train-and-test: capture-disjoint train / test, with unknown-vehicle and unknown-attack subsets (set_01 F1 0.95-0.998 for the best of 18 models,
     but the mean over models is 0.42-0.46 and many strong-looking learners collapse to F1 near 0).
   - CICIDS2017 temporal / group splits (Moczkodan & Ragab 2026, preprint): macro-F1 0.89 at best on 20-flow windows; random-split numbers are higher.
   - ROAD (Guerra et al.): not capture-level as far as stated, yet multiclass mean F1 0.32 and DCNN 0.65-0.75: ROAD is not solved even under a possibly leaky split.
3. **Fair bar by dataset (seen attacks, leak-free, fixed false-alarm budget):**
   - Car-Hacking: no leak-free published number found. Bar = "near 1.0 detection at 1% window FA" is plausible for DoS / Fuzzy / RPM / Gear because L1 rules already reach ~100% (WP2); the bar to state is our block-split number, compared with the leaky 0.998-1.0.
   - ROAD: no leak-free number found. Bar = per-capture-family recall at 1% FA; published F1 0.32-0.75 (multiclass / DCNN) are the only honest-looking comparators.
   - can-train-and-test: F1 about 0.95-0.998 (best learners, known and unknown subsets, set_01 only); mean over learners about 0.45. A fair claim: >= 0.98 F1 on test_01 and test_03 with a 1% FA budget and report test_02 / test_04 separately.
   - CICIDS2017 / CSE-CIC-IDS2018: published 0.99 numbers are not leak-free (duplicates 21.1% / 33.3% in our WP4 counts; label and flow errors per Engelen, Lanvin, Liu). Fair bar: macro-F1 about 0.85-0.90 on time / group splits (Moczkodan & Ragab, windows) after dedup; report per-family recall at 1% benign FA, not accuracy.
   - VeReMi Extension: published numbers are within-family DoS only. Our WP5 result (scored-row mean 83.0% over 13 seen classes at 1.1% FA, sender split) is stricter; no published number is comparable. State "no comparable published number".
   - GPS: AV-GPS F1 0.944 (stratified folds, single attack) is the only readable comparator; the cross-dataset cases (F1 0.90-0.965) are the closest to leak-free. No published GPS result exists on KITTI or comma2k19.
   - LiDAR: object-level accuracy > 94% (Shadow-Catcher, KITTI) and TPR > 85% at FPR < 10% (ADoPT, nuScenes) are not scan-level FA-budget numbers; at a 1% budget they are not comparable. Claim nothing beyond "comparable metric not available".
4. **Rule for B5 (WP9 file rule: no claim "best" without same metric and a protocol at least as strict):** a row may use the word "better" only
   against a published number whose protocol was read and is group / capture / time based. Everything else is labelled "reported under a random split".
5. **Open gaps in this survey (not found or not readable in B0):** Song 2020 original numbers; Verma 2024 baseline numbers; Engelen 2021 and Lanvin 2022
   per-class numbers; any peer-reviewed leak-free CSE-CIC-IDS2018 number; VeReMi Extension original benchmark (Kamel 2020); CARLO original paper; any GPS-spoofing
   result on KITTI or comma2k19. Rows from search snippets are marked UNVERIFIED in the tables and must not be quoted until opened.
