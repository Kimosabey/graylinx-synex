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

### D-002 — The MVP cut grows from 51 to 69 after the Thermynx flow review
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing. S1 remains open — it now closes on 69 features, not 51
- **Decision:** Four groups of capability were in daily use in the existing
  Thermynx implementation, or are required for the loop to close, and were named
  nowhere in this register. They are registered and taken into the cut:
  the conversation shell `C15`–`C20`, the case-resolution lifecycle `RC1`–`RC8`,
  energy and cost `E1`–`E4` (only `E1` in the cut), and the three personas the
  loop cannot close without, `U6`–`U8`. Two new prefixes: `RC` and `E`.
- **Reason:** the earlier cut described a loop that went from a named fault
  straight to a work order. That hop does not exist in practice — somebody
  answers questions first, and some answers come back "could not check". The
  register also assumed a chat surface without naming any of it, while the
  Copilot is the product's differentiator. Registering these makes them
  reviewable; leaving them implicit meant they would be built without a spec.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `mvp/MVP-SCOPE.md` (13 acceptance
  criteria, 10 stages), `CONTEXT.md` §9–§11, `CLAUDE.md` §2 rule 7,
  `scripts/verify.py` `ID_PREFIX`, `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-003 — Synex inherits Thermynx's platform decisions rather than re-litigating them
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** The shared graylinx-v2 database, the Jarvis GPU box and the
  existing stack are used as they are. Thirteen decisions taken before this
  programme, with reasoning recorded against source, are adopted as settled
  truth and listed in `CONTEXT.md` §10. Where one of them constrains a feature,
  the register row says so.
- **Reason:** each of the thirteen was paid for. Two in particular were learned
  the hard way — six "N/A" presses once opened a blocking safety gate with no
  evidence behind it, and ranking checklist routing by seniority once sent a
  filter-drier restriction to a supervisor over three refrigeration
  measurements. Rediscovering those in production is not a reasonable plan.
- **Affects:** `CONTEXT.md` §9–§11; constrains `RC2`, `RC3`, `RC4`, `RC5`,
  `RC7`, `F7`, `F9`, `V7`, `W4`.
- **Reflected in docs:** partial. The constraints are in `CONTEXT.md`; the v4
  source document does not yet mention them and will pick them up at task T2.
- **Note:** three of the thirteen are open capability gaps rather than settled
  design — no interim holding action, no retraction mechanism, and duplicated
  checklist work under event grouping. They are inherited as unsolved. See Q19.
