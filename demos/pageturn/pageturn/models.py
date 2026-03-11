from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str


class Book(BaseModel):
    id: int
    title: str
    author: str
    genre: str
    price: float
    year: int
    in_stock: bool = True


class BookCreate(BaseModel):
    title: str
    author: str
    genre: str
    price: float = Field(gt=0)
    year: int = Field(ge=1000, le=2030)


class BookSearchParams(BaseModel):
    q: str | None = None
    genre: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    page: int = 1
    per_page: int = 20


class BatchImport(BaseModel):
    books: list[BookCreate]


class BatchResult(BaseModel):
    imported: int
    errors: int
    books: list[Book]


class Review(BaseModel):
    id: int
    book_id: int
    reviewer: str
    stars: int
    comment: str


class ReviewCreate(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = ""
