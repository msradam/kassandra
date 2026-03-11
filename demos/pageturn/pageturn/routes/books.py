import threading

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from ..models import BatchImport, BatchResult, Book, BookCreate
from .auth import verify_token

router = APIRouter(prefix="/api/books", tags=["books"])

_lock = threading.Lock()
_next_id = 21
_books: dict[int, Book] = {}


def _seed_books():
    global _next_id
    seed = [
        ("The Great Gatsby", "F. Scott Fitzgerald", "fiction", 12.99, 1925),
        ("To Kill a Mockingbird", "Harper Lee", "fiction", 14.99, 1960),
        ("1984", "George Orwell", "dystopian", 11.99, 1949),
        ("Pride and Prejudice", "Jane Austen", "romance", 9.99, 1813),
        ("The Catcher in the Rye", "J.D. Salinger", "fiction", 10.99, 1951),
        ("Brave New World", "Aldous Huxley", "dystopian", 13.49, 1932),
        ("The Hobbit", "J.R.R. Tolkien", "fantasy", 15.99, 1937),
        ("Fahrenheit 451", "Ray Bradbury", "dystopian", 11.49, 1953),
        ("Dune", "Frank Herbert", "sci-fi", 16.99, 1965),
        ("Neuromancer", "William Gibson", "sci-fi", 13.99, 1984),
        ("The Name of the Wind", "Patrick Rothfuss", "fantasy", 14.49, 2007),
        ("Foundation", "Isaac Asimov", "sci-fi", 12.49, 1951),
        ("Sapiens", "Yuval Noah Harari", "non-fiction", 18.99, 2011),
        ("Thinking, Fast and Slow", "Daniel Kahneman", "non-fiction", 17.99, 2011),
        ("The Art of War", "Sun Tzu", "non-fiction", 8.99, -500),
        ("Clean Code", "Robert C. Martin", "technical", 39.99, 2008),
        ("Design Patterns", "Gang of Four", "technical", 49.99, 1994),
        ("The Pragmatic Programmer", "Hunt & Thomas", "technical", 44.99, 1999),
        (
            "Harry Potter and the Sorcerer's Stone",
            "J.K. Rowling",
            "fantasy",
            12.99,
            1997,
        ),
        ("The Lord of the Rings", "J.R.R. Tolkien", "fantasy", 22.99, 1954),
    ]
    for i, (title, author, genre, price, year) in enumerate(seed, 1):
        _books[i] = Book(
            id=i, title=title, author=author, genre=genre, price=price, year=year
        )
    _next_id = len(seed) + 1


_seed_books()


def _get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    return verify_token(authorization.removeprefix("Bearer ").strip())


@router.get("", response_model=list[Book])
def list_books(
    q: str | None = Query(None, description="Full-text search across title and author"),
    genre: str | None = Query(None, description="Filter by genre"),
    min_price: float | None = Query(None, description="Minimum price filter"),
    max_price: float | None = Query(None, description="Maximum price filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    results = list(_books.values())
    if q:
        q_lower = q.lower()
        results = [
            b
            for b in results
            if q_lower in b.title.lower() or q_lower in b.author.lower()
        ]
    if genre:
        results = [b for b in results if b.genre.lower() == genre.lower()]
    if min_price is not None:
        results = [b for b in results if b.price >= min_price]
    if max_price is not None:
        results = [b for b in results if b.price <= max_price]
    start = (page - 1) * per_page
    return results[start : start + per_page]


@router.get("/{book_id}", response_model=Book)
def get_book(book_id: int):
    if book_id not in _books:
        raise HTTPException(status_code=404, detail="Book not found")
    return _books[book_id]


@router.post("", response_model=Book, status_code=201)
def create_book(book: BookCreate, user: str = Depends(_get_current_user)):
    global _next_id
    with _lock:
        new_book = Book(id=_next_id, **book.model_dump())
        _books[_next_id] = new_book
        _next_id += 1
    return new_book


@router.post("/batch", response_model=BatchResult)
def batch_import(payload: BatchImport, user: str = Depends(_get_current_user)):
    if not payload.books:
        raise HTTPException(status_code=400, detail="Empty batch")
    if len(payload.books) > 50:
        raise HTTPException(status_code=400, detail="Batch size exceeds limit of 50")

    global _next_id
    imported = []
    errors = 0
    with _lock:
        for book_data in payload.books:
            try:
                new_book = Book(id=_next_id, **book_data.model_dump())
                _books[_next_id] = new_book
                imported.append(new_book)
                _next_id += 1
            except Exception:
                errors += 1
    return BatchResult(imported=len(imported), errors=errors, books=imported)
