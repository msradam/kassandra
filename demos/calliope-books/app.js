const express = require('express');
const Database = require('better-sqlite3');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const path = require('path');

const app = express();
app.use(express.json());

const JWT_SECRET = 'calliope-muse-of-epic-poetry';
const PORT = process.env.PORT || 3000;

// ── Database ──

const db = new Database(path.join(__dirname, 'calliope.db'));
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
  );
  CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    genre TEXT,
    year INTEGER,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  );
  CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
  CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
  CREATE INDEX IF NOT EXISTS idx_reviews_book ON reviews(book_id);
`);

// ── Seed data ──

function seed() {
  const count = db.prepare('SELECT COUNT(*) as n FROM books').get().n;
  if (count > 0) return;

  const genres = ['Fiction', 'Science Fiction', 'Mystery', 'History', 'Philosophy', 'Poetry'];
  const authors = [
    'Homer', 'Sappho', 'Virgil', 'Ovid', 'Dante',
    'Cervantes', 'Shakespeare', 'Austen', 'Dostoevsky', 'Borges'
  ];
  const titles = [
    'The Iliad', 'Fragments', 'The Aeneid', 'Metamorphoses', 'Inferno',
    'Don Quixote', 'Hamlet', 'Pride and Prejudice', 'Crime and Punishment', 'Ficciones',
    'Odyssey', 'Odes', 'Georgics', 'Amores', 'Purgatorio',
    'Exemplary Novels', 'Macbeth', 'Sense and Sensibility', 'The Idiot', 'Labyrinths',
    'Song of Achilles', 'Lyrics', 'Eclogues', 'Heroides', 'Paradiso',
    'Galatea', 'Othello', 'Emma', 'Brothers Karamazov', 'The Aleph'
  ];

  const insert = db.prepare(
    'INSERT INTO books (title, author, genre, year, price, stock) VALUES (?, ?, ?, ?, ?, ?)'
  );
  const tx = db.transaction(() => {
    for (let i = 0; i < 30; i++) {
      insert.run(
        titles[i],
        authors[i % authors.length],
        genres[i % genres.length],
        1200 + Math.floor(Math.random() * 800),
        5.99 + Math.floor(Math.random() * 30),
        Math.floor(Math.random() * 50)
      );
    }
  });
  tx();

  // Seed a demo user
  const hash = crypto.createHash('sha256').update('calliope123').digest('hex');
  db.prepare('INSERT OR IGNORE INTO users (username, email, password_hash) VALUES (?, ?, ?)')
    .run('reader', 'reader@calliope.dev', hash);
}
seed();

// ── Auth middleware ──

function authenticate(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid token' });
  }
  try {
    req.user = jwt.verify(header.slice(7), JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Invalid token' });
  }
}

// ── Auth routes ──

app.post('/api/auth/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) {
    return res.status(400).json({ error: 'username, email, and password required' });
  }
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  try {
    const result = db.prepare('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)')
      .run(username, email, hash);
    const token = jwt.sign({ id: result.lastInsertRowid, username }, JWT_SECRET, { expiresIn: '1h' });
    res.status(201).json({ user: { id: result.lastInsertRowid, username, email }, token });
  } catch (e) {
    res.status(409).json({ error: 'Username or email already exists' });
  }
});

app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'email and password required' });
  }
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  const user = db.prepare('SELECT id, username, email FROM users WHERE email = ? AND password_hash = ?')
    .get(email, hash);
  if (!user) return res.status(401).json({ error: 'Invalid credentials' });
  const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '1h' });
  res.json({ user, token });
});

// ── Books routes ──

app.get('/api/books', (req, res) => {
  const { genre, author, search, limit = 20, offset = 0 } = req.query;
  let sql = 'SELECT * FROM books WHERE 1=1';
  const params = [];
  if (genre) { sql += ' AND genre = ?'; params.push(genre); }
  if (author) { sql += ' AND author = ?'; params.push(author); }
  if (search) { sql += ' AND (title LIKE ? OR author LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  sql += ' ORDER BY id LIMIT ? OFFSET ?';
  params.push(Number(limit), Number(offset));
  const books = db.prepare(sql).all(...params);
  const total = db.prepare('SELECT COUNT(*) as n FROM books').get().n;
  res.json({ books, total, limit: Number(limit), offset: Number(offset) });
});

app.get('/api/books/:id', (req, res) => {
  const book = db.prepare('SELECT * FROM books WHERE id = ?').get(req.params.id);
  if (!book) return res.status(404).json({ error: 'Book not found' });
  const reviews = db.prepare(
    'SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.book_id = ? ORDER BY r.created_at DESC'
  ).all(req.params.id);
  const avg = db.prepare('SELECT AVG(rating) as avg_rating FROM reviews WHERE book_id = ?').get(req.params.id);
  res.json({ ...book, reviews, avg_rating: avg.avg_rating || null });
});

app.post('/api/books', authenticate, (req, res) => {
  const { title, author, genre, year, price, stock } = req.body;
  if (!title || !author || !price) {
    return res.status(400).json({ error: 'title, author, and price required' });
  }
  const result = db.prepare(
    'INSERT INTO books (title, author, genre, year, price, stock) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(title, author, genre || null, year || null, price, stock || 0);
  const book = db.prepare('SELECT * FROM books WHERE id = ?').get(result.lastInsertRowid);
  res.status(201).json(book);
});

app.put('/api/books/:id', authenticate, (req, res) => {
  const existing = db.prepare('SELECT * FROM books WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'Book not found' });
  const { title, author, genre, year, price, stock } = req.body;
  db.prepare(
    'UPDATE books SET title=?, author=?, genre=?, year=?, price=?, stock=? WHERE id=?'
  ).run(
    title || existing.title, author || existing.author, genre || existing.genre,
    year || existing.year, price || existing.price, stock ?? existing.stock, req.params.id
  );
  res.json(db.prepare('SELECT * FROM books WHERE id = ?').get(req.params.id));
});

app.delete('/api/books/:id', authenticate, (req, res) => {
  const result = db.prepare('DELETE FROM books WHERE id = ?').run(req.params.id);
  if (result.changes === 0) return res.status(404).json({ error: 'Book not found' });
  res.status(204).end();
});

// ── Reviews routes ──

app.get('/api/books/:id/reviews', (req, res) => {
  const reviews = db.prepare(
    'SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.book_id = ? ORDER BY r.created_at DESC'
  ).all(req.params.id);
  res.json({ reviews });
});

app.post('/api/books/:id/reviews', authenticate, (req, res) => {
  const { rating, comment } = req.body;
  if (!rating || rating < 1 || rating > 5) {
    return res.status(400).json({ error: 'rating (1-5) required' });
  }
  const book = db.prepare('SELECT id FROM books WHERE id = ?').get(req.params.id);
  if (!book) return res.status(404).json({ error: 'Book not found' });
  const result = db.prepare(
    'INSERT INTO reviews (book_id, user_id, rating, comment) VALUES (?, ?, ?, ?)'
  ).run(req.params.id, req.user.id, rating, comment || null);
  const review = db.prepare('SELECT * FROM reviews WHERE id = ?').get(result.lastInsertRowid);
  res.status(201).json(review);
});

// ── Health ──

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', app: 'calliope-books' });
});

// ── Start ──

app.listen(PORT, () => {
  console.log(`Calliope Books running on :${PORT}`);
});
