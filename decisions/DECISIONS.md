# Decision log

Every decision that changes what gets built goes here, then into the affected
chapters. If it is not in this file, it did not happen.

## Format

```
### D-nnn — Short title
- **Date:**
- **Decided by:**
- **Closes:** (Qn / Nn, if applicable)
- **Decision:**
- **Reason:**
- **Affects:** chapters, feature IDs
- **Reflected in docs:** yes / no / partial
```

---

### D-001 — The Graylinx brand colour is `#0020B0`, and the design system is derived from it
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing — this is a new decision, not an answer to an open question
- **Decision:** `#0020B0` (International Klein Blue) is the brand colour. The
  full colour system — brand, neutral, success, warning and danger ramps, plus
  the light and dark semantic tokens — is generated from that single value by
  `scripts/palette.py`. `--accent` is the brand hex unmodified. The placeholder
  palette in `brand/NAMING.md` (`#0F3D5C` / `#1B6E9C`) is superseded and must not
  be reintroduced. Light is the default theme; dark is an explicit opt-in rather
  than an OS preference.
- **Reason:** `brand/NAMING.md` reserved that section to be replaced when a brand
  palette was issued, and one now has been. Deriving the whole system from one
  input rather than hand-picking values means the palette can be regenerated,
  and — more importantly — audited: `--audit` checks all 72 rendered pairs
  against WCAG 2.2 in both themes and fails the build rather than the user.
  Neutrals are placed on the brand hue so the greys belong to the blue.
- **Affects:** `brand/NAMING.md` (Visual identity replaced), `scripts/palette.py`
  (new), `mvp/MVP.html`, `assets/logo.png`. No feature IDs.
- **Reflected in docs:** yes for `brand/NAMING.md` and `mvp/MVP.html`. The v4
  source document in `docs/00-source/` still carries the placeholder palette and
  will pick this up when task T2 splits it into per-chapter markdown.
