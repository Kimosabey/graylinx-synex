#!/usr/bin/env python3
"""Populate the retrieval store — `K1` SOP search, `K5` source-visible answers.

    cd backend
    python ../scripts/ingest_corpus.py --check                 what would happen; writes nothing
    python ../scripts/ingest_corpus.py --ingest                chunk, embed, store
    python ../scripts/ingest_corpus.py --verify                search it and read the citations

    python ../scripts/ingest_corpus.py --approve "<document>" --by "<who>" --basis "<why>"
    python ../scripts/ingest_corpus.py --revoke  "<document>" --by "<who>" --reason "<why>"

---

**What this fixes.** `synex_document_chunk` had a reader and no writer for anything but the
transcribed checklist library. The table, the cosine search, the chunker, the passage types and
the embedder all existed; the written chapters and the FDD specification — the documents `K5`
is *about* — had no producer at all. So `K1` and `K5` retrieved nothing, and a retrieval layer
that returns nothing is indistinguishable from a library that holds nothing.

**Idempotent, and here is how.** Every passage carries `source_digest`, the SHA-256 of the
whole source text it was chunked from. `--ingest` reads the inventory before it writes, so a
document is `ingested` when the store holds none of it, `unchanged` when the digests match and
nothing is written at all, and `replaced` when the source text changed — old passages deleted
and new ones written in one transaction. A stored digest that is *unknown* counts as changed,
never as current. Running this twice in a row writes nothing the second time, and `--check`
says so before you commit to it.

**`--ingest` approves nothing, and that is deliberate.** It cannot: there is no keyword for it
anywhere in the path. After a successful run search still returns nothing, because
`is_approved` defaults `False` and search reads approved passages only. Nothing in the corpus
has been read by a refrigeration engineer — the SME hour with Vishnu is blocker `RC2` — and
content that directs physical work on pressurised refrigerant equipment does not become
retrievable by being copied into a database.

**Approval is therefore its own act, with a name on it.** `--approve` demands `--by` and
`--basis` and records both, marks the approval **provisional — pending SME validation**, and
writes an audit row. The provisional state is printed inside the citation, so a passage that
reaches an answer says on its face that a persona approved it and an engineer has not.
`--revoke` withdraws it; the audit row survives, so the real review can find every provisional
approval, read what was claimed for it, and undo it. `Q105`, `D-018`.

**This never touches the plant.** It reads files out of the repository and writes to Synex's own
PostgreSQL. `graylinx_synex` is not opened. The embedder is `nomic-embed-text` on the host CPU
at 127.0.0.1:11434, so the Jarvis GPU box is not needed and is not contacted.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Windows consoles default to cp1252, which cannot encode the section marks and dashes this
# script prints — and a UnicodeEncodeError while reporting is a crash *before* the useful
# output rather than after it. `scripts/record_on_box.py` carries the same two lines.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _hr(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 68 - len(title)))


async def check() -> int:
    """Read-only. What is on disk, what is in the store, and what a run would do to it."""
    from app.config import Settings
    from app.db.session import create_state_schema, state_session
    from app.jobs.corpus import read_docx  # noqa: F401 — imported to fail early if unusable
    from app.jobs.ingest_corpus import Outcome, _decide, all_sources
    from app.llm.embeddings import Embedder
    from app.retrieval.sop import SopIndex

    settings = Settings()

    _hr("the corpus on disk")
    found = all_sources(REPO_ROOT)
    for document in found.documents:
        print(f"  {document.render()}")
    for problem in found.unreadable:
        print(f"  UNREADABLE {problem}")

    _hr("what is deliberately not ingested")
    for refusal in found.refused:
        print(f"  {refusal.render()}")

    _hr("the embedder")
    embedder = Embedder(settings.embed_host)
    reachable = await embedder.available()
    print(f"  host:  {settings.embed_host}")
    print(f"  model: {embedder.model}")
    print(f"  {'reachable' if reachable else 'UNREACHABLE — start Ollama and pull the model'}")

    _hr("the store")
    try:
        # Creating an absent table is not a write to the corpus — `create_state_schema` never
        # drops or alters, and `--check` that could not reach a store it is about to describe
        # would report "unreachable" for a database that is running perfectly well.
        await create_state_schema(settings)
        async with state_session(settings) as session:
            index = SopIndex(session, embedder)
            await index.ensure_columns()
            held = {record.document: record for record in await index.inventory()}
            provisional = await index.provisional_documents()
            trail = await index.approval_trail()
    except Exception as exc:  # noqa: BLE001 — the reason is the output
        print(f"  UNREACHABLE — {exc}")
        print("\n  docker compose -f infra/docker-compose.yml up -d postgres")
        return 1

    print(f"  {sum(r.passages for r in held.values())} passage(s) across "
          f"{len(held)} document(s); {sum(r.approved for r in held.values())} approved, "
          f"{sum(r.provisional for r in held.values())} of those provisional")

    _hr("what --ingest would do")
    counts: dict[str, int] = {}
    for document in found.documents:
        outcome, reason = _decide(document, held.get(document.title))
        counts[outcome.value] = counts.get(outcome.value, 0) + 1
        if outcome is not Outcome.UNCHANGED:
            print(f"  {outcome.value:<10} {document.title} — {reason}")
    print(f"  {counts}")
    if counts.get(Outcome.UNCHANGED.value) == len(found.documents):
        print("  nothing would be written — the corpus is current. That is idempotency,")
        print("  not a refusal: a changed document would be replaced on the next run.")

    _hr("approvals pending SME validation")
    if provisional:
        for title in sorted(provisional):
            print(f"  {title}")
        print(f"\n  {len(provisional)} document(s) approved by a persona and validated by no")
        print("  refrigeration engineer. This is RC2's worklist; --revoke undoes any of them.")
    else:
        print("  none")
    for event in trail:
        print(f"  {event.render()}")

    print()
    return 0 if reachable else 1


async def ingest() -> int:
    """Chunk, embed and store. Writes to Synex's own Postgres and approves nothing."""
    from app.config import Settings
    from app.jobs.ingest_corpus import ingest_corpus

    _hr("ingesting")
    run = await ingest_corpus(Settings(), REPO_ROOT)
    print(run.render())

    _hr("what to do next")
    print("  Search returns nothing until a document is approved, and approving is a separate")
    print("  act with a name on it:")
    print('    python ../scripts/ingest_corpus.py --approve "<document>" \\')
    print('        --by "<who>" --basis "<why, in words>"')
    print("  Every approval it can grant is provisional, pending SME validation (RC2).")
    print()
    return 0


async def verify() -> int:
    """Search the store and print the citations. The half a row count cannot prove."""
    from app.config import Settings
    from app.db.session import state_session
    from app.llm.embeddings import Embedder
    from app.retrieval.sop import SopIndex

    questions = (
        "how do I make the compressor safe before opening the refrigerant circuit",
        "what does a high discharge pressure residual mean",
        "what is checked when condenser flow is low",
    )

    settings = Settings()
    async with state_session(settings) as session:
        index = SopIndex(session, Embedder(settings.embed_host))

        _hr("the corpus")
        for record in await index.inventory():
            approved = (
                f"{record.approved} approved"
                + (f", {record.provisional} provisional" if record.provisional else "")
                if record.approved
                else "unapproved"
            )
            print(f"  {record.passages:>3} passage(s)  {record.kind:<10} {approved:<28} "
                  f"{record.document}")

        _hr("K1 · K5 — search, and what every passage cites")
        for question in questions:
            result = await index.search(question)
            print(f"\n  Q: {question}")
            if not result.available:
                print(f"     unavailable — {result.reason}")
                continue
            if not result.passages:
                print(f"     {result.render().splitlines()[0]}")
                continue
            for passage in result.passages:
                print(f"     {passage.citation}")

        _hr("S4 — safety is narrower")
        safety = await index.search_safety("what protective equipment is required")
        print(f"  {safety.render().splitlines()[0]}")

    print()
    return 0


async def approve(document: str, actor: str, basis: str) -> int:
    from app.config import Settings
    from app.db.session import state_session
    from app.llm.embeddings import Embedder
    from app.retrieval.sop import SopIndex

    settings = Settings()
    async with state_session(settings) as session:
        index = SopIndex(session, Embedder(settings.embed_host))
        held = {record.document for record in await index.inventory()}
        if document not in held:
            print(f"\n  {document!r} is not in the corpus. Run --check to list what is.")
            return 2
        event = await index.approve(document, actor=actor, basis=basis)

    _hr("approved")
    print(f"  {event.render()}")
    print("\n  This approval is PROVISIONAL. Every passage of this document now cites itself")
    print("  as 'approved pending SME validation', so an answer built on it cannot read as")
    print("  reviewed content. --revoke undoes it and the audit row survives the undoing.")
    print()
    return 0


async def revoke(document: str, actor: str, reason: str) -> int:
    from app.config import Settings
    from app.db.session import state_session
    from app.llm.embeddings import Embedder
    from app.retrieval.sop import SopIndex

    settings = Settings()
    async with state_session(settings) as session:
        index = SopIndex(session, Embedder(settings.embed_host))
        event = await index.revoke(document, actor=actor, reason=reason)

    _hr("revoked")
    print(f"  {event.render()}")
    print("\n  The passages are unsearchable again. The approval that was withdrawn is still")
    print("  in the trail — 'nobody ever approved this' and 'somebody did and it was")
    print("  withdrawn' are different findings, and a review needs the second one.")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Populate and govern the K1/K5 retrieval corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--check", action="store_true", help="inspect and stop; writes nothing")
    ap.add_argument("--ingest", action="store_true", help="chunk, embed and store")
    ap.add_argument("--verify", action="store_true", help="search it and read the citations")
    ap.add_argument("--approve", metavar="DOCUMENT", help="make one document searchable")
    ap.add_argument("--revoke", metavar="DOCUMENT", help="withdraw an approval")
    ap.add_argument("--by", metavar="WHO", help="who is taking responsibility. Required")
    ap.add_argument("--basis", metavar="WHY", help="why, in words. Required to approve")
    ap.add_argument("--reason", metavar="WHY", help="why, in words. Required to revoke")
    args = ap.parse_args()

    if args.approve:
        if not (args.by and args.basis):
            ap.error(
                "--approve needs --by and --basis. An approval attributable to nobody, for no "
                "recorded reason, is what an unapproved procedure looked like the last time "
                "one reached a technician"
            )
        return asyncio.run(approve(args.approve, args.by, args.basis))

    if args.revoke:
        if not (args.by and args.reason):
            ap.error("--revoke needs --by and --reason, for the same reason --approve does")
        return asyncio.run(revoke(args.revoke, args.by, args.reason))

    if args.check:
        return asyncio.run(check())
    if args.ingest:
        return asyncio.run(ingest())
    if args.verify:
        return asyncio.run(verify())

    ap.error("pass --check, --ingest, --verify, --approve or --revoke")
    return 2


if __name__ == "__main__":
    # psycopg3 cannot run async on Windows' default ProactorEventLoop. `app/runtime.py` sets
    # the selector policy, and it has to happen before any loop is created — see the note there.
    sys.path.insert(0, str(BACKEND))
    from app.runtime import use_psycopg_compatible_event_loop

    use_psycopg_compatible_event_loop()
    sys.exit(main())
