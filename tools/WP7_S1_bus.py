"""WP7 S1 bus integration (A5, A6): all runners publish on ONE EvidenceBus from small validation slices; checks: per-(domain, layer) counts on the bus equal the runner outputs, merged order is by
stream time, wall clocks are monotone, interim / placeholder labels are on every LiDAR / network record, every combined record has the contract fields. Also micro-benchmarks of the bus
publish and of the neutral network placeholder push (the placeholder cost is the plumbing cost, not a detector).
Slices (validation only): GPS 12 runs of drives 0011/0035/0027 (the first 12 of the stream), CAN first 14 s of ROAD correlated_signal_attack_2, V2X first 400 messages of VeReMi validation block 4,
cross 150 residual-level steps of the WP6 S2b validation rows, LiDAR 6 scans of drive 0011, network 50 synthetic flow records.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_bus.py     Output: results/WP7/S1_bus.json
"""
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np

import WP1_S4_lib as W1
import WP5_S5_dev as dev5
from common.config import DATA_EXTRA
from common.evidence import Evidence
from gps import lidar_odom as LO
from lidar.data import CACHE, group_id, load, scan_files
from system.bus import EvidenceBus
from system.can_runner import CANRunner
from system.cross_runner import CrossObject, CrossRunner
from system.gps_runner import INPUT_COLUMNS, GPSRunner
from system.net_runner import NetworkRunner
from system.placeholder_runners import LidarInterimModel, LidarInterimRunner, NetworkPlaceholderRunner
from system.v2x_runner import HELDOUT, V2XPhysicsDomain, V2XRunner
from v2x import splitting


def main():
    bus = EvidenceBus()
    outs = {}
    # GPS
    kx = W1.kitti_stream()
    val = kx[kx["part"] == "val"].copy()
    val = val.join(LO.stream_features(val))
    gr = GPSRunner(L.ROOT / "results" / "WP1" / "frozen_gps", bus, per_layer=False)
    n_gps = 0
    for run, g in list(val.groupby("run", sort=False))[:12]:
        gr.reset(run)
        for s in g[[c for c in INPUT_COLUMNS if c in g.columns]].to_dict("records"):
            n_gps += len(gr.push(s))
    outs[("gps", "combined")] = n_gps
    # CAN
    z = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / "correlated_signal_attack_2.npz")
    B = np.maximum(np.load(DATA_EXTRA / "WP2_S4_cache" / "road" / "correlated_signal_attack_2.npy"), 0).astype(np.uint8)
    k = int(np.searchsorted(z["t"], z["t"][0] + 14.0))
    cr = CANRunner(L.ROOT / "results" / "WP2" / "s7_domain", bus, per_layer=False)
    cr.reset("cap")
    n_can = sum(len(cr.push((z["t"][i], int(z["id"][i]), int(z["dlc"][i]), B[i]))) for i in range(k)) + len(cr.flush())
    outs[("can", "combined")] = n_can
    # V2X
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT) & (va["group"] == "4")].sort_values("t", kind="stable").reset_index(drop=True).iloc[:400]
    vr = V2XRunner(V2XPhysicsDomain.load(L.OUT / "frozen_v2x"), bus)
    vr.reset("blk4")
    outs[("v2x", "combined")] = sum(len(vr.push(r)) for r in va.to_dict("records"))
    # cross
    obj = CrossObject.load(L.OUT / "frozen_cross")
    rows = pickle.load(open(DATA_EXTRA / "cache_v3" / "WP6" / "s2b_kitti.pkl", "rb"))["rows"]
    rows = rows[rows["part"] == "val"].iloc[:150]
    names = [e.name for e in obj.edges]
    xr = CrossRunner(obj, bus)
    xr.reset("res")
    outs[("cross", "L2")] = sum(len(xr.push({"t": r["t"], "r": {n: r[f"r_{n}"] for n in names}, "v": {n: r[f"v_{n}"] for n in names}})) for _, r in rows.iterrows())
    # LiDAR interim
    m = LidarInterimModel(CACHE / "retrained_deployed.json").load_calibration(L.OUT / "frozen_lidar_interim" / "calibration.json")
    lr = LidarInterimRunner(m, bus)
    lr.reset("0011")
    files = scan_files("0011")[:6]
    outs[("lidar", "combined")] = sum(len(lr.push({"points": load(f), "t": 0.1 * j, "sample_id": group_id("0011", f)})) for j, f in enumerate(files))
    # network: S1b runner over the frozen domain, 25 minutes of D10 validation flows (S1 used a placeholder here)
    from network.domain import RAW_COLUMNS, NetworkDomain
    from tools.WP4_S3_lib import load as d10_load, stream as d10_stream
    nv = d10_stream(d10_load("D10"), "val")
    t0 = float(nv["t"].min())
    nv = nv[(nv["t"] >= t0 + 3600) & (nv["t"] < t0 + 5100)].sort_values(["t", "row"], kind="stable").reset_index(drop=True)
    nv["src_ip"], nv["dst_ip"] = "h" + nv["src_id"].astype(str), "h" + nv["dst_id"].astype(str)
    nr = NetworkRunner(NetworkDomain.load(L.ROOT / "results" / "WP4" / "s7_domain"), bus)
    nr.reset("d10val")
    outs[("network", "combined")] = sum(len(nr.push(f)) for f in nv[RAW_COLUMNS].to_dict("records")) + len(nr.flush())
    # ---- checks ----
    counts = bus.counts()
    count_ok = {f"{d}/{l}": (counts.get((d, l), 0) == n) for (d, l), n in outs.items()}
    merged = bus.merged()
    order_ok = all(merged[i].evidence.t <= merged[i + 1].evidence.t for i in range(len(merged) - 1))
    wall_ok = all(bus.records[i].wall_ns <= bus.records[i + 1].wall_ns for i in range(len(bus.records) - 1))
    delay_ok = all(r.delay_ms >= 0 for r in bus.records)
    fields_ok = all(isinstance(r.evidence, Evidence) and 0.0 <= r.evidence.score <= 1.0 and (r.evidence.reason != "") == r.evidence.alarm and r.evidence.sample_id != "" for r in bus.records)
    lab = {}
    for dom, st in (("lidar", "interim"),):
        rs = bus.by_domain(dom)
        lab[dom] = bool(rs) and all(r.status == st and r.evidence.details.get("status") == st for r in rs)
    frozen_unlabelled = all("status" not in r.evidence.details for r in bus.records if r.evidence.domain in ("gps", "can", "v2x", "cross", "network"))
    # micro-benchmarks
    b2 = EvidenceBus()
    e = Evidence("gps", "combined", "x", 0.0, 0.1, False, "", {}, "s")
    t0 = time.perf_counter_ns()
    for _ in range(20000):
        b2.publish(e, "bench")
    pub_us = (time.perf_counter_ns() - t0) / 20000 / 1e3
    nr2 = NetworkPlaceholderRunner()
    nr2.reset("b")
    for j in range(5000):
        nr2.push({"t": float(j), "sample_id": "f"})
    ph = nr2.latency.summary()["all_calls"]
    res = {"slices": {"gps_runs": 12, "can_seconds": 14, "v2x_messages": 400, "cross_steps": 150, "lidar_scans": 6, "network_flows": "25 min of D10 validation (S1b, frozen domain)"},
           "evidence_on_bus": {f"{d}/{l}": int(n) for (d, l), n in counts.items()}, "runner_outputs": {f"{d}/{l}": int(n) for (d, l), n in outs.items()},
           "A5_counts_equal": count_ok, "A5_merged_order_by_stream_time": order_ok, "A5_wall_clock_monotone": wall_ok, "A5_ingest_before_publish": delay_ok, "A5_contract_fields": fields_ok,
           "A6_labels_on_every_record": lab, "A6_frozen_records_carry_no_status": frozen_unlabelled,
           "bus_publish_us_per_record": pub_us, "network_placeholder_push_ms": ph, "note_S1b": "network runner is the frozen-domain runner since S1b; placeholder push cost kept only as plumbing reference",
           "pipeline_delay_ms_median_by_domain": {d: float(np.median([r.delay_ms for r in bus.by_domain(d)])) for d in ("gps", "can", "v2x", "cross", "lidar", "network")}}
    res["A5_met"] = bool(all(count_ok.values()) and order_ok and wall_ok and delay_ok and fields_ok)
    res["A6_met"] = bool(all(lab.values()) and frozen_unlabelled)
    L.dump(res, "S1_bus.json")
    print({k: res[k] for k in ("A5_met", "A6_met", "bus_publish_us_per_record")}, flush=True)


if __name__ == "__main__":
    main()
