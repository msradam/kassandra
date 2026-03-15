const express = require('express');
const initSqlJs = require('sql.js');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');

const app = express();
app.use(express.json());

const JWT_SECRET = 'calliope-muse-of-epic-poetry';
const PORT = process.env.PORT || 3000;

let db;

async function initDb() {
  const SQL = await initSqlJs();
  db = new SQL.Database();

  db.run(`
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE books (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      author TEXT NOT NULL,
      genre TEXT,
      year INTEGER,
      price REAL NOT NULL,
      stock INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      book_id INTEGER NOT NULL REFERENCES books(id),
      user_id INTEGER NOT NULL REFERENCES users(id),
      rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
      comment TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_books_genre ON books(genre);
    CREATE INDEX idx_books_author ON books(author);
    CREATE INDEX idx_reviews_book ON reviews(book_id);
  `);

  seed();
}

// ── Helpers ──

function all(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

function get(sql, params = []) {
  const rows = all(sql, params);
  return rows[0] || null;
}

function run(sql, params = []) {
  db.run(sql, params);
  const id = db.exec("SELECT last_insert_rowid()")[0]?.values[0][0];
  const changes = db.getRowsModified();
  return { lastId: id, changes };
}

// ── Seed data ──

function seed() {
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

  for (let i = 0; i < 30; i++) {
    run(
      'INSERT INTO books (title, author, genre, year, price, stock) VALUES (?, ?, ?, ?, ?, ?)',
      [titles[i], authors[i % authors.length], genres[i % genres.length],
       1200 + Math.floor(Math.random() * 800), 5.99 + Math.floor(Math.random() * 30),
       Math.floor(Math.random() * 50)]
    );
  }

  const hash = crypto.createHash('sha256').update('calliope123').digest('hex');
  run('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
    ['reader', 'reader@calliope.dev', hash]);

  // Seed some reviews so queries return data
  for (let bookId = 1; bookId <= 15; bookId++) {
    run('INSERT INTO reviews (book_id, user_id, rating, comment) VALUES (?, ?, ?, ?)',
      [bookId, 1, Math.ceil(Math.random() * 5), 'A timeless classic.']);
  }
}

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
    const { lastId } = run('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
      [username, email, hash]);
    const token = jwt.sign({ id: lastId, username }, JWT_SECRET, { expiresIn: '1h' });
    res.status(201).json({ user: { id: lastId, username, email }, token });
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
  const user = get('SELECT id, username, email FROM users WHERE email = ? AND password_hash = ?',
    [email, hash]);
  if (!user) return res.status(401).json({ error: 'Invalid credentials' });
  const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '1h' });
  res.json({ user, token });
});

// ── Books routes ──

app.get('/api/books/trending', (req, res) => {
  const { period = 'all', limit = 10 } = req.query;
  let dateFilter = '';
  if (period === 'week') dateFilter = "AND r.created_at >= datetime('now', '-7 days')";
  else if (period === 'month') dateFilter = "AND r.created_at >= datetime('now', '-30 days')";
  else if (period === 'year') dateFilter = "AND r.created_at >= datetime('now', '-365 days')";

  const trending = all(`
    SELECT b.*,
           COUNT(r.id) as review_count,
           ROUND(AVG(r.rating), 2) as avg_rating,
           SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) as positive_reviews
    FROM books b
    JOIN reviews r ON r.book_id = b.id
    WHERE 1=1 ${dateFilter}
    GROUP BY b.id
    HAVING review_count >= 1
    ORDER BY avg_rating DESC, review_count DESC
    LIMIT ?
  `, [Number(limit)]);

  res.json({ trending, period, count: trending.length });
});

app.get('/api/books', (req, res) => {
  const { genre, author, search, limit = 20, offset = 0 } = req.query;
  let sql = 'SELECT * FROM books WHERE 1=1';
  const params = [];
  if (genre) { sql += ' AND genre = ?'; params.push(genre); }
  if (author) { sql += ' AND author = ?'; params.push(author); }
  if (search) { sql += ' AND (title LIKE ? OR author LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  sql += ' ORDER BY id LIMIT ? OFFSET ?';
  params.push(Number(limit), Number(offset));
  const books = all(sql, params);
  const total = get('SELECT COUNT(*) as n FROM books').n;
  res.json({ books, total, limit: Number(limit), offset: Number(offset) });
});

app.get('/api/books/:id', (req, res) => {
  const book = get('SELECT * FROM books WHERE id = ?', [Number(req.params.id)]);
  if (!book) return res.status(404).json({ error: 'Book not found' });
  const reviews = all(
    'SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.book_id = ? ORDER BY r.created_at DESC',
    [Number(req.params.id)]
  );
  const avg = get('SELECT AVG(rating) as avg_rating FROM reviews WHERE book_id = ?', [Number(req.params.id)]);
  res.json({ ...book, reviews, avg_rating: avg?.avg_rating || null });
});

app.post('/api/books', authenticate, (req, res) => {
  const { title, author, genre, year, price, stock } = req.body;
  if (!title || !author || !price) {
    return res.status(400).json({ error: 'title, author, and price required' });
  }
  const { lastId } = run(
    'INSERT INTO books (title, author, genre, year, price, stock) VALUES (?, ?, ?, ?, ?, ?)',
    [title, author, genre || null, year || null, price, stock || 0]
  );
  res.status(201).json(get('SELECT * FROM books WHERE id = ?', [lastId]));
});

app.put('/api/books/:id', authenticate, (req, res) => {
  const existing = get('SELECT * FROM books WHERE id = ?', [Number(req.params.id)]);
  if (!existing) return res.status(404).json({ error: 'Book not found' });
  const { title, author, genre, year, price, stock } = req.body;
  run(
    'UPDATE books SET title=?, author=?, genre=?, year=?, price=?, stock=? WHERE id=?',
    [title || existing.title, author || existing.author, genre || existing.genre,
     year || existing.year, price || existing.price, stock ?? existing.stock, Number(req.params.id)]
  );
  res.json(get('SELECT * FROM books WHERE id = ?', [Number(req.params.id)]));
});

app.delete('/api/books/:id', authenticate, (req, res) => {
  const { changes } = run('DELETE FROM books WHERE id = ?', [Number(req.params.id)]);
  if (changes === 0) return res.status(404).json({ error: 'Book not found' });
  res.status(204).end();
});

// ── Reviews routes ──

app.get('/api/books/:id/reviews', (req, res) => {
  const reviews = all(
    'SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.book_id = ? ORDER BY r.created_at DESC',
    [Number(req.params.id)]
  );
  res.json({ reviews });
});

app.post('/api/books/:id/reviews', authenticate, (req, res) => {
  const { rating, comment } = req.body;
  if (!rating || rating < 1 || rating > 5) {
    return res.status(400).json({ error: 'rating (1-5) required' });
  }
  const book = get('SELECT id FROM books WHERE id = ?', [Number(req.params.id)]);
  if (!book) return res.status(404).json({ error: 'Book not found' });
  const { lastId } = run(
    'INSERT INTO reviews (book_id, user_id, rating, comment) VALUES (?, ?, ?, ?)',
    [Number(req.params.id), req.user.id, rating, comment || null]
  );
  res.status(201).json(get('SELECT * FROM reviews WHERE id = ?', [lastId]));
});

// ── Search ──

app.get('/api/books/search', (req, res) => {
  const { q, limit = 20, offset = 0 } = req.query;
  if (!q) return res.status(400).json({ error: 'q parameter required' });

  // Deliberately slow: correlated subquery + N+1 pattern
  const books = all(
    `SELECT b.*,
       (SELECT COUNT(*) FROM reviews r WHERE r.book_id = b.id) as review_count,
       (SELECT AVG(r.rating) FROM reviews r WHERE r.book_id = b.id) as avg_rating
     FROM books b
     WHERE b.title LIKE ? OR b.author LIKE ? OR b.genre LIKE ?
     LIMIT ? OFFSET ?`,
    [`%${q}%`, `%${q}%`, `%${q}%`, Number(limit), Number(offset)]
  );

  // N+1: fetch reviews for each book individually
  const enriched = books.map(book => {
    const reviews = all(
      'SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.book_id = ? ORDER BY r.created_at DESC LIMIT 3',
      [book.id]
    );
    return { ...book, recent_reviews: reviews };
  });

  // Simulate slow full-text scoring (blocking)
  const start = Date.now();
  while (Date.now() - start < 800) { /* busy wait */ }

  res.json({ results: enriched, query: q, count: enriched.length, total: books.length });
});

// ── Health ──

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', app: 'calliope-books' });
});

// ── Start ──

initDb().then(() => {
  app.listen(PORT, () => {
    console.log(`Calliope Books running on :${PORT}`);
  });
});
