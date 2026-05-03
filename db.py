import os
from threading import Lock
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

_schema_lock = Lock()
_schema_initialized = False


def get_connection_string() -> str:
    return (
        f"host={os.getenv('DB_HOST', '192.168.1.211')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'n8n')} "
        f"user={os.getenv('DB_USER', 'n8n')} "
        f"password={os.getenv('DB_PASSWORD', '')}"
    )


@contextmanager
def get_db():
    with psycopg.connect(get_connection_string(), row_factory=dict_row) as connection:
        yield connection


def init_db() -> None:
    global _schema_initialized

    if _schema_initialized:
        return

    with _schema_lock:
        if _schema_initialized:
            return

        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(824501)")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS video_posts (
                        id BIGSERIAL PRIMARY KEY,
                        device_id INTEGER NOT NULL,
                        device_platform_id INTEGER,
                        account_id INTEGER,
                        workflow_id INTEGER NOT NULL,
                        video_platform TEXT NOT NULL DEFAULT '',
                        code_product TEXT NOT NULL DEFAULT '',
                        link_product TEXT NOT NULL DEFAULT '',
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        tags TEXT[] NOT NULL DEFAULT '{}',
                        video_url TEXT NOT NULL DEFAULT '',
                        cover_url TEXT NOT NULL DEFAULT '',
                        local_video_path TEXT NOT NULL DEFAULT '',
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        status TEXT NOT NULL DEFAULT 'ready',
                        upload_job_id BIGINT,
                        upload_status TEXT NOT NULL DEFAULT 'not_sent',
                        last_error TEXT NOT NULL DEFAULT '',
                        result JSONB NOT NULL DEFAULT '{}'::jsonb,
                        uploaded_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS video_platform TEXT NOT NULL DEFAULT ''
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS upload_job_id BIGINT
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS upload_status TEXT NOT NULL DEFAULT 'not_sent'
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS last_error TEXT NOT NULL DEFAULT ''
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE video_posts
                    ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMPTZ
                    """
                )
                cursor.execute("ALTER TABLE video_posts ALTER COLUMN device_platform_id DROP NOT NULL")
                cursor.execute("ALTER TABLE video_posts ALTER COLUMN account_id DROP NOT NULL")
                cursor.execute("ALTER TABLE video_posts ALTER COLUMN code_product SET DEFAULT ''")
                cursor.execute("ALTER TABLE video_posts ALTER COLUMN link_product SET DEFAULT ''")
                cursor.execute("ALTER TABLE video_posts ALTER COLUMN video_url SET DEFAULT ''")
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_video_posts_updated_at
                    ON video_posts (updated_at DESC);
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS video_post_events (
                        id BIGSERIAL PRIMARY KEY,
                        video_id BIGINT,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL DEFAULT '',
                        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_video_post_events_video_created
                    ON video_post_events (video_id, created_at DESC);
                    """
                )
                cursor.execute("SELECT pg_advisory_unlock(824501)")
            connection.commit()
        _schema_initialized = True
