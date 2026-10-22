"""Admin registration for CodeSathi AI models."""

from django.contrib import admin
from .models import (
    KnowledgeDocument,
    DocumentChunk,
    LearningEvent,
    BugCategory,
    VideoLibraryEntry,
    PracticeQuestion,
)


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ["filename", "status", "total_chunks", "total_pages", "file_size_bytes", "created_at"]
    list_filter = ["status"]
    search_fields = ["filename"]
    readonly_fields = ["id", "created_at", "updated_at", "total_chunks", "total_pages"]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ["document", "chunk_index", "page_number", "faiss_id"]
    list_filter = ["document"]
    search_fields = ["text"]


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "language", "topic", "created_at"]
    list_filter = ["event_type", "language"]
    search_fields = ["topic", "code_snippet"]
    readonly_fields = ["id", "created_at"]


@admin.register(BugCategory)
class BugCategoryAdmin(admin.ModelAdmin):
    list_display = ["category", "count", "user_confirmed_count", "last_updated"]


@admin.register(VideoLibraryEntry)
class VideoLibraryEntryAdmin(admin.ModelAdmin):
    list_display = ["topic_key", "title", "channel_name", "youtube_id", "verified", "is_sample_data"]
    list_filter = ["verified", "is_sample_data", "programming_language"]
    search_fields = ["topic_key", "title", "channel_name"]
    list_editable = ["verified"]


@admin.register(PracticeQuestion)
class PracticeQuestionAdmin(admin.ModelAdmin):
    list_display = ["concept", "programming_language", "difficulty", "created_at"]
    list_filter = ["difficulty", "programming_language"]
    search_fields = ["concept", "question_text"]
