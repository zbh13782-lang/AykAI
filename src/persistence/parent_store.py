from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
class PostgresParentStore:
    def __init__(self,dsn):
        self.dsn = dsn

    def init_schema(self):
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                #建表
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS parent_chunks (
                        parent_id TEXT PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                #索引
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_parent_chunks_doc_id
                        ON parent_chunks (doc_id)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_parent_chunks_source
                        ON parent_chunks (source)
                    """
                )

    def upsert_parents(self,rows:list[dict[str, Any]]) -> None:
        if not rows:
            return

        normalized_rows = [
            {
                **row,
                "metadata":Jsonb(row.get("metadata",{}))
            }
            for row in rows
        ]

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                #批量地插入数据，更快
                cur.executemany(
                    """
                    INSERT INTO parent_chunks (parent_id, doc_id, source, content, metadata)
                    VALUES (%(parent_id)s, %(doc_id)s, %(source)s, %(content)s, %(metadata)s)
                    ON CONFLICT (parent_id)
                    DO UPDATE SET
                        doc_id = EXCLUDED.doc_id,
                        source = EXCLUDED.source,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    normalized_rows,
                )

    def fetch_parent(self,parent_ids:list[str]) -> dict[str,dict[str, Any]]:
        if not parent_ids:
            return {}

        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT parent_id, doc_id, source, content, metadata
                    FROM parent_chunks
                    WHERE parent_id = ANY (%s)
                    """,
                    (parent_ids,),
                )
                row = cur.fetchall()
        return {r["parent_id"]:dict(r) for r in row}