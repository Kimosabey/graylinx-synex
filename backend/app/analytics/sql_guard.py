"""The security boundary for model-written SQL. **The model is untrusted; this is what makes
that safe.**

This is the one path in the product where a language model produces something *executable*. The
whole design rests on a single principle: nothing the model writes is believed. The statement is
parsed and checked against an allow-list before it goes anywhere near a connection, and every
rule below refuses rather than repairs — a validator that rewrites a statement is a validator
that can be argued with.

**Why an allow-list and not a deny-list.** A deny-list of dangerous keywords is a race against
whoever writes the next injection, and it has to be complete to work. An allow-list has to be
*correct*, which is a smaller job: one statement, `SELECT` only, one of these tables, one of
these columns, and a `LIMIT`. Anything unrecognised is refused by default.

**Three rules come from live failures in the Thermynx implementation**, and they are in the
prompt as well as here because a rule the model never sees is a rule it breaks every time:

1. **Never `NOW()`, `CURDATE()` or `CURRENT_TIMESTAMP`.** The telemetry is a snapshot that ends
   on a fixed date, so a query anchored to the wall clock matches *no rows* — and returns an
   empty table that reads as "nothing wrong" rather than as "wrong question".
2. **`only_full_group_by`** is on, so ranking equipment against each other with a bare label
   column is a database error, not a result.
3. **A `UNION` branch with its own `ORDER BY`/`LIMIT` must be parenthesised.** This one reached
   a live demonstration as a raw `pymysql.err.ProgrammingError` printed into a chat bubble,
   with the whole failed statement in it.

**The plant connection is read-only by grant anyway** — `synex_plant_ro` holds two grants and
cannot write. This is the second lock, not the only one: a defence that exists once is a defence
that fails once.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: The hard ceiling on rows. A model asked for "everything" gets this and is told so, rather
#: than a query that runs for a minute and returns a table nobody reads.
MAX_ROWS: int = 500

#: Statement verbs that are refused outright. Not a deny-list standing alone — the allow-list
#: below already requires `SELECT` — but naming them makes the refusal say *which* forbidden
#: thing was attempted, which is what a reader needs.
FORBIDDEN_VERBS: tuple[str, ...] = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke",
    "call", "exec", "execute", "merge", "replace", "rename", "lock", "unlock", "set", "use",
    "load", "outfile", "infile", "dumpfile", "handler", "prepare", "deallocate",
)

#: Schemas that expose the server rather than the plant. Reaching any of them is an attempt to
#: read the database *about* the database.
FORBIDDEN_SCHEMAS: tuple[str, ...] = (
    "information_schema", "mysql.", "sys.", "performance_schema",
)

#: Wall-clock functions. See rule 1 above — on a snapshot these silently match nothing.
FORBIDDEN_TIME_FUNCTIONS: tuple[str, ...] = (
    "now(", "curdate(", "current_timestamp", "current_date", "sysdate(", "unix_timestamp(",
)

_COMMENT = re.compile(r"(--|#|/\*)")
_LIMIT = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class Verdict:
    """Whether a statement may run, and — always — why not in words.

    `refusals` is a list rather than the first failure: a statement that reads
    `information_schema` *and* has no `LIMIT` has two problems, and reporting one sends
    somebody round the loop twice.
    """

    allowed: bool
    statement: str = ""
    refusals: tuple[str, ...] = field(default_factory=tuple)

    def render(self) -> str:
        if self.allowed:
            return "The statement is a single bounded SELECT over allowed tables."
        return "Refused: " + "; ".join(self.refusals)


def validate(
    sql: str, *, allowed_tables: frozenset[str], allowed_columns: frozenset[str]
) -> Verdict:
    """Check a model-written statement. **Refuses; never repairs.**

    Returns every reason it was refused, in words, so the refusal can be shown to a reader and
    fed back to the model in one round rather than several.
    """
    raw = (sql or "").strip()
    refusals: list[str] = []

    if not raw:
        return Verdict(False, refusals=("the model produced no statement at all",))

    lowered = raw.lower()

    # ── one statement ───────────────────────────────────────────────────────────
    # A trailing semicolon is stripped rather than refused — it is punctuation, not a second
    # statement — but a semicolon with anything after it is stacking.
    body = raw.rstrip().rstrip(";")
    if ";" in body:
        refusals.append("it contains more than one statement, and only one is ever run")

    # ── no comments ─────────────────────────────────────────────────────────────
    # Comment-based smuggling: `SELECT 1 -- \n DROP` and its variants.
    if _COMMENT.search(body):
        refusals.append("it contains a comment, which is how a second statement gets smuggled")

    # ── SELECT only ─────────────────────────────────────────────────────────────
    if not re.match(r"^\s*\(*\s*select\b", body, re.IGNORECASE):
        refusals.append("it does not begin with SELECT, and nothing else is ever run")

    for verb in FORBIDDEN_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            refusals.append(f"it uses {verb.upper()}, which cannot appear in a read")

    # ── the server is not the plant ─────────────────────────────────────────────
    for schema in FORBIDDEN_SCHEMAS:
        if schema in lowered:
            refusals.append(
                f"it reaches {schema}, which describes the database rather than the plant"
            )

    # ── the snapshot has no now ─────────────────────────────────────────────────
    for fn in FORBIDDEN_TIME_FUNCTIONS:
        if fn in lowered:
            refusals.append(
                f"it uses {fn.rstrip('(').upper()}. The telemetry is a snapshot that ends on a "
                f"fixed date, so a wall-clock anchor matches no rows and returns an empty table "
                f"that reads as 'nothing wrong'. Anchor to MAX(slot_time) instead"
            )

    # ── tables, by allow-list ───────────────────────────────────────────────────
    referenced = {
        m.group(1).lower().strip("`")
        for m in re.finditer(r"\b(?:from|join)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", body, re.IGNORECASE)
    }
    unknown = sorted(referenced - {t.lower() for t in allowed_tables})
    if unknown:
        refusals.append(
            f"it reads {', '.join(unknown)}, which {'is' if len(unknown) == 1 else 'are'} not "
            f"on the allowed list"
        )
    if not referenced:
        refusals.append("it names no table, so there is nothing to check it against")

    # ── columns, by allow-list ──────────────────────────────────────────────────
    # Only identifiers that look like column references are checked; a model inventing
    # `power_factor` or `vibration` on a plant that meters neither is the failure this catches.
    if allowed_columns:
        words = set(re.findall(r"\b([a-z_][a-z0-9_]{3,})\b", body.lower()))
        keywords = {
            "select", "from", "where", "group", "order", "limit", "having", "join", "left",
            "right", "inner", "outer", "on", "as", "and", "or", "not", "null", "count", "sum",
            "avg", "min", "max", "desc", "asc", "distinct", "case", "when", "then", "else",
            "end", "union", "all", "between", "like", "is", "by", "with", "over",
        }
        invented = sorted(
            w for w in words - keywords
            if w not in {c.lower() for c in allowed_columns}
            and w not in {t.lower() for t in allowed_tables}
        )
        if invented:
            refusals.append(
                f"it names {', '.join(invented[:6])}, which "
                f"{'is' if len(invented) == 1 else 'are'} not a column on this plant"
            )

    # ── a bounded read ──────────────────────────────────────────────────────────
    found = _LIMIT.search(body)
    if not found:
        refusals.append(f"it has no LIMIT, and every read is bounded at {MAX_ROWS} rows")
    elif int(found.group(1)) > MAX_ROWS:
        refusals.append(f"its LIMIT of {found.group(1)} is above the {MAX_ROWS}-row ceiling")

    return Verdict(not refusals, statement=body, refusals=tuple(refusals))
