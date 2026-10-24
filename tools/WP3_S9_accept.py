"""WP3 S9: acceptance verdicts of M1-LiDAR -> results/WP3/S9/acceptance.json (the PENDING slot of make_report.py: one entry per rule with `rule`, `met`
and the observed numbers). Rules are the ones written in notes/WP3_lidar.md ("S9 design and ACCEPTANCE RULE") before any S9 result.
Inputs: final.json, freeze_check.json, dev.json, extra.json (tests passed, cache size, cost; written by the worker after the suite).
Usage: python -u -W ignore tools/WP3_S9_accept.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

RES = RESULTS / "WP3" / "S9"


def main():
    F = json.loads((RES / "final.json").read_text())
    Z = json.loads((RES / "freeze_check.json").read_text())
    D = json.loads((RES / "dev.json").read_text())
    X = json.loads((RES / "extra.json").read_text())
    h = F["headline"]
    det = {a: v["det"] for a, v in h["det"].items()}
    ep, epw = F["episodes"]["ep"]["stack"], F["episodes"]["epw"]["stack"]
    worst_fa = max(h["fa_per_drive"].values())
    far = max(det["ph_replace_far"], det["ph_budget_near"], det["ph_budget_far"])
    earn = F["earns_place"]
    A = {}
    A["R1_false_alarms"] = {"fa": h["fa"], "worst_drive_fa": worst_fa, "lodo_mean_fa": h["lodo_mean"], "lodo_worst_fa": h["lodo_worst"],
                            "rule": "stack FA <= 2.5 % at 1 % total budget and worst test drive <= 5 %", "met": bool(h["fa"] <= 0.025 and worst_fa <= 0.05)}
    A["R2_targets_pointdrop_intensity"] = {"pointdrop": det["PointDrop"], "intensity_spoof": det["IntensitySpoof"],
                                           "pointdrop_best_layer_alone": F["dilution"]["PointDrop"]["best_layer_alone"],
                                           "rule": "PointDrop >= 30 % and IntensitySpoof >= 50 % in the stack at the 1 % total budget (predicted borderline)",
                                           "met": bool(det["PointDrop"] >= 0.30 and det["IntensitySpoof"] >= 0.50)}
    A["R3_single_return_phantoms"] = {"far_budget_max": far, "near_replace": det["ph_replace_near"], "fa": h["fa"],
                                      "rule": "far / budget calibrated phantoms <= FA + 10 points (physics bound); near replace reported", "met": bool(far <= h["fa"] + 0.10)}
    A["R4_episodes"] = {"false_episode_rate": ep["false_episode_rate"], "sensor_fixed_replace_near_detected": ep["kinds"]["ep_replace_near"]["detected_3s"],
                        "episodes_per_kind": ep["kinds"]["ep_replace_near"]["episodes"], "world_fixed_replace_near_detected": epw["kinds"]["epW_replace_near"]["detected_3s"],
                        "rule": "false-episode rate <= 10 % and sensor-fixed near replace >= 50 % of the episodes within 3 s; world-fixed reported (predicted not detected after the first scan)",
                        "met": bool(ep["false_episode_rate"] <= 0.10 and ep["kinds"]["ep_replace_near"]["detected_3s"] / ep["kinds"]["ep_replace_near"]["episodes"] >= 0.5)}
    A["R5_every_layer_earns_its_place"] = {"L1_largest_loss_when_removed": earn["raw_L1"]["largest_loss_when_removed"], "L2a": earn["raw_L2a"]["largest_loss_when_removed"],
                                          "L2c": earn["raw_L2c"]["largest_loss_when_removed"], "L2d": earn["raw_L2d"]["largest_loss_when_removed"],
                                          "rule": "each headline layer, when removed, lowers some physical-attack detection by >= 3 points (predicted: L1 does not on the single-return set)",
                                          "met": bool(all(v["earns_place"] for v in earn.values()))}
    A["R6_wp_file_targets"] = {"budget_phantoms_50_400": max(det["ph_budget_near"], det["ph_budget_far"]), "near_sparse": det["ph_budget_near"],
                               "rule": "WP file: 50-400 added points >= 60 % and near sparse > 50 % at 1 % FA (predicted NOT MET: physics bound)",
                               "met": bool(det["ph_budget_near"] >= 0.60 and det["ph_budget_far"] >= 0.60)}
    A["R7_freeze_reproduces_test_scores"] = {"max_abs_diff": max(Z["max_abs_diff"].values()), "alarm_differences": Z["alarm_differences"], "replayed_scans": Z["matched_to_stored"],
                                             "clean_scans": Z["clean"], "attacked_scans": Z["attacked"],
                                             "rule": "frozen domain replayed from raw scans reproduces the stored test per-layer scores and stack score (<= 1e-9, 0 alarm differences) on all clean test scans and the attacked scans of >= 2 test drives",
                                             "met": bool(Z["exact"] and Z["attack_drives"] and len(Z["attack_drives"]) >= 2)}
    A["R8_tests_cache_cost"] = {"tests_passed": X["tests_passed"], "tests_failed": X["tests_failed"], "extra_cache_gb": X["extra_cache_gb"], "scoring_s_per_scan": X["scoring_s_per_scan"],
                                "rule": "full test suite passes, extra cache <= 2 GB, scoring cost per scan reported", "met": bool(X["tests_failed"] == 0 and X["extra_cache_gb"] <= 2.0)}
    A["V1_combiner_choice"] = {"verdict": "CHOSEN " + D["V1"]["chosen"], "rule": D["V1"]["reason"], "validation_mean_physical_detection": D["V1"]["mean_phys"]}
    A["V2_density_part"] = {"gain": D["V2"]["gain"], "verdict": "KEPT" if D["V2"]["density_kept"] else "NOT KEPT (intensity part only)",
                            "rule": "density part kept only if validation mean physical detection +2 points and worst LODO FA +2 points at most"}
    A["milestone"] = {"verdict": "PARTIAL: " + ", ".join(k.split("_")[0] for k, v in A.items() if isinstance(v, dict) and v.get("met") is False and k.startswith("R")) + " NOT MET",
                      "rule": "M1-LiDAR closes PARTIAL when the pre-registered predictions of the physics bound hold and every honest limit is stated"}
    (RES / "acceptance.json").write_text(json.dumps(A, indent=1))
    for k, v in A.items():
        print(k, v.get("met", v.get("verdict")))


if __name__ == "__main__":
    main()
