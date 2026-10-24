"""WP5 S0c: inventory of the V2AIX zip from its central directory only (paths, sizes). Nothing is extracted or executed."""
import json, sys, zipfile, collections
zp = sys.argv[1]
z = zipfile.ZipFile(zp)
bad = z.testzip()
rows = [(i.filename, i.file_size, i.compress_size) for i in z.infolist() if not i.is_dir()]
print("testzip:", bad, "files:", len(rows), "uncompressed GB:", sum(r[1] for r in rows) / 1e9)
st = collections.defaultdict(lambda: [0, 0, 0])
for n, s, c in rows:
    p = n.split("/")
    key = "/".join(p[:-1]) if len(p) > 1 else ""
    k = "/".join(p[:4]) if "scenarios" not in p else "/".join(p[:p.index("scenarios")]) + "/scenarios"
    if p[-1] == "joined.json":
        k = "/".join(p[:-1]) + "/joined"
    st[k][0] += 1; st[k][1] += s; st[k][2] += c
for k, v in sorted(st.items()):
    print(k, v[0], "files", round(v[1] / 1e6, 1), "MB unc", round(v[2] / 1e6, 1), "MB comp")
big = sorted(rows, key=lambda r: -r[1])[:5]
print("largest:", big)
json.dump([list(r) for r in rows], open(sys.argv[2], "w"))

md = ["# V2AIX JSON archive inventory (from the zip central directory, results of tools/WP5_S0c_inventory.py)", "",
      f"Archive: {len(rows)} files, {sum(r[1] for r in rows)/1e9:.2f} GB uncompressed, zip test OK. Topics inside a recording: /v2x/cam (parsed CAM), /v2x/raw, /gps/cohda_mk5/fix; "
      "Sensor-Context also /gps/oxts_rt3000/{fix,status,odom} and /tf_static. No DENM in this JSON release.", "",
      "| stratum (path under json/) | files | MB uncompressed | MB compressed |", "|---|---|---|---|"]
for k, v in sorted(st.items()):
    md.append(f"| {k} | {v[0]} | {v[1]/1e6:.1f} | {v[2]/1e6:.1f} |")
open(sys.argv[3], "w").write("\n".join(md) + "\n")
