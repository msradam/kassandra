import threading

from fastapi import APIRouter, Depends, HTTPException

from ..models import Review, ReviewCreate
from .auth import verify_token
from .books import _books

router = APIRouter(prefix="/api/books", tags=["reviews"])

_lock = threading.Lock()
_next_id = 1
_reviews: dict[int, list[Review]] = {}


def _get_current_user(authorization: str = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    return verify_token(authorization.removeprefix("Bearer ").strip())


@router.get("/{book_id}/reviews", response_model=list[Review])
def list_reviews(book_id: int):
    if book_id not in _books:
        raise HTTPException(status_code=404, detail="Book not found")
    return _reviews.get(book_id, [])


@router.post("/{book_id}/reviews", response_model=Review, status_code=201)
def create_review(
    book_id: int,
    review: ReviewCreate,
    user: str = Depends(_get_current_user),
):
    if book_id not in _books:
        raise HTTPException(status_code=404, detail="Book not found")

    global _next_id
    with _lock:
        new_review = Review(
            id=_next_id,
            book_id=book_id,
            reviewer=user,
            stars=review.stars,
            comment=review.comment,
        )
        _reviews.setdefault(book_id, []).append(new_review)
        _next_id += 1
    return new_review
