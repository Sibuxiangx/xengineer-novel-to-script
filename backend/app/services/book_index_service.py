from app.schemas.book_index import BookIndex


class BookIndexService:
    """Service boundary for creating and reading book index artifacts."""

    async def summarize_index(self, book_index: BookIndex) -> str:
        return f"{book_index.title} contains {book_index.chapter_count} chapters."

