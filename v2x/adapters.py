"""Dataset adapters: raw V2X files -> unified message table (v2x/schema.py).

Inputs: D12 VeReMi Extension combined CSV, D14 Tampa CV Pilot BSM sample CSV, D13 V2AIX JSON
(real ETSI CAM, adapter in v2x/v2aix.py). Output: DataFrame with schema.COLUMNS, sorted by (track, t).
Notes:
- VeReMi: pos/spd/acl/hed are 2-D vectors; heading = atan2(hedy, hedx), acl = projection of
  the acceleration vector on the heading. No receiver id / position in the combined CSV.
  Track = sender + pseudonym (a pseudonym is one continuous stream). Label = VeReMi class.
- Tampa: J2735 units (lat/long 1e-7 deg, speed 0.02 m/s, heading 0.0125 deg clockwise from
  north, accel 0.01 m/s^2, yaw 0.01 deg/s clockwise). Generation time = secMark (ms in the
  minute) combined with the RSU record time; duplicates (same id, same generation time, heard
  by two RSUs) dropped. Track = vehicle id + segment (a new segment after a gap > 5 s).
  RSU positions are unknown -> rx_x / rx_y NaN. Real, unlabeled: label 0 (assumed genuine).
Run readers with python -I on untrusted data.
"""
import numpy as np
import pandas as pd

from common.config import DATA_EXTRA
from v2x import tampa_link
from v2x.schema import COLUMNS, TEXT, CLASS_NAMES, DataNotAvailableError

VEREMI_CSV = DATA_EXTRA / "D12_veremi_extension" / "mixalldata_clean.csv"
TAMPA_CSV = DATA_EXTRA / "D14_tampa_bsm" / "bsm_sample.csv"
V2AIX_DIR = DATA_EXTRA / "D13_v2aix"
TAMPA_LAT0, TAMPA_LON0 = 27.95, -82.45     # fixed local-frame origin (deg)
TAMPA_GAP_S = 5.0                          # a gap longer than this starts a new track segment
_M_PER_DEG = 111320.0


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None if c in TEXT else np.nan
    df = df[COLUMNS].sort_values(["track", "t"], kind="stable").reset_index(drop=True)
    return df


def load_veremi(path=VEREMI_CSV, nrows=None) -> pd.DataFrame:
    r = pd.read_csv(path, nrows=nrows)
    hx, hy = r["hedx"].to_numpy(float), r["hedy"].to_numpy(float)
    n = np.hypot(hx, hy)
    n[n == 0] = 1.0
    ux, uy = hx / n, hy / n
    out = pd.DataFrame({
        "msg_id": "veremi:" + r["messageID"].astype(np.int64).astype(str),
        "source": "veremi",
        "sender": r["sender"].astype(np.int64).astype(str),
        "pseudo": r["senderPseudo"].astype(np.int64).astype(str),
        "t": r["sendTime"].astype(float),
        "x": r["posx"].astype(float), "y": r["posy"].astype(float),
        "vx": r["spdx"].astype(float), "vy": r["spdy"].astype(float),
        "speed": np.hypot(r["spdx"], r["spdy"]),
        "heading": np.arctan2(hy, hx),
        "acl": r["aclx"].to_numpy(float) * ux + r["acly"].to_numpy(float) * uy,
        "yaw_rate": np.nan,
        "pos_sigma": 0.5 * (r["posx_n"].to_numpy(float) + r["posy_n"].to_numpy(float)),
        "spd_sigma": 0.5 * (r["spdx_n"].to_numpy(float) + r["spdy_n"].to_numpy(float)),
        "acl_sigma": 0.5 * (r["aclx_n"].to_numpy(float) + r["acly_n"].to_numpy(float)),
        "label": r["class"].astype(int),
        "injected": False,
    })
    out["track"] = out["sender"] + "/" + out["pseudo"]
    out["attack"] = out["label"].map(CLASS_NAMES)
    return _finish(out)


def load_tampa_v1(path=TAMPA_CSV, with_age=False) -> pd.DataFrame:
    """LEGACY (S1-S3 of WP5, kept for the record): sender = coreData_id, which is per RSU, so one over-the-air message heard by
    several RSUs appears under several ids (S1b finding). Use load_tampa().
    with_age=True adds the extra column age_s = RSU log time - generation time (s; 1 s log resolution)."""
    cols = ["metadata_recordGeneratedAt", "metadata_RSUID", "coreData_id",
            "coreData_secMark", "coreData_lat", "coreData_long", "coreData_accelset_yaw",
            "coreData_accelset_long", "coreData_speed", "coreData_heading"]
    r = pd.read_csv(path, usecols=cols)
    rec = pd.to_datetime(r["metadata_recordGeneratedAt"], utc=True).astype("int64") // 10 ** 9
    rec_s = rec % 60
    sm = r["coreData_secMark"] / 1000.0
    minute = ((rec - rec_s) % 86400).to_numpy(dtype=float)   # seconds of the UTC day (exact)
    gen = minute + sm.to_numpy()
    gen = np.where(sm - rec_s > 30, gen - 60, gen)       # made just before the minute turned
    gen = np.where(rec_s - sm > 30, gen + 60, gen)
    r["t"] = gen % 86400.0
    r["age_s"] = ((rec.to_numpy(dtype=float) % 86400.0 - r["t"].to_numpy() + 43200.0) % 86400.0) - 43200.0
    r["sender"] = r["coreData_id"].astype(np.int64).astype(str)
    r = r.sort_values(["sender", "t", "metadata_RSUID"], kind="stable")
    r = r.drop_duplicates(["sender", "t"]).reset_index(drop=True)
    seg = (r.groupby("sender")["t"].diff() > TAMPA_GAP_S).groupby(r["sender"]).cumsum()
    lat = r["coreData_lat"].to_numpy(float) / 1e7
    lon = r["coreData_long"].to_numpy(float) / 1e7
    spd = r["coreData_speed"].to_numpy(float) * 0.02
    spd[r["coreData_speed"].to_numpy() == 8191] = np.nan
    hd = r["coreData_heading"].to_numpy(float) * 0.0125   # compass degrees, clockwise from north
    th = np.pi / 2 - np.radians(hd)
    th[r["coreData_heading"].to_numpy() == 28800] = np.nan
    acl = r["coreData_accelset_long"].to_numpy(float) * 0.01
    acl[r["coreData_accelset_long"].to_numpy() == 2001] = np.nan
    yaw = -np.radians(r["coreData_accelset_yaw"].to_numpy(float) * 0.01)
    out = pd.DataFrame({
        "msg_id": "tampa:" + r["sender"] + ":" + r["t"].map("{:.3f}".format),
        "source": "tampa", "sender": r["sender"], "pseudo": r["sender"],
        "track": r["sender"] + "/" + seg.astype(str),
        "t": r["t"],
        "x": (lon - TAMPA_LON0) * _M_PER_DEG * np.cos(np.radians(TAMPA_LAT0)),
        "y": (lat - TAMPA_LAT0) * _M_PER_DEG,
        "speed": spd, "vx": spd * np.cos(th), "vy": spd * np.sin(th),
        "heading": th, "acl": acl, "yaw_rate": yaw,
        "rx_id": r["metadata_RSUID"], "lat": lat, "lon": lon,
        "label": 0, "attack": "Genuine", "injected": False,
    })
    age = pd.Series(r["age_s"].to_numpy(), index=out["msg_id"].to_numpy())
    out = _finish(out[np.isfinite(out["speed"])])
    if with_age:
        out["age_s"] = age.loc[out["msg_id"].to_numpy()].to_numpy()
    return out


def load_v2aix(path=V2AIX_DIR, recordings=None) -> pd.DataFrame:
    """V2AIX (real ETSI CAM, RWTH ika; WP5 S0c): all extracted recordings (or the listed recording ids) as one unified table with the ego
    GNSS position as receiver (rx_x, rx_y). Unit conversions and time handling are documented in v2x/v2aix.py.
    Raises DataNotAvailableError if nothing is extracted."""
    from v2x import v2aix
    root = path / "extracted" / "json"
    if not root.exists() or not v2aix.list_recordings(root):
        raise DataNotAvailableError("V2AIX (D13) not extracted under " + str(root))
    return v2aix.load_all(root, recordings)


_TAMPA_CACHE = {}


def tampa_messages(path=TAMPA_CSV, tier2=True):
    """Deduplicated unique messages + info of v2x.tampa_link.build (cached)."""
    key = (str(path), bool(tier2))
    if key not in _TAMPA_CACHE:
        _TAMPA_CACHE[key] = tampa_link.build(path, link=tier2)
    u, info = _TAMPA_CACHE[key]
    return u.copy(), info


def load_tampa(path=TAMPA_CSV, with_age=False, tier2=True) -> pd.DataFrame:
    """Tampa BSMs, deduplicated and linked (WP5 S1b, v2x/tampa_link.py): one row per over-the-air message; sender = passage of a
    physical vehicle (id 'P007_1' = vehicle 7, passage 1; passages are cut at silences > 120 s); pseudo = sender; track = sender +
    segment (new segment after a gap > 5 s). rx_id is NaN: the message was heard by one or more RSUs (the receiver is not a single
    one after deduplication). with_age=True adds age_s = RSU log time of the first received copy - generation time (s).
    Same units and conventions as load_tampa_v1."""
    u, _ = tampa_messages(path, tier2)
    u = u.sort_values(["sender", "t"], kind="stable").drop_duplicates(["sender", "t"]).reset_index(drop=True)
    sd = u["sender"]
    seg = (u.groupby("sender")["t"].diff() > TAMPA_GAP_S).groupby(sd).cumsum()
    lat = u["lat_i"].to_numpy(float) / 1e7
    lon = u["lon_i"].to_numpy(float) / 1e7
    spd = u["spd_i"].to_numpy(float) * 0.02
    spd[u["spd_i"].to_numpy() == 8191] = np.nan
    th = np.pi / 2 - np.radians(u["hd_i"].to_numpy(float) * 0.0125)
    th[u["hd_i"].to_numpy() == 28800] = np.nan
    acl = u["acl_i"].to_numpy(float) * 0.01
    acl[u["acl_i"].to_numpy() == 2001] = np.nan
    yaw = -np.radians(u["yaw_i"].to_numpy(float) * 0.01)
    out = pd.DataFrame({
        "msg_id": "tampa:" + sd + ":" + u["t"].map("{:.3f}".format),
        "source": "tampa", "sender": sd, "pseudo": sd, "track": sd + "/" + seg.astype(str),
        "t": u["t"].to_numpy(),
        "x": (lon - TAMPA_LON0) * _M_PER_DEG * np.cos(np.radians(TAMPA_LAT0)),
        "y": (lat - TAMPA_LAT0) * _M_PER_DEG,
        "speed": spd, "vx": spd * np.cos(th), "vy": spd * np.sin(th),
        "heading": th, "acl": acl, "yaw_rate": yaw, "lat": lat, "lon": lon,
        "label": 0, "attack": "Genuine", "injected": False})
    age = pd.Series(u["age_s"].to_numpy(), index=out["msg_id"].to_numpy())
    out = _finish(out[np.isfinite(out["speed"])])
    if with_age:
        out["age_s"] = age.loc[out["msg_id"].to_numpy()].to_numpy()
    return out
