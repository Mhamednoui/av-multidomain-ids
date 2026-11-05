"""WP9 B5: shared helpers for the final comparison (formatting only; no scoring).

Purpose: format numbers read from approved result JSONs and render master-table cells from templates.
Inputs: none (pure functions). Outputs: strings. The path resolver used for building lives in
WP9_B5_build.py, the independent re-reader used for checking lives in WP9_B5_check.py.
References: RULES.md section 6 (every table number is generated from / copied from the JSON).
"""

ALLOWED_VERDICTS = ("better", "equal", "comparable-not-like-for-like", "not comparable", "below")


def fmt(kind, v):
    """Format a raw value. kinds: f2 f3 f4, pct0 pct1 pct2 pct3, ci2 ci3 ci4 (list of 2), cip1 (percent CI),
    int, sgn_pts1 (signed points from a fraction), sgn1 (signed number), ci_pts1 (CI in points), x1/x2 (plain number)."""
    if v is None:
        return "n/a"
    if kind in ("f2", "f3", "f4"):
        return f"{v:.{kind[1]}f}"
    if kind in ("pct0", "pct1", "pct2", "pct3"):
        return f"{100.0 * v:.{kind[3]}f}%"
    if kind in ("ci2", "ci3", "ci4"):
        d = kind[2]
        return f"[{v[0]:.{d}f}, {v[1]:.{d}f}]"
    if kind in ("cipct1", "cipct2", "cipct3"):
        d = kind[5]
        return f"[{100.0 * v[0]:.{d}f}%, {100.0 * v[1]:.{d}f}%]"
    if kind == "cip1_br":
        return f"[{100.0 * v[0]:.1f}, {100.0 * v[1]:.1f}]"
    if kind == "ci_sgn1":
        return f"[{v[0]:+.1f}, {v[1]:+.1f}]"
    if kind == "sgn1":
        return f"{v:+.1f}"
    if kind == "cip1":
        return f"[{100.0 * v[0]:.1f}, {100.0 * v[1]:.1f}]"
    if kind == "int":
        return f"{int(v):,}"
    if kind == "sgn_pts1":
        return f"{100.0 * v:+.1f}"
    if kind == "ci_pts1":
        return f"[{100.0 * v[0]:+.1f}, {100.0 * v[1]:+.1f}]"
    if kind == "x1":
        return f"{v:.1f}"
    if kind == "x2":
        return f"{v:.2f}"
    if kind == "sgn2":
        return f"{v:+.2f}"
    if kind == "bool":
        return "yes" if v else "no"
    raise ValueError(kind)


def render(template, texts):
    return template.format(**texts)


def minmax(vals):
    return min(vals), max(vals)
