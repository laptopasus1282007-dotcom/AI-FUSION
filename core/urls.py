"""
All URL routes for CodeSathi AI.
"""

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Code Explainer
    path("explain/", views.explain_view, name="explain"),
    path("explain/result/", views.explain_result, name="explain_result"),

    # Debugging Assistant
    path("debug/", views.debug_view, name="debug"),
    path("debug/result/", views.debug_result, name="debug_result"),

    # Debugging Evidence Lab
    path("evidence/", views.evidence_view, name="evidence"),

    # Fix It Yourself Mode
    path("fixit/", views.fixit_view, name="fixit"),
    path("fixit/hint/", views.fixit_hint, name="fixit_hint"),
    path("fixit/guided/", views.fixit_guided, name="fixit_guided"),
    path("fixit/solution/", views.fixit_solution, name="fixit_solution"),

    # AI Video Learning Assistant
    path("video/", views.video_view, name="video"),
    path("video/recommend/", views.video_recommend, name="video_recommend"),
    path("video/simpler/", views.explain_simpler, name="explain_simpler"),
    path("video/practice/", views.practice_question, name="practice_question"),

    # Bug DNA
    path("bugdna/", views.bugdna_view, name="bugdna"),
    path("bugdna/confirm/", views.bugdna_confirm, name="bugdna_confirm"),

    # Knowledge Base
    path("knowledge/", views.knowledge_view, name="knowledge"),
    path("knowledge/upload/", views.knowledge_upload, name="knowledge_upload"),
    path("knowledge/delete/<uuid:doc_id>/", views.knowledge_delete, name="knowledge_delete"),
    path("knowledge/ask/", views.knowledge_ask, name="knowledge_ask"),
    path("knowledge/status/<uuid:doc_id>/", views.knowledge_status, name="knowledge_status"),

    # Learning History
    path("history/", views.history_view, name="history"),
    path("history/clear/", views.history_clear, name="history_clear"),

    # Settings & About
    path("settings/", views.settings_view, name="settings"),
]
