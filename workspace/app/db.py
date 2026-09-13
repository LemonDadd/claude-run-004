"""SQLite 存储层：保存 1900-2100 农历压缩数据表。

数据是静态只读的：首次启动时从内置 YEAR_INFOS 落库，之后直接复用。
转换热点数据（压缩整数与年累计天数）在进程内缓存，保证批量吞吐。
"""
from __future__ import annotations

import os
import sqlite3
from typing import List, Tuple

from .lunar_data import MAX_YEAR, MIN_YEAR, YEAR_INFOS

_DEFAULT_PATH = os.environ.get("LUNAR_DB_PATH", os.path.join(os.getcwd(), "lunar.db"))


class LunarStore:
    def __init__(self, db_path: str = _DEFAULT_PATH):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._infos: List[int] | None = None
        self._count = 0

    # ---- 连接与初始化 ----
    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            # 数据仅在启动播种阶段写入，之后跨线程只读：关闭同线程约束
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._init_schema()
            self._seed()
            self._count = self._conn.execute(
                "SELECT COUNT(*) FROM lunar_year"
            ).fetchone()[0]
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lunar_year (
                year        INTEGER PRIMARY KEY,
                packed      INTEGER NOT NULL,   -- 17bit 压缩整数
                leap_month  INTEGER NOT NULL,   -- 闰月月份 0=无
                year_days   INTEGER NOT NULL,   -- 该农历年总天数
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def _seed(self) -> None:
        cur = self._conn.execute("SELECT COUNT(*) FROM lunar_year")
        if cur.fetchone()[0] == len(YEAR_INFOS):
            return
        rows = []
        for i, info in enumerate(YEAR_INFOS):
            y = MIN_YEAR + i
            leap = info & 0xF
            days = 29 * 12
            for m in range(1, 13):
                days += (info >> (16 - m)) & 1
            if leap:
                days += 29 + ((info >> 16) & 1)
            rows.append((y, info, leap, days))
        self._conn.executemany(
            "INSERT OR REPLACE INTO lunar_year (year, packed, leap_month, year_days)"
            " VALUES (?,?,?,?)",
            rows,
        )
        self._conn.commit()

    # ---- 查询 ----
    def count(self) -> int:
        self.connect()
        return self._count

    def get_packed(self, year: int) -> int | None:
        row = self.connect().execute(
            "SELECT packed FROM lunar_year WHERE year=?", (year,)
        ).fetchone()
        return row[0] if row else None

    def all_packed(self) -> List[Tuple[int, int]]:
        return self.connect().execute(
            "SELECT year, packed FROM lunar_year ORDER BY year"
        ).fetchall()


_store: LunarStore | None = None


def get_store() -> LunarStore:
    global _store
    if _store is None:
        _store = LunarStore()
        _store.connect()
    return _store
