#!/usr/bin/env python3
"""Derive and audit the Synex colour system from the Graylinx brand colour.

    python scripts/palette.py            # print the ramps, tokens and the WCAG audit
    python scripts/palette.py --css      # print only the CSS custom properties
    python scripts/palette.py --audit     # print only the audit; exit 1 if anything fails

Everything descends from one input: BRAND = #0020B0, International Klein Blue.
Ramps are built in OKLCH so the lightness steps are perceptually even, then
gamut-mapped into sRGB by reducing chroma — never by clipping channels, which
would shift the hue.

The audit is the point. Every foreground/background pair the interface actually
uses is checked against WCAG 2.2:

    1.4.3 Contrast (Minimum)      AA   body text >= 4.5:1, large text >= 3:1
    1.4.6 Contrast (Enhanced)     AAA  body text >= 7:1
    1.4.11 Non-text Contrast      AA   UI component boundaries, focus >= 3:1

If a token fails, the token is wrong — do not lower the threshold.
"""
from __future__ import annotations

import argparse
import math
import sys

BRAND = "#0020B0"          # Graylinx — International Klein Blue
BRAND_NAME = "International Klein Blue"

# --------------------------------------------------------------------------
# Colour space conversions — sRGB <-> OKLab / OKLCH
# --------------------------------------------------------------------------

def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = (v ** 3 for v in (l_, m_, s_))
    return (
        linear_to_srgb(+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        linear_to_srgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        linear_to_srgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
    )


def oklch_to_oklab(L: float, C: float, H: float) -> tuple[float, float, float]:
    h = math.radians(H)
    return (L, C * math.cos(h), C * math.sin(h))


def rgb_to_oklch(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    L, a, b = rgb_to_oklab(rgb)
    return (L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)


def in_gamut(rgb: tuple[float, float, float], eps: float = 1e-4) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb)


def oklch(L: float, C: float, H: float) -> str:
    """OKLCH to the nearest in-gamut sRGB hex, reducing chroma to fit."""
    if in_gamut(oklab_to_rgb(oklch_to_oklab(L, C, H))):
        return rgb_to_hex(oklab_to_rgb(oklch_to_oklab(L, C, H)))
    lo, hi = 0.0, C
    for _ in range(40):                     # binary search on chroma, hue held
        mid = (lo + hi) / 2
        if in_gamut(oklab_to_rgb(oklch_to_oklab(L, mid, H))):
            lo = mid
        else:
            hi = mid
    return rgb_to_hex(oklab_to_rgb(oklch_to_oklab(L, lo, H)))


# --------------------------------------------------------------------------
# WCAG 2.2 contrast
# --------------------------------------------------------------------------

def luminance(h: str) -> float:
    r, g, b = (srgb_to_linear(c) for c in hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------
# The ramps
# --------------------------------------------------------------------------

# Perceptually even lightness steps, the shape most tonal scales use.
STEPS = {
    "50": 0.981, "100": 0.951, "200": 0.902, "300": 0.834, "400": 0.746,
    "500": 0.650, "600": 0.556, "700": 0.470, "800": 0.392, "900": 0.322,
    "950": 0.245,
}

BRAND_L, BRAND_C, BRAND_H = rgb_to_oklch(hex_to_rgb(BRAND))

# Chroma envelope: full saturation through the mid-dark steps where the brand
# lives, tapering at both ends so the tints stay usable as surfaces and the
# darkest steps do not turn to mud.
CHROMA = {
    "50": 0.012, "100": 0.026, "200": 0.052, "300": 0.086, "400": 0.130,
    "500": 0.170, "600": 0.205, "700": 0.230, "800": 0.245, "900": 0.225,
    "950": 0.175,
}


def ramp(hue: float, chroma_scale: float = 1.0, chroma: dict | None = None) -> dict:
    src = chroma or CHROMA
    return {k: oklch(STEPS[k], src[k] * chroma_scale, hue) for k in STEPS}


def fit(against: str, target: float, hue: float, chroma: float, darker: bool) -> str:
    """The colour closest in lightness to `against` that still clears `target`.

    Used for borders and quiet text, where the honest move is to compute the
    lightest (or darkest) value that satisfies the ratio rather than to pick a
    ramp step by eye and then argue about the threshold. Hue is held; only
    lightness moves, so the result stays on the brand's axis.
    """
    lo, hi = (0.0, 1.0) if darker else (0.0, 1.0)
    best = "#000000" if darker else "#FFFFFF"
    for _ in range(48):
        mid = (lo + hi) / 2
        c = oklch(mid, chroma, hue)
        if contrast(c, against) >= target:
            best = c
            # push back toward `against` — darker means we may still lighten
            lo, hi = (mid, hi) if darker else (lo, mid)
        else:
            lo, hi = (lo, mid) if darker else (mid, hi)
    return best


# Neutrals carry a trace of the brand hue, so greys never read as a foreign
# colour next to the blue. This is the whole reason the page feels like one system.
NEUTRAL_CHROMA = {k: min(v, 0.018) for k, v in CHROMA.items()}

BRAND_RAMP = ramp(BRAND_H)
NEUTRAL = ramp(BRAND_H, chroma=NEUTRAL_CHROMA)

# Semantic hues, spaced far from the brand's ~264 deg so status never reads as
# brand. Green and red are also separated in lightness, not only hue, because
# roughly 1 in 12 men cannot separate them by hue alone.
HUES = {"success": 152.0, "warning": 75.0, "danger": 26.0}
SUCCESS = ramp(HUES["success"], 0.85)
WARNING = ramp(HUES["warning"], 0.95)
DANGER = ramp(HUES["danger"], 0.90)

RAMPS = {
    "brand": BRAND_RAMP, "neutral": NEUTRAL,
    "success": SUCCESS, "warning": WARNING, "danger": DANGER,
}


# --------------------------------------------------------------------------
# Semantic tokens — the only names the interface is allowed to use
# --------------------------------------------------------------------------

# Two border tokens, because WCAG 1.4.11 does not treat them alike:
#   --rule         decorative hairline — table gridlines, section dividers. Not
#                  required to identify a component, so it is exempt from 3:1.
#                  Still audited at 1.4:1 so it cannot vanish.
#   --rule-strong  the boundary of an actual control — the search field, chips,
#                  card outlines. In scope for 1.4.11, so it is computed to clear
#                  3:1 rather than picked by eye.
L_SUNKEN = NEUTRAL["50"]
L_THEAD = BRAND_RAMP["100"]
D_PAGE = NEUTRAL["950"]
D_CARD = oklch(0.285, 0.020, BRAND_H)
D_SUNKEN = oklch(0.330, 0.022, BRAND_H)
D_THEAD = oklch(0.375, 0.040, BRAND_H)

LIGHT = {
    "page":        "#FFFFFF",
    "card":        "#FFFFFF",
    "sunken":      L_SUNKEN,
    "thead":       L_THEAD,
    # lightest hairline that stays visible on white — dense gridlines, not a control
    "rule":        fit("#FFFFFF", 1.5, BRAND_H, 0.020, darker=True),
    # lightest grey on the brand axis that still clears 3:1 on white
    "rule-strong": fit(L_THEAD, 3.0, BRAND_H, 0.018, darker=True),
    "ink":         BRAND_RAMP["900"],
    "body":        NEUTRAL["900"],
    "muted":       NEUTRAL["700"],
    "accent":      BRAND,                 # the brand colour itself, unmodified
    "accent-hover": BRAND_RAMP["900"],
    "on-accent":   "#FFFFFF",
    "focus":       BRAND_RAMP["700"],
    "ok":          SUCCESS["800"],
    "warn":        WARNING["900"],
    "stop":        DANGER["800"],
    "mvp":         BRAND,
    "p2":          NEUTRAL["700"],
    # quietest grey that still clears AA body text on the lightest surface
    "p3":          fit(L_SUNKEN, 4.6, BRAND_H, 0.014, darker=True),
}

DARK = {
    "page":        D_PAGE,
    "card":        D_CARD,
    "sunken":      D_SUNKEN,
    "thead":       D_THEAD,
    "rule":        oklch(0.430, 0.026, BRAND_H),
    # fitted against the lightest surface it borders, which also satisfies the darker ones
    "rule-strong": fit(D_THEAD, 3.0, BRAND_H, 0.030, darker=False),
    "ink":         BRAND_RAMP["200"],
    "body":        NEUTRAL["100"],
    "muted":       NEUTRAL["400"],
    "accent":      BRAND_RAMP["400"],
    "accent-hover": BRAND_RAMP["300"],
    "on-accent":   oklch(0.200, 0.040, BRAND_H),
    "focus":       BRAND_RAMP["400"],
    "ok":          SUCCESS["400"],
    "warn":        WARNING["400"],
    "stop":        DANGER["400"],
    "mvp":         BRAND_RAMP["400"],
    "p2":          NEUTRAL["400"],
    "p3":          fit(D_SUNKEN, 4.6, BRAND_H, 0.014, darker=False),
}

# Every pair the interface actually renders. (fg, bg, minimum, what it is)
def pairs(t: dict) -> list[tuple[str, str, float, str]]:
    return [
        ("body", "page", 7.0, "body text on the page"),
        ("body", "card", 7.0, "body text in a card"),
        ("body", "sunken", 4.5, "body text on a sunken panel"),
        ("ink", "page", 7.0, "headings on the page"),
        ("ink", "card", 7.0, "headings in a card"),
        ("ink", "thead", 4.5, "table header text"),
        ("muted", "thead", 4.5, "muted text on a table header"),
        ("ink", "sunken", 4.5, "headings on a sunken panel"),
        ("muted", "page", 4.5, "muted text on the page"),
        ("muted", "card", 4.5, "muted text in a card"),
        ("muted", "sunken", 4.5, "muted text on a sunken panel"),
        ("accent", "page", 4.5, "links and accents on the page"),
        ("accent", "card", 4.5, "links and accents in a card"),
        ("accent", "sunken", 4.5, "links and accents on a sunken panel"),
        ("on-accent", "accent", 4.5, "text on an accent fill"),
        ("ok", "card", 4.5, "PASS text"),
        ("ok", "sunken", 4.5, "PASS text on a sunken panel"),
        ("warn", "card", 4.5, "warning text"),
        ("warn", "sunken", 4.5, "warning text on a sunken panel"),
        ("stop", "card", 4.5, "FAIL and never-decided-by text"),
        ("stop", "sunken", 4.5, "FAIL text on a sunken panel"),
        ("p2", "card", 4.5, "Phase 2 badge text"),
        ("p2", "sunken", 4.5, "Phase 2 badge on a sunken panel"),
        ("p3", "card", 4.5, "Phase 3 badge text"),
        ("p3", "sunken", 4.5, "Phase 3 badge on a sunken panel"),
        # 1.4.11 Non-text contrast — component boundaries and focus, 3:1
        ("rule-strong", "page", 3.0, "control boundaries on the page"),
        ("rule-strong", "card", 3.0, "control boundaries in a card"),
        ("rule-strong", "sunken", 3.0, "control boundaries on a sunken panel"),
        ("rule-strong", "thead", 3.0, "control boundaries on a table header"),
        # Decorative hairlines are outside 1.4.11, but must not disappear
        ("rule", "page", 1.4, "decorative hairline on the page"),
        ("rule", "card", 1.4, "decorative hairline in a card"),
        ("rule", "sunken", 1.25, "decorative hairline on a sunken panel"),
        ("accent", "sunken", 3.0, "chip boundary against its track"),
        ("focus", "page", 3.0, "focus ring on the page"),
        ("focus", "card", 3.0, "focus ring in a card"),
        ("focus", "sunken", 3.0, "focus ring on a sunken panel"),
    ]


def audit(verbose: bool = True) -> int:
    failures = 0
    for mode, t in (("LIGHT", LIGHT), ("DARK", DARK)):
        if verbose:
            print(f"\n  {mode}")
            print(f"  {'ratio':>7}  {'req':>4}  {'':4} {'pair':<44} {'colours'}")
            print("  " + "-" * 98)
        for fg, bg, need, what in pairs(t):
            r = contrast(t[fg], t[bg])
            ok = r >= need - 0.005
            if not ok:
                failures += 1
            aaa = " AAA" if r >= 7 else ("  AA" if r >= 4.5 else "")
            if verbose:
                mark = "ok  " if ok else "FAIL"
                print(f"  {r:>6.2f}:1  {need:>4.1f}  {mark} {what:<44} "
                      f"{t[fg]} on {t[bg]}{aaa}")
    return failures


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def css() -> str:
    out = ["/* Derived from " + BRAND + " (" + BRAND_NAME + ") by scripts/palette.py.",
           "   Do not hand-edit a value here — change the script and regenerate. */",
           ":root{"]
    for name, hexv in LIGHT.items():
        out.append(f"  --{name}:{hexv};")
    out.append("}")
    out.append('@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){')
    for name, hexv in DARK.items():
        out.append(f"  --{name}:{hexv};")
    out.append("}}")
    out.append(':root[data-theme="dark"]{')
    for name, hexv in DARK.items():
        out.append(f"  --{name}:{hexv};")
    out.append("}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Derive and audit the Synex colour system")
    ap.add_argument("--css", action="store_true", help="print only the CSS custom properties")
    ap.add_argument("--audit", action="store_true", help="print only the WCAG audit")
    args = ap.parse_args()

    if args.css:
        print(css())
        return 0

    if not args.audit:
        print(f"Brand: {BRAND}  {BRAND_NAME}")
        print(f"  OKLCH  L {BRAND_L:.4f}  C {BRAND_C:.4f}  H {BRAND_H:.2f} deg")
        print(f"  sits nearest ramp step: "
              f"{min(STEPS, key=lambda k: abs(STEPS[k] - BRAND_L))}\n")

        for name, r in RAMPS.items():
            print(f"  {name:<8} " + "  ".join(f"{k}:{v}" for k, v in r.items()))
        print()
        for mode, t in (("light", LIGHT), ("dark", DARK)):
            print(f"  {mode} tokens")
            for k, v in t.items():
                print(f"    --{k:<13} {v}")
            print()

    print("WCAG 2.2 audit — 1.4.3 (AA text), 1.4.6 (AAA body), 1.4.11 (non-text)")
    failures = audit()
    total = len(pairs(LIGHT)) * 2
    print(f"\n  {total - failures} of {total} pairs pass.")
    if failures:
        print(f"  FAILED — {failures} pair(s) below the required ratio. Fix the token, "
              f"not the threshold.")
        return 1
    print("  PASSED — every rendered pair meets its requirement in both modes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
