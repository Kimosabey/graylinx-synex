"""Embeddings — 768 dimensions, and they never leave the site.

**The one model role that is not on the box.** `nomic-embed-text` is 274 MB against the
roster's 41 GB at Q4, so it runs on the host CPU rather than the rented GPU. That is not a
compromise: `CONTEXT.md` §4 marks it *"always local"*, and it means retrieval — `K1` SOP
search, `S4` safety answers from the SOP — works with the box terminated, which is the same
property every other gate in this repository holds.

**Why the dimension is locked and not configured.** `infra/sql/02-postgres-extensions.sql`
says it plainly: changing the embedding model invalidates every vector already stored. So a
model swap is a **migration**, not a setting — which is why `embed` is the one role excluded
from `app.llm.models.EDITABLE`, and why `DIMENSIONS` is asserted against what the server
actually returns rather than trusted.

**Code never names a model.** This module asks `app.llm.models` for the `embed` role, like
every other call site. It is one of the two modules permitted to reach a client at all —
contract 5 in `importlinter.ini`, with an AST test that fails if a model name appears
outside the role table.

**An unreachable embedder is a stated absence, never a zero vector.** Returning zeros would
make every document equidistant from every query and the search would silently return the
first row of the table — confidently, and wrongly. It raises instead.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.llm.models import model_for

#: Locked to `nomic-embed-text`. Not configurable — see the module docstring.
DIMENSIONS: int = 768

#: Long enough for a slow first call on a cold CPU model, short enough that a hung Ollama
#: fails a request rather than holding a worker. The roster's own ceilings live in
#: `app/config.py`; this one is local to the embedder because it is a different machine.
TIMEOUT_SECONDS: float = 60.0


class EmbeddingUnavailable(RuntimeError):
    """The embedder could not be reached, or returned something unusable.

    Deliberately an exception rather than an empty result. A zero vector would make every
    document equidistant from every query, so the search would return whatever came first
    and look like it had worked.
    """


@dataclass(frozen=True)
class Embedding:
    """One vector, with what produced it carried alongside.

    The model name travels with the vector because a table holding embeddings from two
    different models is silently broken — the numbers are all valid floats and the distances
    between them are meaningless.
    """

    text: str
    vector: tuple[float, ...]
    model: str

    def __post_init__(self) -> None:
        if len(self.vector) != DIMENSIONS:
            raise EmbeddingUnavailable(
                f"the embedder returned {len(self.vector)} dimensions and this store is "
                f"built for {DIMENSIONS}. Every vector already stored was produced by a "
                f"different model, so this is a migration rather than a bad response."
            )


class Embedder:
    """Reaches the local embedding model. One entry point, like `ModelClient`."""

    def __init__(self, host: str, timeout: float = TIMEOUT_SECONDS) -> None:
        self._host = host.rstrip("/")
        self._timeout = timeout

    @property
    def model(self) -> str:
        """Resolved from the role table, never named here."""
        return model_for("embed")

    async def available(self) -> bool:
        """Is the model actually pulled? A surface can then say *why* search is unavailable
        rather than returning nothing and letting a reader assume the library is empty."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._host}/api/tags")
                response.raise_for_status()
                names = {m.get("name", "").split(":")[0] for m in response.json().get("models", [])}
                return self.model.split(":")[0] in names
        except (httpx.HTTPError, ValueError):
            return False

    async def embed(self, text: str) -> Embedding:
        """One vector. Raises rather than returning zeros — see `EmbeddingUnavailable`."""
        payload = {"model": self.model, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._host}/api/embeddings", json=payload)
                response.raise_for_status()
                vector = response.json().get("embedding")
        except httpx.HTTPError as exc:
            raise EmbeddingUnavailable(
                f"the embedding model {self.model!r} could not be reached at {self._host}: "
                f"{exc}. Retrieval is unavailable — which is a stated absence, not an empty "
                f"result set."
            ) from exc

        if not vector:
            raise EmbeddingUnavailable(
                f"{self.model!r} returned no embedding for a {len(text)}-character input."
            )
        return Embedding(text=text, vector=tuple(float(v) for v in vector), model=self.model)

    async def embed_all(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]:
        """Sequential on purpose.

        The embedder is a CPU model on the host machine; firing a hundred concurrent requests
        at it makes every one slower and none of them finish sooner. The corpus is 131
        checklist items and a handful of documents — this is not the bottleneck.
        """
        return tuple([await self.embed(text) for text in texts])
