"""Plain English for a reader, with our own filing removed.

**The defect this fixes.** Answers were shipping our internal references to a plant engineer:
*"Severity: severity not yet agreed (Q49)"*, *"the two columns are swapped or mislabelled. F16"*,
*"a stated absence rather than a number. C21"*. `Q49` is an open question in this repository,
`F16` is a feature id, `C21` is a constraint, `D-009` is a decision. To the person reading, they
are ticket numbers from somebody else's system appearing inside a sentence about their chiller.

**They are not removed from the data — only from the prose.** Every one of those references is
load-bearing internally: it is how a reader of *this repository* finds why a signal is
distrusted, and stripping it at source would cost the traceability the notes exist for. So the
note keeps its reference and the *answer* drops it, and the Inspector shows the full note where
somebody investigating actually wants it.

**Also the parenthetical about our own plumbing.** *"(from the signal registry, not
recomputed)"* is a statement about where Synex looked, not about the plant. It matters in a
provenance panel and it is noise in a sentence about condenser flow.
"""
from __future__ import annotations

import re

#: Our filing, in every form it appears in a note. Ordered longest-first so `D-009` is not
#: left as a stray `D-` by a shorter pattern matching first.
_INTERNAL_REF = re.compile(
    r"\s*[—–-]?\s*\(?\b(?:D-\d{3}|Q\d{1,3}|F\d{1,2}|C\d{1,2}|RC\d{1,2}|W\d{1,2}|S\d{1,2}|G\d{1,2}|V\d{1,2}|K\d{1,2})\b\)?\.?"
)

#: A note about where Synex looked rather than about the plant.
_PLUMBING = re.compile(r"\s*\((?:from the signal registry[^)]*|recomputed[^)]*)\)")


def for_reader(text: str) -> str:
    """Strip our filing from a sentence a plant engineer will read.

    Conservative by construction: it removes references and one parenthetical and touches
    nothing else. A number, a signal name, a band or a verdict is never altered — those are the
    content, and `C21`'s discipline is that the back end renders every figure exactly once.
    """
    if not text:
        return text
    out = _PLUMBING.sub("", text)
    # Keep the sentence break the reference was carrying. Removing "— Q8." wholesale ran two
    # sentences together: "cannot be computed at all Absent entirely from the window."
    out = _INTERNAL_REF.sub(lambda m: "." if m.group(0).rstrip().endswith(".") else "", out)
    # Tidy what removal leaves behind: doubled spaces, a space before punctuation, and a
    # sentence that now ends on a dangling dash.
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.;,])", r"\1", out)
    out = re.sub(r"[—–-]\s*$", "", out).strip()
    # A reference that was already ending a sentence leaves the full stop doubled.
    out = re.sub(r"\.{2,}", ".", out)
    # A note reduced to nothing but punctuation is an empty note, and an empty string is a
    # clearer absence than a lone full stop.
    return "" if not re.search(r"[A-Za-z0-9]", out) else out
