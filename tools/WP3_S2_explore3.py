import numpy as np
from lidar.data import drives_of, scan_files, load
np.set_printoptions(linewidth=200, suppress=True, precision=3)
def runs(p):
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    w = np.flatnonzero(np.abs(np.diff(az)) > 100)
    ids = np.r_[0, w + 1, len(p)]
    ring = np.zeros(len(p), int)
    for k in range(len(ids) - 1): ring[ids[k]:ids[k+1]] = k
    return ring, az
pool = []
for d in drives_of("train")[:6]:
    fs = scan_files(d)
    for i in range(0, len(fs), 30):
        p = load(fs[i]); ring, az = runs(p)
        if ring.max() != 64: continue
        pool.append((p, ring, az, np.linalg.norm(p[:, :3], axis=1)))
print(len(pool), "scans")
NB = 180  # 2 deg
cm = [np.zeros(NB) for _ in pool]
fit = {}
for it in range(4):
    for k in range(65):
        z = np.concatenate([p[ring == k, 2] - cm[j][np.clip(((az[ring == k] + 180) // 2).astype(int), 0, NB-1)] for j, (p, ring, az, rr) in enumerate(pool)])
        r = np.concatenate([rr[ring == k] for (p, ring, az, rr) in pool])
        m = (r > 4) & (r < 60); keep = m.copy()
        for _ in range(5):
            c = np.polyfit(r[keep], z[keep], 1)
            e = z - np.polyval(c, r); keep = m & (np.abs(e) < 0.1)
        fit[k] = (c, np.mean(keep[m]), 1.4826*np.median(np.abs(e[keep])))
    for j, (p, ring, az, rr) in enumerate(pool):
        E = p[:, 2] - np.array([np.polyval(fit[k][0], 0)*0 for k in range(1)])[0]
        pred = np.zeros(len(p))
        for k in range(65):
            m = ring == k; pred[m] = np.polyval(fit[k][0], rr[m])
        E = p[:, 2] - pred
        ab = np.clip(((az + 180) // 2).astype(int), 0, NB - 1)
        good = (rr > 8) & (rr < 50) & (np.abs(E) < 0.15)
        c2 = np.zeros(NB)
        for b in range(NB):
            m = good & (ab == b)
            c2[b] = np.median(E[m]) if m.sum() >= 5 else 0
        cm[j] = c2
    print("iter", it, "cm amplitude", np.mean([np.ptp(c) for c in cm]))
for k in range(65):
    c, inl, mad = fit[k]
    print(k, "v=%.3f el=%.3f inl=%.3f sigma_z=%.4f" % (c[1+0-1] if False else c[1], np.degrees(np.arcsin(c[0])), inl, mad))
