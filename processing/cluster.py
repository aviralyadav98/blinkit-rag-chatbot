"""
Phase 2 step 4 — Cluster (docs/IMPLEMENTATION.md Phase 2, CLAUDE.md decided architecture).

HDBSCAN over embeddings, chosen over pure LLM-over-raw-corpus reads because
that approach is inconsistent and expensive at scale (CLAUDE.md) — clustering
first bounds how much text the LLM has to read per theme.

min_cluster_size defaults small (3) because this project's corpus is modest
in size (hundreds, not tens of thousands, of chunks) — HDBSCAN's usual
defaults (15+) would mark nearly everything as noise here. Revisit upward as
the corpus grows (Phase 8 incremental re-clustering).
"""

import hdbscan
import numpy as np
from sklearn.decomposition import PCA

# HDBSCAN degrades badly in very high dimensions: at bge-m3's 1024 dims, density
# becomes near-uniform (everything roughly equidistant) and the algorithm
# collapses the whole corpus into ~2 mega-clusters regardless of min_cluster_size.
# Reducing to a moderate dimensionality first is the standard recipe for
# clustering sentence embeddings and restores fine-grained, stable clusters.
# This reduction is used ONLY for clustering — the full 1024-d embeddings are
# still what gets stored in Chroma and used for retrieval.
PCA_DIMS = 50


def cluster_chunks(chunks: list[dict], min_cluster_size: int = 3) -> list[dict]:
    """Adds a `cluster_id` field to each chunk (-1 means HDBSCAN treated it as noise)."""
    if len(chunks) < min_cluster_size:
        for chunk in chunks:
            chunk["cluster_id"] = -1
        return chunks

    embeddings = np.array([c["embedding"] for c in chunks])

    n_comp = min(PCA_DIMS, embeddings.shape[0] - 1, embeddings.shape[1])
    features = (
        PCA(n_components=n_comp, random_state=0).fit_transform(embeddings)
        if n_comp >= 2
        else embeddings
    )

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    labels = clusterer.fit_predict(features)
    for chunk, label in zip(chunks, labels):
        chunk["cluster_id"] = int(label)
    return chunks
