"""
LLM service for CodeSathi AI.

Supports:
- OpenAI (and compatible endpoints, e.g. Together, Groq)
- Google Gemini via google-generativeai SDK

Provider is chosen by the LLM_PROVIDER setting.
All API keys are read from Django settings (loaded from .env).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider detection helpers
# ---------------------------------------------------------------------------

def _provider() -> str:
    return getattr(settings, "LLM_PROVIDER", "openai").lower()


def _openai_client():
    """Return an openai.OpenAI client configured from settings."""
    try:
        import openai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "openai package is not installed. Run: pip install openai"
        ) from exc
    api_key = settings.OPENAI_API_KEY
    base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set it in your .env file."
        )
    return openai.OpenAI(api_key=api_key, base_url=base_url)


def _gemini_model():
    """Return a configured Gemini generative model."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai package is not installed. "
            "Run: pip install google-generativeai"
        ) from exc
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Set it in your .env file."
        )
    genai.configure(api_key=api_key)
    model_name = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
    return genai.GenerativeModel(model_name)


# ---------------------------------------------------------------------------
# Core call
# ---------------------------------------------------------------------------

def call_llm(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    """
    Send a prompt to the configured LLM and return the text response.
    Raises RuntimeError with a user-friendly message on failure.
    """
    provider = _provider()
    try:
        if provider == "gemini":
            return _call_gemini(prompt, system, temperature)
        else:  # openai / openai-compatible
            return _call_openai(prompt, system, temperature)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.exception("LLM call failed")
        raise RuntimeError(f"LLM request failed: {exc}") from exc


def _call_openai(prompt: str, system: str, temperature: float) -> str:
    client = _openai_client()
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _call_gemini(prompt: str, system: str, temperature: float) -> str:
    model = _gemini_model()
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    result = model.generate_content(
        full_prompt,
        generation_config={"temperature": temperature},
    )
    return result.text.strip()


# ---------------------------------------------------------------------------
# Structured JSON call
# ---------------------------------------------------------------------------

def call_llm_json(prompt: str, system: str = "", temperature: float = 0.3) -> dict:
    """
    Call the LLM expecting a JSON object as response.
    Returns parsed dict. Raises ValueError if response cannot be parsed.
    """
    json_instruction = (
        "\n\nIMPORTANT: Respond with valid JSON only. "
        "Do not include markdown fences or any text outside the JSON object."
    )
    raw = call_llm(prompt + json_instruction, system, temperature)
    # Strip possible markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("LLM JSON parse failed: %s\nRaw: %s", exc, raw[:200])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Code Explainer
# ---------------------------------------------------------------------------

def explain_code(
    code: str,
    language: str,
    explanation_language: str = "English",
    context_chunks: Optional[list[dict]] = None,
) -> dict:
    """
    Explain the given code snippet.
    Returns a dict with keys:
      summary, explanation, line_by_line, variables_functions,
      potential_errors, corrected_code, examples, key_points,
      document_references
    """
    context_text = ""
    if context_chunks:
        context_text = "\n\n## Relevant Knowledge Base Excerpts\n"
        for c in context_chunks:
            context_text += (
                f"[From: {c['filename']}, page {c.get('page_number', '?')}]\n"
                f"{c['text']}\n\n"
            )

    system = (
        "You are CodeSathi AI, a beginner-friendly programming education assistant. "
        "Explain code clearly and simply. Use the explanation language requested."
    )
    prompt = f"""Analyze this {language} code and provide a structured explanation in {explanation_language}.

```{language}
{code}
```
{context_text}

Respond with a JSON object with these exact keys:
- "summary": one-sentence overview
- "explanation": 2-3 paragraph simple explanation
- "line_by_line": array of objects, each with "line" (code line or range), "explanation" (beginner friendly)
- "variables_functions": array of objects with "name", "type", "purpose"
- "potential_errors": array of objects with "type", "description", "suggestion"
- "corrected_code": corrected version of code if errors found, else empty string
- "examples": beginner-friendly usage example as a string
- "key_points": array of 3-5 key learning takeaways as strings
- "document_references": array of objects with "filename", "page", "excerpt" (only if context chunks were provided and used)
"""
    result = call_llm_json(prompt, system)
    # Ensure all keys exist
    defaults = {
        "summary": "", "explanation": "", "line_by_line": [],
        "variables_functions": [], "potential_errors": [], "corrected_code": "",
        "examples": "", "key_points": [], "document_references": [],
    }
    for k, v in defaults.items():
        result.setdefault(k, v)
    return result


# ---------------------------------------------------------------------------
# Debugging Assistant
# ---------------------------------------------------------------------------

def debug_code(
    code: str,
    error_message: str,
    language: str,
    explanation_language: str = "English",
    context_chunks: Optional[list[dict]] = None,
) -> dict:
    """
    Analyse code and error message to produce a structured debugging report.
    Returns dict with keys:
      root_cause, relevant_snippet, why_it_occurs, expected_vs_actual,
      suggested_correction, corrected_code, correction_explanation,
      document_evidence, evidence_status, error_category
    """
    context_text = ""
    if context_chunks:
        context_text = "\n\n## Knowledge Base Evidence\n"
        for c in context_chunks:
            context_text += (
                f"[From: {c['filename']}, page {c.get('page_number', '?')}]\n"
                f"{c['text']}\n\n"
            )

    system = (
        "You are CodeSathi AI, a beginner-friendly debugging assistant. "
        "Identify bugs clearly and explain them in simple terms. "
        "NEVER claim code has been executed unless it actually was."
    )
    prompt = f"""Debug this {language} code. Respond in {explanation_language}.

Code:
```{language}
{code}
```

Error message (may be empty):
{error_message or '(no error message provided)'}
{context_text}

Respond with a JSON object with these exact keys:
- "root_cause": likely root cause description
- "relevant_snippet": the specific line(s) causing the issue
- "why_it_occurs": why this bug happens (beginner explanation)
- "expected_vs_actual": what should happen vs what actually happens
- "suggested_correction": how to fix it
- "corrected_code": corrected version of the code
- "correction_explanation": brief explanation of the fix
- "document_evidence": array of objects with "filename", "page", "excerpt" if knowledge base evidence was used
- "evidence_status": one of: "Supported by Retrieved Documents", "Based on AI General Knowledge", "Supported by Documents and AI General Knowledge", "Needs Verification"
- "error_category": one of: syntax, logic, conditions, loops, variables, functions, arrays, pointers, io, other
"""
    result = call_llm_json(prompt, system)
    defaults = {
        "root_cause": "", "relevant_snippet": "", "why_it_occurs": "",
        "expected_vs_actual": "", "suggested_correction": "", "corrected_code": "",
        "correction_explanation": "", "document_evidence": [],
        "evidence_status": "Needs Verification", "error_category": "other",
    }
    for k, v in defaults.items():
        result.setdefault(k, v)
    return result


# ---------------------------------------------------------------------------
# Fix It Yourself Mode
# ---------------------------------------------------------------------------

def get_hint(code: str, error_message: str, language: str, explanation_language: str = "English") -> str:
    """Return a small hint without revealing the full solution."""
    prompt = f"""A beginner is debugging this {language} code.

Code:
```{language}
{code}
```
Error: {error_message or '(no error provided)'}

Give ONE small, helpful hint (1-2 sentences) in {explanation_language} that guides them toward the issue WITHOUT revealing the answer. 
Be friendly and encouraging."""
    return call_llm(prompt, temperature=0.4)


def get_guided_step(
    code: str, error_message: str, language: str,
    step_number: int = 1, explanation_language: str = "English"
) -> str:
    """Return a guided step-by-step explanation."""
    prompt = f"""Guide a beginner through debugging this {language} code. This is step {step_number}.

Code:
```{language}
{code}
```
Error: {error_message or '(none)'}

Explain the relevant concept (step {step_number}) simply in {explanation_language}, then ask them to try the next step. 
Do NOT give the full answer yet."""
    return call_llm(prompt, temperature=0.4)


def get_solution(code: str, error_message: str, language: str, explanation_language: str = "English") -> dict:
    """Return corrected code and explanation."""
    prompt = f"""Show the solution for this {language} debugging problem in {explanation_language}.

Code:
```{language}
{code}
```
Error: {error_message or '(none)'}

Return JSON with:
- "corrected_code": the corrected code
- "explanation": why the fix works (beginner friendly)
- "what_was_wrong": what was wrong with the original
"""
    result = call_llm_json(prompt)
    result.setdefault("corrected_code", "")
    result.setdefault("explanation", "")
    result.setdefault("what_was_wrong", "")
    return result


# ---------------------------------------------------------------------------
# Simpler Explanation
# ---------------------------------------------------------------------------

def explain_more_simply(
    concept: str,
    original_explanation: str,
    explanation_language: str = "English",
    user_question: str = "",
) -> str:
    """Generate a simpler alternative explanation using small examples."""
    prompt = f"""A beginner does not understand this concept: "{concept}"

Original explanation given:
{original_explanation[:800]}

User's specific question (if any): {user_question or 'None'}

Provide a DIFFERENT, simpler explanation in {explanation_language} using:
1. Very simple everyday language
2. A small concrete code example
3. Step-by-step breakdown
4. A one-sentence summary at the end

Do NOT repeat the original explanation word-for-word."""
    return call_llm(prompt, temperature=0.5)


# ---------------------------------------------------------------------------
# Practice Questions
# ---------------------------------------------------------------------------

def generate_practice_question(
    concept: str,
    language: str,
    difficulty: str = "beginner",
    explanation_language: str = "English",
) -> dict:
    """Generate a short practice question for the given concept."""
    prompt = f"""Create a {difficulty} practice question about "{concept}" in {language}.
Respond in {explanation_language}.

Return JSON with:
- "question": the question text
- "hint": a small hint
- "answer_explanation": full answer with code example
"""
    result = call_llm_json(prompt, temperature=0.6)
    result.setdefault("question", "")
    result.setdefault("hint", "")
    result.setdefault("answer_explanation", "")
    return result


# ---------------------------------------------------------------------------
# Knowledge Base Q&A
# ---------------------------------------------------------------------------

def answer_from_documents(
    question: str,
    context_chunks: list[dict],
    explanation_language: str = "English",
) -> dict:
    """
    Answer a user question using retrieved document chunks.
    Returns:
      answer, source_mode, sources
    """
    if not context_chunks:
        # No chunks — general knowledge fallback
        answer = call_llm(
            f"Answer this question in {explanation_language}: {question}",
            system="You are a helpful programming education assistant."
        )
        return {
            "answer": answer,
            "source_mode": "ai_general",
            "sources": [],
        }

    context_text = "\n\n".join(
        f"[{c['filename']}, p.{c.get('page_number','?')}]:\n{c['text']}"
        for c in context_chunks
    )
    prompt = f"""Answer this question using the provided document excerpts. Respond in {explanation_language}.

Question: {question}

Document excerpts:
{context_text}

Return JSON with:
- "answer": detailed answer
- "source_mode": "doc_only", "ai_general", or "doc_and_ai"
- "sources": array of objects with "filename", "page", "excerpt_used"
"""
    result = call_llm_json(prompt)
    result.setdefault("answer", "")
    result.setdefault("source_mode", "doc_and_ai")
    result.setdefault("sources", [])
    return result
