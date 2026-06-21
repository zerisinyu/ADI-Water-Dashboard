"""
Retrieval-Augmented Generation (RAG) over the AUDC Data Dictionary.

Uses TF-IDF to find the most relevant indicator definitions for a user
query, then formats them as context for the LLM system prompt.
No external vector database required.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "Data"

_index_built = False
_documents: list[str] = []
_metadata: list[dict] = []
_vectorizer = None
_tfidf_matrix = None


def _build_index() -> None:
    """Build the TF-IDF index from data dictionary and descriptions CSVs."""
    global _index_built, _documents, _metadata, _vectorizer, _tfidf_matrix

    if _index_built:
        return

    docs = []
    meta = []

    # 1. Load AUDC Data Dictionary
    dict_path = DATA_DIR / "AUDC Data dictionary.csv"
    if dict_path.exists():
        try:
            df = pd.read_csv(dict_path, encoding="utf-8", on_bad_lines="skip")
            # Normalise column names
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            for _, row in df.iterrows():
                indicator = str(row.get("high_level_indicators", "")).strip()
                if not indicator or indicator == "nan":
                    continue
                page = str(row.get("dashboard_page", "")).strip()
                domain = str(row.get("water_supply_or_sanitation", "")).strip()
                freq = str(row.get("frequency", "")).strip()
                granularity = str(row.get("granularity", "")).strip()
                variables = str(row.get("related_variables_in_datasets", "")).strip()
                calc = str(row.get("description/calculation", "")).strip()

                doc_text = (
                    f"Indicator: {indicator}. "
                    f"Domain: {domain}. Page: {page}. "
                    f"Frequency: {freq}. Granularity: {granularity}. "
                    f"Variables: {variables}. "
                    f"Calculation: {calc}"
                )
                docs.append(doc_text)
                meta.append({
                    "indicator": indicator,
                    "domain": domain,
                    "page": page,
                    "frequency": freq,
                    "variables": variables,
                    "calculation": calc,
                })
        except Exception:
            logger.exception("Failed to load AUDC Data dictionary")

    # 2. Load data_descriptions.csv
    desc_path = DATA_DIR / "data_descriptions.csv"
    if desc_path.exists():
        try:
            df = pd.read_csv(desc_path, encoding="utf-8", on_bad_lines="skip")
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            for _, row in df.iterrows():
                table = str(row.get("table_name", "")).strip()
                var = str(row.get("variables", "")).strip()
                desc = str(row.get("description", "")).strip()
                freq = str(row.get("frequency", "")).strip()
                gran = str(row.get("granularity", "")).strip()

                if not var or var == "nan":
                    continue

                doc_text = (
                    f"Variable: {var} in table {table}. "
                    f"Description: {desc}. "
                    f"Frequency: {freq}. Granularity: {gran}."
                )
                docs.append(doc_text)
                meta.append({
                    "indicator": f"{table}.{var}",
                    "domain": "",
                    "page": "",
                    "frequency": freq,
                    "variables": var,
                    "calculation": desc,
                })
        except Exception:
            logger.exception("Failed to load data_descriptions")

    if not docs:
        logger.warning("No documents loaded for RAG index")
        _index_built = True
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        _vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2),
        )
        _tfidf_matrix = _vectorizer.fit_transform(docs)
        _documents = docs
        _metadata = meta
        _index_built = True
        logger.info("RAG index built with %d documents", len(docs))
    except ImportError:
        logger.warning("scikit-learn not available; RAG disabled")
        _index_built = True


def retrieve_relevant_indicators(query_text: str, top_k: int = 3) -> str:
    """
    Retrieve the top-k most relevant indicator definitions for a query.

    Returns a formatted string suitable for LLM prompt injection.
    """
    _build_index()

    if _vectorizer is None or _tfidf_matrix is None or not _documents:
        return ""

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        query_vec = _vectorizer.transform([query_text])
        scores = cosine_similarity(query_vec, _tfidf_matrix).flatten()
        top_indices = scores.argsort()[-top_k:][::-1]

        parts = []
        for idx in top_indices:
            if scores[idx] < 0.05:  # Skip very low relevance
                continue
            m = _metadata[idx]
            parts.append(
                f"- {m['indicator']}: {m.get('calculation', '')} "
                f"(Variables: {m.get('variables', '')})"
            )

        return "\n".join(parts) if parts else ""
    except Exception:
        logger.exception("RAG retrieval failed")
        return ""
