"""
RAG (Retrieval-Augmented Generation) service for CodeSathi AI.

Handles:
- PDF text extraction via PyMuPDF
- TXT reading
- Text chunking with overlap
- Sentence-Transformer embeddings
- FAISS indexing and persistence
- Similarity search with source attribution
"""

from __future__ import annotations

import io
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHUNK_SIZE = 400       # target tokens (approx chars / 4)
CHUNK_OVERLAP = 80     # overlap between consecutive chunks
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K_RETRIEVAL = 5
SIMILARITY_THRESHOLD = 0.35   # cosine similarity; chunks below are discarded
FAISS_INDEX_FILE = "index.faiss"
CHUNK_STORE_FILE = "chunks.pkl"


def _index_dir() -> Path:
    d = Path(getattr(settings, "FAISS_INDEX_DIR", settings.BASE_DIR / "faiss_index"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Embedding model (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc
    return _embed_model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Return a float32 numpy array of shape (N, dim)."""
    model = _get_embed_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.astype(np.float32)


# ---------------------------------------------------------------------------
# FAISS index helpers
# ---------------------------------------------------------------------------

def _load_faiss_index():
    """Load or create a FAISS flat L2 index."""
    try:
        import faiss  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is not installed. Run: pip install faiss-cpu"
        ) from exc
    index_path = _index_dir() / FAISS_INDEX_FILE
    if index_path.exists():
        return faiss.read_index(str(index_path))
    # Create new index — dimension determined on first insertion
    return None


def _save_faiss_index(index) -> None:
    try:
        import faiss  # type: ignore
    except ImportError:
        return
    faiss.write_index(index, str(_index_dir() / FAISS_INDEX_FILE))


def _load_chunk_store() -> list[dict]:
    """Load the list of chunk metadata dicts from disk."""
    path = _index_dir() / CHUNK_STORE_FILE
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return []


def _save_chunk_store(store: list[dict]) -> None:
    path = _index_dir() / CHUNK_STORE_FILE
    with open(path, "wb") as f:
        pickle.dump(store, f)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> list[dict]:
    """
    Extract text from a PDF.
    Returns list of dicts: {"page": int, "text": str}
    """
    try:
        import fitz  # PyMuPDF  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed. Run: pip install pymupdf"
        ) from exc
    pages = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            pages.append({"page": page_num, "text": text})
    doc.close()
    return pages


def extract_text_from_txt(file_bytes: bytes) -> list[dict]:
    """Decode a text file. Returns single-page list."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace")
    return [{"page": 1, "text": text}]


def clean_text(text: str) -> str:
    """Basic text cleaning — collapse whitespace, remove null bytes."""
    import re
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_pages(pages: list[dict], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Split page texts into overlapping chunks.
    Each chunk dict: {"text": str, "page": int, "chunk_index": int}
    """
    chunks = []
    idx = 0
    for page_info in pages:
        text = clean_text(page_info["text"])
        words = text.split()
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "page": page_info["page"],
                    "chunk_index": idx,
                })
                idx += 1
            if end >= len(words):
                break
            start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Document indexing
# ---------------------------------------------------------------------------

def index_document(document_id: str, filename: str, chunks: list[dict]) -> list[int]:
    """
    Embed and add chunks to the FAISS index.
    Returns list of FAISS IDs assigned to each chunk.
    Persists index and chunk store to disk.
    """
    try:
        import faiss  # type: ignore
    except ImportError as exc:
        raise RuntimeError("faiss-cpu is not installed.") from exc

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    dim = embeddings.shape[1]

    # Load or create index
    index_path = _index_dir() / FAISS_INDEX_FILE
    if index_path.exists():
        index = faiss.read_index(str(index_path))
    else:
        index = faiss.IndexFlatIP(dim)  # Inner Product (cosine after normalise)

    # Normalise for cosine similarity
    faiss.normalize_L2(embeddings)

    # Current total vectors = base for new IDs
    base_id = index.ntotal
    index.add(embeddings)
    _save_faiss_index(index)

    # Update chunk store
    store = _load_chunk_store()
    faiss_ids = []
    for i, chunk in enumerate(chunks):
        fid = base_id + i
        store.append({
            "faiss_id": fid,
            "document_id": str(document_id),
            "filename": filename,
            "text": chunk["text"],
            "page_number": chunk.get("page"),
            "chunk_index": chunk["chunk_index"],
        })
        faiss_ids.append(fid)
    _save_chunk_store(store)
    return faiss_ids


def remove_document_from_index(document_id: str) -> None:
    """
    Remove all chunks for a document from the chunk store.
    FAISS FlatIndex does not support deletion, so we rebuild.
    """
    try:
        import faiss  # type: ignore
    except ImportError:
        return

    store = _load_chunk_store()
    remaining = [c for c in store if c["document_id"] != str(document_id)]
    if not remaining:
        # Clear index
        _save_chunk_store([])
        index_path = _index_dir() / FAISS_INDEX_FILE
        if index_path.exists():
            index_path.unlink()
        return

    # Re-embed remaining chunks and rebuild index
    texts = [c["text"] for c in remaining]
    embeddings = embed_texts(texts)
    dim = embeddings.shape[1]
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    _save_faiss_index(index)

    # Re-assign FAISS IDs
    for i, chunk in enumerate(remaining):
        chunk["faiss_id"] = i
    _save_chunk_store(remaining)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search_chunks(
    query: str,
    top_k: int = TOP_K_RETRIEVAL,
    threshold: float = SIMILARITY_THRESHOLD,
    document_id: Optional[str] = None,
) -> list[dict]:
    """
    Search for the most relevant chunks for a query.
    Returns list of chunk dicts with added "score" field.
    Optionally filter by document_id.
    """
    try:
        import faiss  # type: ignore
    except ImportError:
        logger.error("faiss-cpu not installed; retrieval unavailable")
        return []

    index_path = _index_dir() / FAISS_INDEX_FILE
    if not index_path.exists():
        return []

    store = _load_chunk_store()
    if not store:
        return []

    index = faiss.read_index(str(index_path))
    query_emb = embed_texts([query])
    faiss.normalize_L2(query_emb)

    k = min(top_k * 3, index.ntotal)  # over-fetch then filter
    scores, ids = index.search(query_emb, k)

    results = []
    id_to_chunk = {c["faiss_id"]: c for c in store}
    for score, fid in zip(scores[0], ids[0]):
        if fid == -1:
            continue
        chunk = id_to_chunk.get(int(fid))
        if chunk is None:
            continue
        if document_id and chunk["document_id"] != str(document_id):
            continue
        if score < threshold:
            continue
        results.append({**chunk, "score": float(score)})
        if len(results) >= top_k:
            break

    return results


# ---------------------------------------------------------------------------
# Full document ingestion pipeline
# ---------------------------------------------------------------------------

def ingest_document(document) -> None:
    """
    Full pipeline: extract → chunk → embed → index.
    Updates document.status in the database.
    `document` is a KnowledgeDocument model instance.
    """
    from .models import KnowledgeDocument, DocumentChunk  # lazy import

    try:
        document.status = KnowledgeDocument.Status.PROCESSING
        document.save(update_fields=["status"])

        # Read file bytes
        document.file.open("rb")
        file_bytes = document.file.read()
        document.file.close()

        # Extract text
        fname = document.filename.lower()
        if fname.endswith(".pdf"):
            pages = extract_text_from_pdf(file_bytes)
            document.total_pages = len(pages)
        else:
            pages = extract_text_from_txt(file_bytes)
            document.total_pages = 1

        if not pages:
            raise ValueError("No text could be extracted from the document.")

        # Chunk
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("Document produced no text chunks.")

        # Clear existing chunks for this doc (re-ingestion)
        DocumentChunk.objects.filter(document=document).delete()

        # Index
        faiss_ids = index_document(str(document.id), document.filename, chunks)

        # Save chunk metadata to DB
        db_chunks = []
        for chunk, fid in zip(chunks, faiss_ids):
            db_chunks.append(
                DocumentChunk(
                    document=document,
                    chunk_index=chunk["chunk_index"],
                    page_number=chunk.get("page"),
                    text=chunk["text"],
                    faiss_id=fid,
                )
            )
        DocumentChunk.objects.bulk_create(db_chunks)

        document.total_chunks = len(chunks)
        document.status = KnowledgeDocument.Status.INDEXED
        document.error_message = ""
        document.save(update_fields=["total_chunks", "total_pages", "status", "error_message"])

    except Exception as exc:
        logger.exception("Document ingestion failed for %s", document.filename)
        document.status = KnowledgeDocument.Status.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
        raise
