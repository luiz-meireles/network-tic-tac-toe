CREATE TABLE IF NOT EXISTS users(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    win_count INTEGER,
    lose_count INTEGER,
    tie_count INTEGER
);

CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    type TEXT NOT NULL,
    log json
)