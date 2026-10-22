"""
Database models for CodeSathi AI.

Models:
- KnowledgeDocument: uploaded PDF/TXT files with processing state
- DocumentChunk: individual text chunks with embeddings metadata
- LearningEvent: records every meaningful user interaction
- BugCategory: error category counts per session
- VideoLibraryEntry: curated beginner tutorial video metadata
- PracticeQuestion: auto-generated questions tied to a concept
"""

import uuid
from django.db import models


class KnowledgeDocument(models.Model):
    """A PDF or TXT file uploaded to the knowledge base."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        INDEXED = "indexed", "Indexed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="knowledge_docs/")
    file_size_bytes = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADED
    )
    total_chunks = models.PositiveIntegerField(default=0)
    total_pages = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.status})"


class DocumentChunk(models.Model):
    """A single text chunk extracted from a KnowledgeDocument."""

    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    # FAISS assigns integer IDs; we store it for reverse lookup
    faiss_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        unique_together = ["document", "chunk_index"]

    def __str__(self):
        return f"{self.document.filename} chunk {self.chunk_index}"


class LearningEvent(models.Model):
    """Records a meaningful user learning interaction."""

    class EventType(models.TextChoices):
        CODE_EXPLAIN = "code_explain", "Code Explanation"
        DEBUG_REQUEST = "debug_request", "Debugging Request"
        FIX_YOURSELF = "fix_yourself", "Fix It Yourself"
        HINT_REQUESTED = "hint_requested", "Hint Requested"
        SOLUTION_VIEWED = "solution_viewed", "Solution Viewed"
        VIDEO_OPENED = "video_opened", "Video Opened"
        PRACTICE_ATTEMPT = "practice_attempt", "Practice Question Attempt"
        UNDERSTANDING_CONFIRMED = "understanding_confirmed", "Understanding Confirmed"
        KB_QUESTION = "kb_question", "Knowledge Base Question"
        BUG_CATEGORY_CONFIRMED = "bug_category_confirmed", "Bug Category Confirmed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    language = models.CharField(max_length=50, blank=True)  # programming language
    explanation_language = models.CharField(max_length=20, default="english")
    topic = models.CharField(max_length=255, blank=True)
    code_snippet = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} at {self.created_at:%Y-%m-%d %H:%M}"


class BugCategory(models.Model):
    """Running tally of confirmed/likely error categories (Bug DNA)."""

    class Category(models.TextChoices):
        SYNTAX = "syntax", "Syntax"
        LOGIC = "logic", "Logic"
        CONDITIONS = "conditions", "Conditions"
        LOOPS = "loops", "Loops"
        VARIABLES = "variables", "Variables & Data Types"
        FUNCTIONS = "functions", "Functions"
        ARRAYS = "arrays", "Arrays & Strings"
        POINTERS = "pointers", "Pointers & Memory"
        IO = "io", "Input / Output"
        OTHER = "other", "Other"

    category = models.CharField(
        max_length=20, choices=Category.choices, unique=True
    )
    count = models.PositiveIntegerField(default=0)
    user_confirmed_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-count"]

    def __str__(self):
        return f"{self.category}: {self.count}"


class VideoLibraryEntry(models.Model):
    """Curated beginner tutorial video metadata (admin-managed)."""

    topic_key = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=300)
    channel_name = models.CharField(max_length=200, blank=True)
    youtube_id = models.CharField(max_length=20)  # 11-char YouTube video ID
    thumbnail_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    programming_language = models.CharField(max_length=50, blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")],
        default="beginner",
    )
    verified = models.BooleanField(default=False)
    is_sample_data = models.BooleanField(
        default=True,
        help_text="True = sample/demonstration data; False = admin-verified real video",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["topic_key", "-verified"]

    def __str__(self):
        return f"[{self.topic_key}] {self.title}"

    @property
    def embed_url(self):
        return f"https://www.youtube.com/embed/{self.youtube_id}"

    @property
    def watch_url(self):
        return f"https://www.youtube.com/watch?v={self.youtube_id}"


class PracticeQuestion(models.Model):
    """Auto-generated practice question for a concept."""

    concept = models.CharField(max_length=200)
    programming_language = models.CharField(max_length=50, blank=True)
    question_text = models.TextField()
    answer_explanation = models.TextField()
    difficulty = models.CharField(max_length=20, default="beginner")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.concept}: {self.question_text[:60]}"
