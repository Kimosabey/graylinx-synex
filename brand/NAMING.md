# Naming and identity

## Product names

| Level | Name | Notes |
|---|---|---|
| Platform | **Graylinx Synex** | Full name on covers, first mention, legal and commercial copy |
| Platform, short | **Synex** | Every mention after the first, within the same document |
| Assistant | **Synex Copilot** | First mention in any chapter |
| Assistant, short | **the Copilot** | After first mention |
| Diagnostics | **Synex FDD** or **the FDD engine** | Never "the AI diagnosis" |
| Company | **Graylinx** | The company, never the product |

## Rules

- `Synex` is always title case. Never `SYNEX`, never `synex`, except in
  filenames and code identifiers where lowercase is conventional.
- Never write **"Synex AI"**. The intelligence is implied; the doubling reads as
  marketing filler.
- Never write **"the Synex chatbot"**. It is a copilot, and the word chatbot
  undersells the product by about an order of magnitude.
- Do not narrow Synex to HVAC. HVAC is the first vertical. Copy that reads
  "Synex, the HVAC AI platform" is wrong and defeats the point of the name.
- In headings, prefer the short form once the document has established the full
  name: "3. The Synex Copilot" rather than "3. The Graylinx Synex AI Copilot".

## The name, explained (for decks and intros)

> **Synex** = **Sync** + **Nexus**.
> Sync, because it connects data, people, equipment and workflows.
> Nexus, because it is the central point they connect through.
> Short, modern, AI-native, and not tied to any one vertical.

Tagline: **Intelligent Operations, Connected by AI.**

## Legacy names to replace on sight

| Legacy | Replacement |
|---|---|
| Graylinx Enterprise AI Platform | Graylinx Synex |
| GEAP | Synex |
| AI Copilot / Graylinx AI Copilot | Synex Copilot |
| Chatbot / the bot / AI assistant | Synex Copilot |

## Unresolved — do not decide this yourself

**N1: How do Synex and Thermynx relate?** Until a human answers, write no
sentence that positions one as replacing, containing, superseding or being a
module of the other. If a sentence needs the relationship to make sense, mark
it `TBD (N1)` and move on.

## Visual identity

Carried forward from the current document set. If a brand palette is issued
later, this section is replaced by it.

**A brand palette has now been issued, so this section is that palette.** The
placeholder set (`#0F3D5C` heading ink, `#1B6E9C` accent) is superseded and must
not be reintroduced. See `decisions/DECISIONS.md` D-001.

### The one input

| Role | Value |
|---|---|
| Brand colour | `#0020B0` — International Klein Blue |
| OKLCH | L 0.3673 · C 0.2203 · H 264.12° |

Everything else is derived from it by `scripts/palette.py`. Nothing in the design
system is chosen by eye, and no hex is hand-written.

```bash
python scripts/palette.py            # ramps, tokens and the WCAG audit
python scripts/palette.py --css      # the CSS custom properties
python scripts/palette.py --audit    # the audit alone; exits 1 on any failure
```

### How the ramps are built

Ramps are generated in OKLCH so lightness steps are perceptually even, then
gamut-mapped into sRGB by **reducing chroma, never by clipping channels** —
clipping shifts the hue and the blue stops being the brand blue.

The neutrals sit on the brand's own hue with chroma capped at 0.018. That is why
no grey on the page reads as a foreign colour beside the blue, and it is the
single decision that makes the system feel like one thing.

| Ramp | 400 | 700 | 800 | 900 |
|---|---|---|---|---|
| brand | `#83ABFF` | `#1145D9` | `#0024C0` | `#001993` |
| neutral | `#A7ADB8` | `#565B65` | `#414650` | `#2F333D` |
| success (152°) | `#74C18A` | `#006E35` | `#005428` | `#003F1C` |
| warning (75°) | `#DAA14A` | `#7B5100` | `#5F3E00` | `#472D00` |
| danger (26°) | `#EE8F86` | `#AD0015` | `#87000E` | `#660008` |

Semantic hues are placed far from the brand's 264° so a status colour can never
be mistaken for a brand colour. Success and danger are separated in **lightness
as well as hue**, because roughly one man in twelve cannot separate them by hue.
Status is never carried by colour alone — `PASS`, `FAIL` and `UNKNOWN` are always
written out.

### Semantic tokens

Components use these names and never a raw hex. `--accent` is the brand colour
itself, unmodified, so `#0020B0` appears literally wherever the brand should be
felt.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--page` | `#FFFFFF` | `#1C2029` | page ground |
| `--card` | `#FFFFFF` | `#252A34` | cards, tables |
| `--sunken` | `#F6F9FF` | `#303541` | panels, filter tracks, row hover |
| `--thead` | `#E7EFFF` | `#364157` | table header fill |
| `--rule` | `#DEE4EF` | `#49505F` | decorative hairlines, gridlines |
| `--rule-strong` | `#8B919D` | `#828C9E` | control boundaries — the 3:1 token |
| `--ink` | `#001993` | `#CFDFFF` | headings |
| `--body` | `#2F333D` | `#E9EFFB` | body text |
| `--muted` | `#565B65` | `#A7ADB8` | secondary text |
| `--accent` | `#0020B0` | `#83ABFF` | links, chips, active states |
| `--on-accent` | `#FFFFFF` | `#0D1528` | text on an accent fill |
| `--focus` | `#1145D9` | `#83ABFF` | focus rings |
| `--ok` / `--warn` / `--stop` | `#005428` / `#472D00` / `#87000E` | `#74C18A` / `#DAA14A` / `#EE8F86` | PASS / caution / FAIL |

Two border tokens, because WCAG 1.4.11 does not treat them alike. `--rule` is a
decorative hairline and is exempt from 3:1; `--rule-strong` bounds an actual
control and is computed to clear 3:1 against the darkest surface it can sit on.
Conflating them is how a design system quietly fails an audit.

### Accessibility

`scripts/palette.py --audit` checks every foreground/background pair the
interface actually renders, in both themes, and exits non-zero on any failure:

| Criterion | Requirement |
|---|---|
| 1.4.3 Contrast (Minimum) | AA — body text ≥ 4.5:1, large text ≥ 3:1 |
| 1.4.6 Contrast (Enhanced) | AAA — body text ≥ 7:1 on page and card |
| 1.4.11 Non-text Contrast | control boundaries and focus ≥ 3:1 |

**72 of 72 pairs pass.** If a pair fails, the token is wrong — do not lower the
threshold. Body and heading text clear AAA on every primary surface.

Light is the default theme everywhere. Dark is an explicit opt-in, not an OS
preference, so a document opens the same way for everyone it is sent to.

### Typography

| Role | Stack |
|---|---|
| Headings | Inter Semibold → Segoe UI Semibold → system |
| Body | Inter → Segoe UI Variable Text → Segoe UI → system |
| Code, IDs, residuals | Cascadia Mono → Consolas → SF Mono → Menlo |

Inter first where it is installed, a system fallback otherwise — no web font is
ever fetched, because the platform is on-premise by default and a document must
render with no network. Numeric columns use tabular figures so a column does not
shift width row to row.

Print: body 10.5 pt, table type 8.5 pt, headings 17 / 12.5 / 10.5 pt.
Tables: header row shaded and repeating, hairline borders, no vertical emphasis.

### The wordmark

`assets/logo.png` is the master — a transparent-alpha PNG whose ink is the brand
blue. The brand blue is too dark to read on a dark surface, so anything with a
dark theme must ship **two ink variants of the same alpha mask** rather than
filtering or inverting the logo. `mvp/MVP.html` shows the pattern.
