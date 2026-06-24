"""Initial schema — full DDL for all tables through M4.

Revision ID: 0001
Revises:
Create Date: 2026-06-23

Uses raw SQL so the migration exactly matches the validated schema.sql,
including all IF NOT EXISTS guards (safe to run against an existing DB).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            username      VARCHAR(64) UNIQUE NOT NULL,
            email         VARCHAR(128) UNIQUE,
            password_hash VARCHAR(256) NOT NULL,
            is_admin      BOOLEAN DEFAULT FALSE,
            avatar_id     VARCHAR(64) DEFAULT 'odin',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO users (username, password_hash, is_admin, avatar_id)
        VALUES ('admin', 'placeholder_hash', TRUE, 'odin')
        ON CONFLICT (username) DO NOTHING
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS virtual_accounts (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id     VARCHAR(64) UNIQUE NOT NULL DEFAULT 'default',
            balance     NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            equity      NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            peak_equity NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            drawdown    NUMERIC(6,4)  NOT NULL DEFAULT 0.0,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO virtual_accounts (user_id, balance, equity, peak_equity)
        VALUES ('default', 0.00, 0.00, 0.00)
        ON CONFLICT (user_id) DO NOTHING
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_sessions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id         VARCHAR(64) NOT NULL DEFAULT 'default',
            initial_balance NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            currency        VARCHAR(8)    NOT NULL DEFAULT 'EUR',
            started_at      TIMESTAMPTZ DEFAULT NOW(),
            ended_at        TIMESTAMPTZ,
            status          VARCHAR(16) NOT NULL DEFAULT 'RUNNING'
                            CHECK (status IN ('RUNNING','STOPPED'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sim_sessions_user   ON simulation_sessions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sim_sessions_status ON simulation_sessions(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_accounts (
            session_id  UUID PRIMARY KEY REFERENCES simulation_sessions(id) ON DELETE CASCADE,
            balance     NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            equity      NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            peak_equity NUMERIC(18,4) NOT NULL DEFAULT 0.00,
            drawdown    NUMERIC(6,4)  NOT NULL DEFAULT 0.0,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_trades (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id    UUID NOT NULL REFERENCES simulation_sessions(id) ON DELETE CASCADE,
            symbol        VARCHAR(20) NOT NULL,
            side          VARCHAR(4)  NOT NULL CHECK (side IN ('BUY','SELL')),
            quantity      NUMERIC(18,8) NOT NULL,
            entry_price   NUMERIC(18,6) NOT NULL,
            current_price NUMERIC(18,6),
            stop_loss     NUMERIC(18,6),
            take_profit   NUMERIC(18,6),
            unrealized_pnl NUMERIC(18,4) DEFAULT 0.0,
            status        VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
            opened_at     TIMESTAMPTZ DEFAULT NOW(),
            closed_at     TIMESTAMPTZ,
            close_price   NUMERIC(18,6),
            realized_pnl  NUMERIC(18,4)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_session_status ON simulation_trades(session_id, status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_logs (
            id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID NOT NULL REFERENCES simulation_sessions(id) ON DELETE CASCADE,
            timestamp  TIMESTAMPTZ DEFAULT NOW(),
            level      VARCHAR(10) NOT NULL DEFAULT 'INFO',
            message    TEXT NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sim_logs_session_ts ON simulation_logs(session_id, timestamp DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS broker_connections (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            broker           VARCHAR(32) NOT NULL,
            environment      VARCHAR(16) NOT NULL DEFAULT 'practice',
            encrypted_key    BYTEA NOT NULL,
            encrypted_secret BYTEA,
            account_id       VARCHAR(64),
            is_active        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, broker, environment)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_broker_connections_user ON broker_connections(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
            symbol        VARCHAR(20)   NOT NULL,
            side          VARCHAR(4)    NOT NULL CHECK (side IN ('BUY','SELL')),
            quantity      NUMERIC(18,8) NOT NULL,
            entry_price   NUMERIC(18,6) NOT NULL,
            current_price NUMERIC(18,6),
            stop_loss     NUMERIC(18,6),
            take_profit   NUMERIC(18,6),
            unrealized_pnl NUMERIC(18,4) DEFAULT 0.0,
            status        VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
            final_score   NUMERIC(5,4),
            kelly_fraction NUMERIC(5,4),
            opened_at     TIMESTAMPTZ DEFAULT NOW(),
            closed_at     TIMESTAMPTZ,
            close_price   NUMERIC(18,6),
            realized_pnl  NUMERIC(18,4)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_user   ON positions(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS prediction_logs (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
            timestamp           TIMESTAMPTZ DEFAULT NOW(),
            symbol              VARCHAR(20) NOT NULL,
            probability_up      NUMERIC(5,4),
            probability_down    NUMERIC(5,4),
            confidence_score    NUMERIC(5,4),
            expected_volatility NUMERIC(8,4),
            gemini_prob         NUMERIC(6,4),
            technical_score     NUMERIC(6,4),
            pattern_score       NUMERIC(6,4) DEFAULT 0.0,
            correlation_score   NUMERIC(6,4),
            final_score         NUMERIC(6,4),
            direction           VARCHAR(4),
            agent_used          VARCHAR(20) DEFAULT 'loki',
            reasoning           TEXT,
            trade_executed      BOOLEAN DEFAULT FALSE,
            position_id         UUID REFERENCES positions(id),
            outcome             VARCHAR(10),
            accuracy_pct        NUMERIC(6,2),
            is_what_if          BOOLEAN DEFAULT FALSE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_prediction_logs_symbol    ON prediction_logs(symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prediction_logs_timestamp ON prediction_logs(timestamp DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prediction_logs_user      ON prediction_logs(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS paypal_transactions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            paypal_order_id VARCHAR(64) UNIQUE NOT NULL,
            type            VARCHAR(10) NOT NULL CHECK (type IN ('DEPOSIT','WITHDRAW')),
            amount          NUMERIC(18,4) NOT NULL,
            currency        VARCHAR(5)    NOT NULL DEFAULT 'EUR',
            status          VARCHAR(20)   NOT NULL DEFAULT 'PENDING',
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            completed_at    TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id        BIGSERIAL PRIMARY KEY,
            symbol    VARCHAR(20) NOT NULL,
            timeframe VARCHAR(5)  NOT NULL DEFAULT 'M5',
            ts        TIMESTAMPTZ NOT NULL,
            open      NUMERIC(18,6) NOT NULL,
            high      NUMERIC(18,6) NOT NULL,
            low       NUMERIC(18,6) NOT NULL,
            close     NUMERIC(18,6) NOT NULL,
            volume    NUMERIC(22,4) NOT NULL DEFAULT 0,
            source    VARCHAR(20)   NOT NULL DEFAULT 'live',
            UNIQUE (symbol, timeframe, ts)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_candles_sym_tf_ts     ON candles (symbol, timeframe, ts DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_candles_sym_tf_ts_asc ON candles (symbol, timeframe, ts ASC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
            position_id     UUID REFERENCES positions(id) ON DELETE SET NULL,
            broker          VARCHAR(32)   NOT NULL,
            broker_order_id VARCHAR(128),
            symbol          VARCHAR(32)   NOT NULL,
            side            VARCHAR(4)    NOT NULL CHECK (side IN ('BUY','SELL')),
            order_type      VARCHAR(16)   NOT NULL DEFAULT 'MARKET',
            quantity        NUMERIC(18,8) NOT NULL,
            requested_price NUMERIC(18,8),
            filled_price    NUMERIC(18,8),
            filled_qty      NUMERIC(18,8) DEFAULT 0,
            status          VARCHAR(16)   NOT NULL DEFAULT 'PENDING'
                            CHECK (status IN ('PENDING','FILLED','PARTIAL','REJECTED','CANCELLED')),
            stop_loss       NUMERIC(18,8),
            take_profit     NUMERIC(18,8),
            error_message   TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_user     ON orders(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_broker   ON orders(broker, broker_order_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         BIGSERIAL PRIMARY KEY,
            user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
            event_type VARCHAR(32) NOT NULL,
            order_id   UUID REFERENCES orders(id) ON DELETE SET NULL,
            broker     VARCHAR(32),
            symbol     VARCHAR(32),
            payload    JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user  ON audit_log(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_event ON audit_log(event_type, created_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key        VARCHAR(64) PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO system_config (key, value) VALUES
            ('trading_mode',            'PAPER'),
            ('auto_mode',               'false'),
            ('final_score_threshold',   '0.85'),
            ('confidence_threshold',    '0.70'),
            ('max_drawdown_limit',      '0.10'),
            ('risk_per_trade',          '0.01')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    # Ordered to respect FK constraints
    for tbl in (
        "audit_log", "orders", "prediction_logs", "positions",
        "broker_connections", "simulation_logs", "simulation_trades",
        "simulation_accounts", "simulation_sessions",
        "paypal_transactions", "candles", "system_config",
        "virtual_accounts", "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
