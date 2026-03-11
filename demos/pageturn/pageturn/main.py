from fastapi import FastAPI

from .routes import auth, books, health, reviews

app = FastAPI(
    title="PageTurn",
    description="Minimal bookstore API for Kassandra demo",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(books.router)
app.include_router(reviews.router)
