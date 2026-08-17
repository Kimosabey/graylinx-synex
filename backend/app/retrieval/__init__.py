"""Retrieval — `K1` SOP search, `K5` source-visible answers, `S4` safety from the SOP.

Sits between `app.services` and `app.llm` in the spine. It may reach the embedder (which is
`app.llm`) and the document store (`app.db`), and nothing reaches *into* it except services.

Runs with the GPU terminated: the embedder is `nomic-embed-text` at 274 MB on the host CPU,
not on the rented card.
"""
