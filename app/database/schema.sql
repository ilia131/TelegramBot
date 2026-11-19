CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY,
    volume_gb INTEGER NOT NULL CHECK(volume_gb > 0),
    duration_days INTEGER NOT NULL CHECK(duration_days > 0),
    price_toman INTEGER NOT NULL CHECK(price_toman > 0)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    volume_gb INTEGER NOT NULL,
    duration_days INTEGER NOT NULL,
    price_toman INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'draft', 'awaiting_transfer', 'awaiting_receipt', 'pending_review',
        'approved', 'rejected', 'awaiting_provisioning', 'provisioned', 'cancelled'
    )),
    config_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_draft ON orders(user_id)
WHERE status IN ('draft', 'awaiting_transfer', 'awaiting_receipt');
CREATE INDEX IF NOT EXISTS customer_orders ON orders(user_id, id DESC);
CREATE TABLE IF NOT EXISTS payment_receipts (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id),
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL CHECK(file_size BETWEEN 1 AND 10485760),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    external_id TEXT NOT NULL UNIQUE,
    subscription_url TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    quota_gb REAL NOT NULL CHECK(quota_gb > 0),
    used_gb REAL NOT NULL CHECK(used_gb >= 0),
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    balance_toman INTEGER NOT NULL DEFAULT 0 CHECK(balance_toman >= 0),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES wallets(user_id),
    idempotency_key TEXT NOT NULL UNIQUE,
    amount_toman INTEGER NOT NULL CHECK(amount_toman != 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admin_actions (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id),
    admin_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    recipient INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('review', 'approved', 'rejected')),
    next_attempt INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(order_id, recipient, kind)
);
