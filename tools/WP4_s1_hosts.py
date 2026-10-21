"""WP4 S1: per-host attack labels for D10 (CICIDS2017), from the dataset documentation, verified on the data.

Documented (CIC page, ids-2017): attacker = Kali 205.174.165.73, seen as 172.16.0.1 behind the firewall NAT;
victims are 192.168.10.x machines (web server 192.168.10.50, Ubuntu 192.168.10.51/.19/.17, Windows 192.168.10.5/.8/.9/.12/.14/.15/.25).
Per attack flow: the end whose IP is in ATTACKERS is the attacker, the other end is the victim. Attack flows with no documented
attacker end (e.g. infiltration pivot) are reported, not guessed.
Output: results/WP4/s1_hosts_d10.json, cache ../data_extra/cache_v3/WP4/D10/roles.pkl (file, row, src_role, dst_role).
Run: python -u -W ignore -I tools/WP4_s1_hosts.py
"""
import glob, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIN = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4", "D10", "final")
ATTACKERS = {"205.174.165.73", "172.16.0.1"}


def main():
    parts = []
    for p in sorted(glob.glob(os.path.join(FIN, "*.pkl"))):
        d = pd.read_pickle(p, compression="gzip")[["file", "row", "ts", "src_ip", "dst_ip", "family", "split", "day"]]
        for c in ["file", "src_ip", "dst_ip", "family", "split", "day"]:
            d[c] = d[c].astype(str)
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    att = d["family"] != "BENIGN"
    s_att = d["src_ip"].isin(ATTACKERS).to_numpy()
    d_att = d["dst_ip"].isin(ATTACKERS).to_numpy()
    a = att.to_numpy()
    d["src_role"] = np.where(a & s_att, "attacker", np.where(a & d_att, "victim", "none"))
    d["dst_role"] = np.where(a & d_att, "attacker", np.where(a & s_att, "victim", "none"))
    d[["file", "row", "src_role", "dst_role"]].to_pickle(os.path.join(FIN, "..", "roles.pkl"))
    res = {"attackers_documented": sorted(ATTACKERS), "per_family": {}}
    for f, g in d[a].groupby("family"):
        has = (g["src_ip"].isin(ATTACKERS) | g["dst_ip"].isin(ATTACKERS))
        vic = pd.concat([g.loc[g["src_ip"].isin(ATTACKERS), "dst_ip"], g.loc[g["dst_ip"].isin(ATTACKERS), "src_ip"]])
        other = g[~has]
        res["per_family"][f] = {
            "flows": int(len(g)), "share_with_documented_attacker_end": float(has.mean()),
            "days": sorted(g["day"].unique().tolist()),
            "top_victims": vic.value_counts().head(5).to_dict(),
            "top_src_ip_all": g["src_ip"].value_counts().head(3).to_dict(),
            "top_dst_ip_all": g["dst_ip"].value_counts().head(3).to_dict(),
            "no_documented_attacker_flows": int(len(other)),
            "no_attacker_top_src": other["src_ip"].value_counts().head(3).to_dict()}
    # host-level: hosts that act as attacker / victim per day
    h = d[a & (d["src_role"] != "none")]
    res["hosts_attacker_flows_by_day"] = {str(k): int(v) for k, v in
                                         h[h["src_role"] == "attacker"].groupby(["day", "src_ip"]).size().items()}
    res["victim_hosts_by_family"] = {f: g["dst_ip"].value_counts().head(8).to_dict()
                                     for f, g in d[a & (d["dst_role"] == "victim")].groupby("family")}
    res["attack_flows_total"] = int(a.sum())
    res["attack_flows_with_roles"] = int(((d["src_role"] != "none") | (d["dst_role"] != "none"))[a].sum())
    json.dump(res, open(os.path.join(ROOT, "results", "WP4", "s1_hosts_d10.json"), "w"), indent=1)
    print(json.dumps({f: (v["flows"], round(v["share_with_documented_attacker_end"], 3), v["top_victims"]) for f, v in res["per_family"].items()}, indent=0))


if __name__ == "__main__":
    main()
