"""A question in words becomes one bounded SELECT over this plant's telemetry.

**The class of question nothing else here can answer.** Every other path reads residuals — what
a fitted model predicted against what was measured — and four of the twelve tables have no
fitted model at all. Raw telemetry has none of that limitation: `comp1_kw` is a measured column
with 10,077 non-null readings on chiller 1 and 9,209 on chiller 2, so *"which chiller uses more
power"* is answerable from the readings even though `compressor_power_residual` is 100% NULL.
Those are two different facts about power and the product was conflating them into a refusal.

**The model is untrusted and `sql_guard` is what makes that safe.** This is the one path where
a language model produces something *executable*, and nothing it writes is believed: the
statement is parsed and checked against an allow-list before it reaches a connection. The
validator refuses and never repairs — a validator that rewrites a statement is a validator that
can be argued with. `synex_plant_ro` cannot write, which is the second lock rather than the
only one.

**devstral writes it, not the brain.** This is the `sql` role, and the division is the one the
roster settled: the brain plans and reasons, devstral executes. SQL is a short constrained
output, which is what devstral is for.

**A refusal comes back in words the model can act on.** When the guard rejects a statement the
reasons are quoted back and it is asked once more. One retry, because a model that produced
`information_schema` twice will produce it a third time, and each attempt costs a reader
several seconds of waiting.

**The rows are returned, never interpreted.** This path answers *"what does the data say"*, and
turning that into *"and therefore the machine is fouled"* is diagnosis, which the rules own.
The wording layer describes what came back and stops.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.analytics.sql_guard import MAX_ROWS, validate

#: Long enough for devstral to write a statement, short enough that a stuck call does not read
#: as a hung product. Two attempts fit inside a reader's patience; three do not.
TIMEOUT_S: float = 30.0

_SYSTEM = """You write ONE MySQL SELECT statement over an industrial chiller plant's telemetry.

RULES, and every one of them is enforced by a validator that will reject your statement:
- SELECT only. One statement. No semicolons except a trailing one. No comments.
- Only the tables and columns listed below. Inventing a column name is the commonest failure.
- Always include a LIMIT, and never above the ceiling you are given.
- NEVER use NOW(), CURDATE(), CURRENT_DATE or any wall-clock function. This telemetry is a
  fixed snapshot, so a wall-clock anchor matches no rows and returns an empty table that reads
  as "nothing wrong" rather than "wrong question". Anchor to MAX(slot_time) instead.
- `only_full_group_by` is on: every non-aggregated column in the select list must appear in
  GROUP BY.
- A UNION branch carrying its own ORDER BY or LIMIT must be parenthesised.
- `is_running = 1` filters to slots where the machine was actually on. A plant this size is
  stopped roughly three quarters of the time, so an average over every slot is an average
  mostly of zeros and answers a question nobody asked.
- `id` and `ss_id` identify a ROW, not a machine. Never GROUP BY either of them: grouping by
  `id` produces one group per reading, so an average comes back as the reading itself. The
  machine is the TABLE — to compare two machines, select from each and UNION the results with
  a literal naming the machine.
- One table per machine. There is no column that says which chiller a row belongs to.

A worked comparison, because this is the shape most often got wrong:
  SELECT 'chiller_1' AS machine, ROUND(AVG(comp1_kw), 1) AS avg_kw
  FROM chiller_1_normalized WHERE is_running = 1
  UNION ALL
  SELECT 'chiller_2', ROUND(AVG(comp1_kw), 1)
  FROM chiller_2_normalized WHERE is_running = 1
  LIMIT 10

Reply with the statement and nothing else. No prose, no explanation, no code fence."""


@dataclass(frozen=True)
class QueryResult:
    """What came back, or why nothing did."""

    statement: str = ""
    columns: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[tuple, ...] = field(default_factory=tuple)
    refusals: tuple[str, ...] = field(default_factory=tuple)
    error: str = ""

    @property
    def ran(self) -> bool:
        return bool(self.columns) and not self.error

    def render(self) -> str:
        """The rows as a reader sees them, or the refusal in its own words."""
        if self.error:
            return f"That question could not be turned into a query: {self.error}"
        if self.refusals:
            reasons = "; ".join(self.refusals)
            return (
                f"The query that was written could not be run: {reasons}. Nothing was executed "
                f"and nothing was assumed in its place."
            )
        if not self.rows:
            return (
                "The query ran and matched no rows. That is a fact about this snapshot rather "
                "than about the plant — a window with no readings is not a plant with no "
                "faults."
            )

        header = " | ".join(self.columns)
        body = "\n".join(
            " | ".join("—" if v is None else str(v) for v in row) for row in self.rows[:50]
        )
        more = (
            f"\n\n{len(self.rows)} row(s) returned; the first 50 are shown."
            if len(self.rows) > 50
            else ""
        )
        return f"{header}\n{body}{more}\n\nRead from: `{self.statement}`"


def _schema(tables: frozenset[str], columns: frozenset[str]) -> str:
    """The tables and columns the model may use, as the prompt shows them."""
    return (
        f"TABLES: {', '.join(sorted(tables))}\n\n"
        f"COLUMNS (the same set on every table): {', '.join(sorted(columns))}\n\n"
        f"ROW CEILING: {MAX_ROWS}"
    )


async def answer(
    question: str,
    *,
    client,
    repo,
    allowed_tables: frozenset[str],
    allowed_columns: frozenset[str],
) -> QueryResult:
    """Write a statement, check it, run it. **Never raises.**

    Every failure — an unreachable box, a timeout, a statement the guard refuses twice, a
    database error — comes back as a `QueryResult` a caller can render, because a stack trace
    is not an answer and on a demonstration it reads as a broken product.
    """
    if client is None or repo is None:
        return QueryResult(error="the query path needs both a model and a plant connection")

    schema = _schema(allowed_tables, allowed_columns)
    refusals: tuple[str, ...] = ()
    statement = ""

    for attempt in (1, 2):
        prompt = f"{schema}\n\nQUESTION: {question}"
        if attempt == 2 and refusals:
            # Quoted back rather than summarised: "be more careful" is advice, and a validator's
            # own words name the exact rule that was broken.
            prompt += (
                f"\n\nYour previous statement was:\n{statement}\n\n"
                f"It was REJECTED because: {'; '.join(refusals)}\n\n"
                f"Write it again, fixing exactly that."
            )

        try:
            completion = await asyncio.wait_for(
                client.complete(
                    role="sql",
                    task="write_sql",
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=TIMEOUT_S,
            )
        except TimeoutError:
            return QueryResult(error="the query writer did not answer in time")
        except Exception as cause:
            return QueryResult(
                error=f"the query writer could not be reached: {type(cause).__name__}"
            )

        statement = _strip(getattr(completion, "text", "") or "")
        verdict = validate(
            statement, allowed_tables=allowed_tables, allowed_columns=allowed_columns
        )
        if verdict.allowed:
            try:
                columns, rows = await repo.run_validated_select(
                    verdict.statement, max_rows=MAX_ROWS
                )
            except Exception as cause:
                return QueryResult(
                    statement=verdict.statement,
                    error=f"the database refused it: {type(cause).__name__}",
                )
            return QueryResult(statement=verdict.statement, columns=columns, rows=rows)

        refusals = verdict.refusals

    return QueryResult(statement=statement, refusals=refusals)


def _strip(raw: str) -> str:
    """Pull the statement out of whatever came back.

    Models fence SQL however they were feeling. The fence is removed rather than the reply
    rejected, because a correct statement wrapped in backticks is a formatting difference and
    refusing it would send a reader round the loop for nothing.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    if text.lower().startswith("sql\n"):
        text = text[4:].strip()
    return text
