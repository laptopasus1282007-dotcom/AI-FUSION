"""
Context processors for CodeSathi AI.
Makes global configuration status available to all templates.
"""

from django.conf import settings


def codesathi_context(request):
    provider = getattr(settings, "LLM_PROVIDER", "openai").lower()
    if provider == "gemini":
        llm_ready = bool(getattr(settings, "GEMINI_API_KEY", ""))
    else:
        llm_ready = bool(getattr(settings, "OPENAI_API_KEY", ""))

    return {
        "llm_available": llm_ready,
        "llm_provider": provider,
    }
