from django.core.management.base import BaseCommand
from core.models import BugCategory, VideoLibraryEntry


class Command(BaseCommand):
    help = "Seeds initial bug categories and curated educational video entries."

    def handle(self, *args, **options):
        # 1. Seed Bug Categories
        categories = [
            (BugCategory.Category.SYNTAX, "Syntax"),
            (BugCategory.Category.LOGIC, "Logic"),
            (BugCategory.Category.CONDITIONS, "Conditions"),
            (BugCategory.Category.LOOPS, "Loops"),
            (BugCategory.Category.VARIABLES, "Variables & Data Types"),
            (BugCategory.Category.FUNCTIONS, "Functions"),
            (BugCategory.Category.ARRAYS, "Arrays & Strings"),
            (BugCategory.Category.POINTERS, "Pointers & Memory"),
            (BugCategory.Category.IO, "Input / Output"),
            (BugCategory.Category.OTHER, "Other"),
        ]

        created_cat_count = 0
        for cat_code, cat_name in categories:
            _, created = BugCategory.objects.get_or_create(category=cat_code)
            if created:
                created_cat_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_cat_count} new bug categories (total: {BugCategory.objects.count()})."))

        # 2. Seed Curated Real Video Entries
        curated_videos = [
            {
                "topic_key": "loops_python_",
                "title": "Python Tutorial for Beginners: Loops and Iterations - For/While Loops",
                "channel_name": "Corey Schafer",
                "youtube_id": "6iF8Xb7Z3wQ",
                "thumbnail_url": "https://img.youtube.com/vi/6iF8Xb7Z3wQ/mqdefault.jpg",
                "description": "Learn how to use For and While loops in Python with break and continue statements.",
                "programming_language": "Python",
                "difficulty": "beginner",
                "verified": True,
                "is_sample_data": False,
            },
            {
                "topic_key": "functions_python_",
                "title": "Python Tutorial for Beginners: Functions - How to Define and Call Functions",
                "channel_name": "Corey Schafer",
                "youtube_id": "9Os0o3wzS_I",
                "thumbnail_url": "https://img.youtube.com/vi/9Os0o3wzS_I/mqdefault.jpg",
                "description": "Complete beginner guide to writing and using functions in Python.",
                "programming_language": "Python",
                "difficulty": "beginner",
                "verified": True,
                "is_sample_data": False,
            },
            {
                "topic_key": "indexerror_python_indexerror",
                "title": "Python IndexError: list index out of range - What it means & How to fix",
                "channel_name": "CS Dojo",
                "youtube_id": "daefaLgNkw0",
                "thumbnail_url": "https://img.youtube.com/vi/daefaLgNkw0/mqdefault.jpg",
                "description": "Visual explanation of zero-based indexing in Python and why off-by-one errors happen.",
                "programming_language": "Python",
                "difficulty": "beginner",
                "verified": True,
                "is_sample_data": False,
            },
            {
                "topic_key": "pointers_c_",
                "title": "Pointers in C / C++ [Full Course]",
                "channel_name": "freeCodeCamp.org",
                "youtube_id": "2ybLD6_2gKM",
                "thumbnail_url": "https://img.youtube.com/vi/2ybLD6_2gKM/mqdefault.jpg",
                "description": "Visual and in-depth introduction to memory addresses, pointers, and referencing in C.",
                "programming_language": "C",
                "difficulty": "beginner",
                "verified": True,
                "is_sample_data": False,
            },
            {
                "topic_key": "loops_javascript_",
                "title": "JavaScript Loops Explained: For, While, For...of, For...in",
                "channel_name": "freeCodeCamp.org",
                "youtube_id": "s9wW2PpJsmQ",
                "thumbnail_url": "https://img.youtube.com/vi/s9wW2PpJsmQ/mqdefault.jpg",
                "description": "Comprehensive explanation of JavaScript iteration and loop mechanics.",
                "programming_language": "JavaScript",
                "difficulty": "beginner",
                "verified": True,
                "is_sample_data": False,
            },
        ]

        created_vid_count = 0
        for vid in curated_videos:
            _, created = VideoLibraryEntry.objects.get_or_create(
                topic_key=vid["topic_key"],
                youtube_id=vid["youtube_id"],
                defaults=vid,
            )
            if created:
                created_vid_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_vid_count} curated videos (total: {VideoLibraryEntry.objects.count()})."))
