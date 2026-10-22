"""
Views for CodeSathi AI.

All AI responses come from real LLM calls.
All retrieval comes from real FAISS search.
No fake statistics, fake video cards, or fabricated data.
"""

from __future__ import annotations

import json
import logging
import os
import threading

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET

from .models import (
    BugCategory,
    DocumentChunk,
    KnowledgeDocument,
    LearningEvent,
    PracticeQuestion,
    VideoLibraryEntry,
)
from . import llm_service, rag_service, video_service

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["Python", "JavaScript", "C", "C++", "Java"]
EXPLANATION_LANGUAGES = ["English", "Hindi", "Marathi"]
DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_event(event_type: str, **kwargs) -> None:
    """Silently persist a learning event; never raises."""
    try:
        LearningEvent.objects.create(event_type=event_type, **kwargs)
    except Exception:
        pass


def _get_context_chunks(query: str) -> tuple[list[dict], str]:
    """
    Retrieve relevant chunks for a query.
    Returns (chunks, source_mode).
    source_mode: "doc_only", "ai_general", "doc_and_ai", "retrieval_error"
    """
    try:
        chunks = rag_service.search_chunks(query)
        source_mode = "doc_only" if chunks else "ai_general"
        return chunks, source_mode
    except Exception as exc:
        logger.warning("RAG retrieval error: %s", exc)
        return [], "retrieval_error"


def _llm_available() -> bool:
    """Check if an API key is configured."""
    provider = getattr(settings, "LLM_PROVIDER", "openai").lower()
    if provider == "gemini":
        return bool(getattr(settings, "GEMINI_API_KEY", ""))
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard(request):
    """Main dashboard with feature overview and real stats."""
    doc_count = KnowledgeDocument.objects.filter(
        status=KnowledgeDocument.Status.INDEXED
    ).count()
    event_count = LearningEvent.objects.count()
    top_bugs = BugCategory.objects.order_by("-count")[:3]

    return render(request, "core/dashboard.html", {
        "doc_count": doc_count,
        "event_count": event_count,
        "top_bugs": top_bugs,
        "llm_available": _llm_available(),
        "supported_languages": SUPPORTED_LANGUAGES,
    })


# ---------------------------------------------------------------------------
# Code Explainer
# ---------------------------------------------------------------------------

def explain_view(request):
    """Code explainer form."""
    return render(request, "core/explain.html", {
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
        "llm_available": _llm_available(),
    })


@require_POST
def explain_result(request):
    """Process code explanation request."""
    code = request.POST.get("code", "").strip()
    language = request.POST.get("language", "Python")
    explanation_language = request.POST.get("explanation_language", "English")

    if not code:
        messages.error(request, "Please enter some code to explain.")
        return redirect("core:explain")

    if not _llm_available():
        messages.error(request, "LLM API key not configured. Please set it in your .env file.")
        return redirect("core:explain")

    # RAG retrieval
    chunks, source_mode = _get_context_chunks(code[:500] + " " + language)

    try:
        result = llm_service.explain_code(
            code=code,
            language=language,
            explanation_language=explanation_language,
            context_chunks=chunks if chunks else None,
        )
        if chunks:
            source_mode = "doc_and_ai" if result.get("document_references") else "ai_general"
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("core:explain")

    _record_event(
        LearningEvent.EventType.CODE_EXPLAIN,
        language=language,
        explanation_language=explanation_language,
        code_snippet=code[:500],
        topic=result.get("summary", "")[:200],
    )

    return render(request, "core/explain_result.html", {
        "code": code,
        "language": language,
        "explanation_language": explanation_language,
        "result": result,
        "source_mode": source_mode,
        "chunks": chunks,
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
    })


# ---------------------------------------------------------------------------
# Debugging Assistant
# ---------------------------------------------------------------------------

def debug_view(request):
    """Debugging assistant form."""
    return render(request, "core/debug.html", {
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
        "llm_available": _llm_available(),
    })


@require_POST
def debug_result(request):
    """Process debugging request."""
    code = request.POST.get("code", "").strip()
    error_message = request.POST.get("error_message", "").strip()
    language = request.POST.get("language", "Python")
    explanation_language = request.POST.get("explanation_language", "English")

    if not code:
        messages.error(request, "Please enter the code to debug.")
        return redirect("core:debug")

    if not _llm_available():
        messages.error(request, "LLM API key not configured.")
        return redirect("core:debug")

    query = f"{language} error: {error_message} {code[:300]}"
    chunks, source_mode = _get_context_chunks(query)

    try:
        result = llm_service.debug_code(
            code=code,
            error_message=error_message,
            language=language,
            explanation_language=explanation_language,
            context_chunks=chunks if chunks else None,
        )
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("core:debug")

    # Update Bug DNA
    cat = result.get("error_category", "other")
    _update_bug_category(cat)

    _record_event(
        LearningEvent.EventType.DEBUG_REQUEST,
        language=language,
        explanation_language=explanation_language,
        code_snippet=code[:500],
        error_message=error_message[:500],
        topic=result.get("root_cause", "")[:200],
        metadata={"error_category": cat},
    )

    return render(request, "core/debug_result.html", {
        "code": code,
        "error_message": error_message,
        "language": language,
        "explanation_language": explanation_language,
        "result": result,
        "source_mode": source_mode,
        "chunks": chunks,
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
    })


def _update_bug_category(category_key: str) -> None:
    try:
        obj, _ = BugCategory.objects.get_or_create(category=category_key)
        obj.count += 1
        obj.save(update_fields=["count"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Debugging Evidence Lab
# ---------------------------------------------------------------------------

def evidence_view(request):
    """Evidence Lab — uses session data from last debug result."""
    context = request.session.get("last_debug_result", {})
    return render(request, "core/evidence.html", {"context": context})


# ---------------------------------------------------------------------------
# Fix It Yourself Mode
# ---------------------------------------------------------------------------

def fixit_view(request):
    return render(request, "core/fixit.html", {
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
        "llm_available": _llm_available(),
    })


@require_POST
def fixit_hint(request):
    code = request.POST.get("code", "")
    error_message = request.POST.get("error_message", "")
    language = request.POST.get("language", "Python")
    explanation_language = request.POST.get("explanation_language", "English")

    try:
        hint = llm_service.get_hint(code, error_message, language, explanation_language)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    _record_event(LearningEvent.EventType.HINT_REQUESTED, language=language, code_snippet=code[:300])
    return JsonResponse({"hint": hint})


@require_POST
def fixit_guided(request):
    code = request.POST.get("code", "")
    error_message = request.POST.get("error_message", "")
    language = request.POST.get("language", "Python")
    step = int(request.POST.get("step", 1))
    explanation_language = request.POST.get("explanation_language", "English")

    try:
        step_text = llm_service.get_guided_step(
            code, error_message, language, step, explanation_language
        )
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"step": step_text, "step_number": step})


@require_POST
def fixit_solution(request):
    code = request.POST.get("code", "")
    error_message = request.POST.get("error_message", "")
    language = request.POST.get("language", "Python")
    explanation_language = request.POST.get("explanation_language", "English")

    try:
        solution = llm_service.get_solution(code, error_message, language, explanation_language)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    _record_event(LearningEvent.EventType.SOLUTION_VIEWED, language=language, code_snippet=code[:300])
    return JsonResponse(solution)


# ---------------------------------------------------------------------------
# AI Video Learning Assistant
# ---------------------------------------------------------------------------

def video_view(request):
    return render(request, "core/video.html", {
        "supported_languages": SUPPORTED_LANGUAGES,
        "explanation_languages": EXPLANATION_LANGUAGES,
    })


@require_POST
def video_recommend(request):
    """Return video recommendations as JSON."""
    concept = request.POST.get("concept", "").strip()
    language = request.POST.get("language", "")
    error_type = request.POST.get("error_type", "")
    difficulty = request.POST.get("difficulty", "beginner")

    if not concept:
        return JsonResponse({"error": "Please specify a concept."}, status=400)

    result = video_service.get_video_recommendations(
        concept=concept,
        programming_language=language,
        error_type=error_type,
        difficulty=difficulty,
    )

    _record_event(
        LearningEvent.EventType.VIDEO_OPENED,
        topic=concept,
        language=language,
        metadata={"source": result.get("source"), "query": result.get("search_query")},
    )
    return JsonResponse(result)


@require_POST
def explain_simpler(request):
    """Return a simpler explanation as JSON."""
    concept = request.POST.get("concept", "")
    original = request.POST.get("original_explanation", "")
    explanation_language = request.POST.get("explanation_language", "English")
    user_question = request.POST.get("user_question", "")

    if not concept:
        return JsonResponse({"error": "Concept is required."}, status=400)

    try:
        simpler = llm_service.explain_more_simply(
            concept, original, explanation_language, user_question
        )
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"explanation": simpler})


@require_POST
def practice_question(request):
    """Generate a practice question and return as JSON."""
    concept = request.POST.get("concept", "")
    language = request.POST.get("language", "Python")
    difficulty = request.POST.get("difficulty", "beginner")
    explanation_language = request.POST.get("explanation_language", "English")

    if not concept:
        return JsonResponse({"error": "Concept is required."}, status=400)

    try:
        q = llm_service.generate_practice_question(concept, language, difficulty, explanation_language)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Persist question
    try:
        PracticeQuestion.objects.create(
            concept=concept,
            programming_language=language,
            question_text=q.get("question", ""),
            answer_explanation=q.get("answer_explanation", ""),
            difficulty=difficulty,
        )
    except Exception:
        pass

    _record_event(
        LearningEvent.EventType.PRACTICE_ATTEMPT,
        topic=concept,
        language=language,
    )
    return JsonResponse(q)


# ---------------------------------------------------------------------------
# Bug DNA Insights
# ---------------------------------------------------------------------------

def bugdna_view(request):
    categories = BugCategory.objects.all().order_by("-count")
    total_bugs = sum(c.count for c in categories)
    history_count = LearningEvent.objects.filter(
        event_type__in=[
            LearningEvent.EventType.DEBUG_REQUEST,
            LearningEvent.EventType.FIX_YOURSELF,
        ]
    ).count()

    return render(request, "core/bugdna.html", {
        "categories": categories,
        "total_bugs": total_bugs,
        "history_count": history_count,
    })


@require_POST
def bugdna_confirm(request):
    """User confirms or updates an error category."""
    category_key = request.POST.get("category", "")
    try:
        obj, _ = BugCategory.objects.get_or_create(category=category_key)
        obj.user_confirmed_count += 1
        obj.save(update_fields=["user_confirmed_count"])
        _record_event(
            LearningEvent.EventType.BUG_CATEGORY_CONFIRMED,
            topic=category_key,
        )
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

def knowledge_view(request):
    docs = KnowledgeDocument.objects.all()
    return render(request, "core/knowledge.html", {"docs": docs})


@require_POST
def knowledge_upload(request):
    """Handle file upload and trigger background ingestion."""
    uploaded_file = request.FILES.get("document")
    if not uploaded_file:
        messages.error(request, "No file selected.")
        return redirect("core:knowledge")

    # Validate type
    fname = uploaded_file.name.lower()
    if not (fname.endswith(".pdf") or fname.endswith(".txt")):
        messages.error(request, "Only PDF and TXT files are supported.")
        return redirect("core:knowledge")

    # Validate size
    max_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    if uploaded_file.size > max_mb * 1024 * 1024:
        messages.error(request, f"File exceeds the {max_mb} MB limit.")
        return redirect("core:knowledge")

    doc = KnowledgeDocument.objects.create(
        filename=uploaded_file.name,
        file=uploaded_file,
        file_size_bytes=uploaded_file.size,
        mime_type=uploaded_file.content_type or "",
    )

    # Background ingestion
    thread = threading.Thread(target=_ingest_in_background, args=(str(doc.id),), daemon=True)
    thread.start()

    messages.success(
        request,
        f"'{uploaded_file.name}' uploaded. Processing in background — refresh to see status."
    )
    return redirect("core:knowledge")


def _ingest_in_background(doc_id: str) -> None:
    """Run ingestion in a daemon thread."""
    try:
        doc = KnowledgeDocument.objects.get(id=doc_id)
        rag_service.ingest_document(doc)
    except Exception as exc:
        logger.error("Background ingestion failed for %s: %s", doc_id, exc)


@require_POST
def knowledge_delete(request, doc_id):
    """Delete document and remove from FAISS index."""
    doc = get_object_or_404(KnowledgeDocument, id=doc_id)
    filename = doc.filename
    try:
        rag_service.remove_document_from_index(str(doc.id))
    except Exception as exc:
        logger.warning("FAISS removal error: %s", exc)
    doc.file.delete(save=False)
    doc.delete()
    messages.success(request, f"'{filename}' deleted from knowledge base.")
    return redirect("core:knowledge")


@require_POST
def knowledge_ask(request):
    """Answer a question using knowledge base + AI."""
    question = request.POST.get("question", "").strip()
    if not question:
        return JsonResponse({"error": "Please enter a question."}, status=400)

    if not _llm_available():
        return JsonResponse({"error": "LLM API key not configured."}, status=400)

    chunks, source_mode = _get_context_chunks(question)

    if source_mode == "retrieval_error":
        # Try general knowledge fallback
        try:
            answer = llm_service.call_llm(question)
            return JsonResponse({
                "answer": answer,
                "source_mode": "ai_general",
                "sources": [],
                "retrieval_error": True,
                "retrieval_error_message": "Document retrieval failed. Answer uses AI general knowledge.",
            })
        except RuntimeError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    try:
        result = llm_service.answer_from_documents(question, chunks)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    _record_event(
        LearningEvent.EventType.KB_QUESTION,
        topic=question[:200],
        metadata={"source_mode": result.get("source_mode")},
    )
    return JsonResponse(result)


def knowledge_status(request, doc_id):
    """Return processing status for a document (for polling)."""
    doc = get_object_or_404(KnowledgeDocument, id=doc_id)
    return JsonResponse({
        "status": doc.status,
        "total_chunks": doc.total_chunks,
        "total_pages": doc.total_pages,
        "error_message": doc.error_message,
    })


# ---------------------------------------------------------------------------
# Learning History
# ---------------------------------------------------------------------------

def history_view(request):
    events = LearningEvent.objects.all()[:200]
    return render(request, "core/history.html", {"events": events})


@require_POST
def history_clear(request):
    LearningEvent.objects.all().delete()
    messages.success(request, "Learning history cleared.")
    return redirect("core:history")


# ---------------------------------------------------------------------------
# Settings & About
# ---------------------------------------------------------------------------

def settings_view(request):
    """Settings/About page — shows configuration status without exposing secrets."""
    provider = getattr(settings, "LLM_PROVIDER", "openai")
    openai_configured = bool(getattr(settings, "OPENAI_API_KEY", ""))
    gemini_configured = bool(getattr(settings, "GEMINI_API_KEY", ""))
    youtube_configured = bool(getattr(settings, "YOUTUBE_API_KEY", ""))

    if request.method == "POST":
        # Allow saving preferences to session
        pref_lang = request.POST.get("preferred_language", "English")
        pref_level = request.POST.get("difficulty", "beginner")
        pref_video_first = request.POST.get("video_first", "false") == "true"

        request.session["pref_lang"] = pref_lang
        request.session["pref_level"] = pref_level
        request.session["pref_video_first"] = pref_video_first
        messages.success(request, "Preferences saved.")
        return redirect("core:settings")

    return render(request, "core/settings.html", {
        "provider": provider,
        "openai_configured": openai_configured,
        "gemini_configured": gemini_configured,
        "youtube_configured": youtube_configured,
        "explanation_languages": EXPLANATION_LANGUAGES,
        "difficulty_levels": DIFFICULTY_LEVELS,
        "pref_lang": request.session.get("pref_lang", "English"),
        "pref_level": request.session.get("pref_level", "beginner"),
        "pref_video_first": request.session.get("pref_video_first", False),
    })
