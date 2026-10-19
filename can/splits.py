"""CAN splits (WP2 S1): lists of capture ids, never rows (RULES 5.1).

ROAD: by capture as in v2 (instance 1 train, 2 val, 3 test; masquerade copies with their
  originals; ambient test / val lists fixed by v2).
Car-Hacking: only 4 long files, attacks sit in the first ~75-80% of each: interleaved time
  blocks (v2 block_split copied from ../codes_v2/can/train.py): 100 blocks per file, blocks that
  contain an attack and blocks that do not are each cut 70 / 15 / 15 train / val / test.
D11: its own known / unknown vehicle test sets, one experiment per set (set_01..set_04).
  train_01 -> train, except the validation hold-out (rule fixed before results: for each attack
  family with >= 2 captures in train_01 the highest-numbered capture goes to val). Byte-identical
  files (same sha256) are deduplicated: inside one experiment a hash lives on one side only
  (precedence train > val > test_01 > ... > test_04; later copies are excluded and listed).
Inputs: capture tables (can/adapters.py), file hashes (results/WP2/s1_d11_scan.json).
Outputs: dicts of capture ids, saved as JSON by tools/WP2_S1_splits.py.
"""
import numpy as np

from common.config import SEED
from common.splits import check_disjoint

N_BLOCKS = 100


def road_split(caps) -> dict:
    """caps: output of adapters.road_captures(). Returns {'train','val','test'} lists of capture
    names (usable captures only) and checks that each masquerade sits with its original."""
    use = caps[caps["usable"]]
    out = {p: sorted(use[use["part"] == p]["name"].tolist()) for p in ("train", "val", "test")}
    check_disjoint(out)
    side = {n: p for p, ns in out.items() for n in ns}
    for n in side:
        if n.endswith("_masquerade"):
            orig = n[:-len("_masquerade")]
            if orig in side and side[orig] != side[n]:
                raise ValueError(f"masquerade {n} and its original are on different sides")
    return out


def block_index(n: int) -> np.ndarray:
    return np.minimum((np.arange(n) * N_BLOCKS) // n, N_BLOCKS - 1)


def block_assign(label, rng) -> np.ndarray:
    """v2 interleaved block split: part name per block (length N_BLOCKS)."""
    has_attack = np.zeros(N_BLOCKS, dtype=bool)
    has_attack[np.unique(block_index(len(label))[np.asarray(label) != 0])] = True
    assign = np.empty(N_BLOCKS, dtype=object)
    for group in (np.flatnonzero(has_attack), np.flatnonzero(~has_attack)):
        g = rng.permutation(group)
        k1, k2 = int(round(0.70 * len(g))), int(round(0.85 * len(g)))
        assign[g[:k1]], assign[g[k1:k2]], assign[g[k2:]] = "train", "val", "test"
    return assign


def block_split(label, rng) -> np.ndarray:
    """Part name ('train' / 'val' / 'test') per frame."""
    return block_assign(label, rng)[block_index(len(label))]


def carhacking_blocks(labels_by_file: dict) -> dict:
    """{file: label array} -> {file: list of N_BLOCKS part names}. Files in dict order, one
    generator seeded with SEED, as in v2 (same call order, same draws)."""
    rng = np.random.default_rng(SEED)
    return {name: [str(x) for x in block_assign(lab, rng)] for name, lab in labels_by_file.items()}


def d11_split(table, hashes: dict) -> dict:
    """table: adapters.d11_file_table(); hashes: {capture: sha256}.
    Returns {set: {'train': [...], 'val': [...], 'test_01..04': [...], 'excluded_duplicates': {...}}}.
    Guarantees: no hash on both sides inside a set; every file at most once per set."""
    out = {}
    for s, g in table.groupby("set"):
        parts = {"train": [], "val": []}
        tr = g[g["role"] == "train"]
        for fam, f in tr.groupby("attack_family"):
            f = f.sort_values("number")
            if len(f) >= 2:
                parts["val"].append(f.iloc[-1]["capture"])
                parts["train"] += f.iloc[:-1]["capture"].tolist()
            else:
                parts["train"] += f["capture"].tolist()
        for sub in sorted(g[g["role"] == "test"]["subset"].unique()):
            parts[sub[:7]] = g[g["subset"] == sub]["capture"].tolist()
        seen, excluded = {}, {}
        for part in ["train", "val", "test_01", "test_02", "test_03", "test_04"]:
            keep = []
            for c in parts.get(part, []):
                h = hashes[c]
                if h in seen:
                    excluded[c] = {"part": part, "same_as": seen[h][0], "same_as_part": seen[h][1]}
                else:
                    seen[h] = (c, part)
                    keep.append(c)
            parts[part] = sorted(keep)
        parts["excluded_duplicates"] = excluded
        out[s] = parts
    return out


def check_d11_split(split: dict, hashes: dict):
    """Raise if any hash is on two sides / two parts of one experiment, or a file appears twice."""
    for s, parts in split.items():
        seen = {}
        for part, caps in parts.items():
            if part == "excluded_duplicates":
                continue
            for c in caps:
                if hashes[c] in seen:
                    raise ValueError(f"{s}: {c} duplicates {seen[hashes[c]][0]} ({part} vs {seen[hashes[c]][1]})")
                seen[hashes[c]] = (c, part)
