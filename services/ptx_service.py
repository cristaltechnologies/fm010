"""
services/ptx_service.py
All I/O for the PTX file — replaces ISAM operations from selptx.cp / recptx.cp
Mirrors COBOL ACCESS MODE IS DYNAMIC (random + sequential access).
"""
import psycopg
from db.connection import get_conn
from models.ptx import PtxRecord, _pad, _zpad


OK_STATUS = "00"


class PtxService:
    """
    COBOL ISAM PTX file → PostgreSQL ptx table.

    File status codes returned (2-char, mirrors COBOL FILE-STATUS):
        "00" success
        "10" end of file
        "22" duplicate key on write
        "23" record not found
        "35" file unavailable
        "90" other error
    """

    def __init__(self):
        self.file_status = "00"

    def _conn(self):
        return get_conn()

    def _row_to_rec(self, row: dict) -> PtxRecord:
        return PtxRecord(
            ptx_key=row["ptx_key"],
            ptx_code1=row["ptx_code1"],
            ptx_desc=row["ptx_desc"],
            ptx_subdesc=row["ptx_subdesc"],
            ptx_other_data=row["ptx_other_data"],
        )

    # ── READ by primary key — mirrors: READ PTX KEY IS PTX-KEY ─────────────
    def read_by_key(self, ptx_key: str) -> PtxRecord | None:
        try:
            with self._conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT ptx_key, ptx_code1, ptx_desc, ptx_subdesc, ptx_other_data "
                    "FROM ptx WHERE ptx_key = %s",
                    (_pad(ptx_key, 12),)
                )
                row = cur.fetchone()
            if row:
                self.file_status = "00"
                return self._row_to_rec(row)
            self.file_status = "23"
            return None
        except psycopg2.Error as e:
            self.file_status = "90"
            return None

    # ── READ LOCK — mirrors: READ PTX RECORD LOCK ──────────────────────────
    # PostgreSQL uses row-level locking automatically on UPDATE/DELETE.
    # For explicit lock (e.g. SELECT FOR UPDATE), use this variant.
    def read_lock(self, ptx_key: str) -> PtxRecord | None:
        try:
            with self._conn().cursor(cursor_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    "SELECT ptx_key, ptx_code1, ptx_desc, ptx_subdesc, ptx_other_data "
                    "FROM ptx WHERE ptx_key = %s FOR UPDATE NOWAIT",
                    (_pad(ptx_key, 12),)
                )
                row = cur.fetchone()
            if row:
                self.file_status = "00"
                return self._row_to_rec(row)
            self.file_status = "23"
            return None
        except psycopg2.errors.LockNotAvailable:
            self.file_status = "9B"   # record locked by another session
            return None
        except psycopg2.Error:
            self.file_status = "90"
            return None

    # ── READ sequential — mirrors: READ PTX NEXT ───────────────────────────
    def read_all(self) -> list[PtxRecord]:
        try:
            with self._conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT ptx_key, ptx_code1, ptx_desc, ptx_subdesc, ptx_other_data "
                    "FROM ptx ORDER BY ptx_key"
                )
                rows = cur.fetchall()
            self.file_status = "00"
            return [self._row_to_rec(r) for r in rows]
        except psycopg2.Error:
            self.file_status = "90"
            return []

    # ── READ by alternate key — mirrors: READ PTX KEY IS PTX-ALT-KEY1 ──────
    def read_by_alt_key(self, ptx_code1: str, ptx_desc: str = "") -> list[PtxRecord]:
        try:
            with self._conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT ptx_key, ptx_code1, ptx_desc, ptx_subdesc, ptx_other_data "
                    "FROM ptx WHERE ptx_code1 = %s AND ptx_desc LIKE %s ORDER BY ptx_key",
                    (_zpad(ptx_code1, 2), ptx_desc.strip() + "%")
                )
                rows = cur.fetchall()
            self.file_status = "00"
            return [self._row_to_rec(r) for r in rows]
        except psycopg2.Error:
            self.file_status = "90"
            return []

    # ── WRITE — mirrors: WRITE PTX-REC INVALID KEY ─────────────────────────
    def write(self, rec: PtxRecord) -> bool:
        try:
            with self._conn().cursor() as cur:
                cur.execute(
                    "INSERT INTO ptx (ptx_key, ptx_code1, ptx_desc, ptx_subdesc, ptx_other_data) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        _pad(rec.ptx_key, 12),
                        _zpad(rec.ptx_code1, 2),
                        _pad(rec.ptx_desc, 25),
                        _pad(rec.ptx_subdesc, 25),
                        _pad(rec.ptx_other_data, 700),
                    )
                )
            self._conn().commit()
            self.file_status = "00"
            return True
        except psycopg2.errors.UniqueViolation:
            self._conn().rollback()
            self.file_status = "22"
            return False
        except psycopg2.Error:
            self._conn().rollback()
            self.file_status = "90"
            return False

    # ── REWRITE — mirrors: REWRITE PTX-REC INVALID KEY ─────────────────────
    def rewrite(self, rec: PtxRecord) -> bool:
        try:
            with self._conn().cursor() as cur:
                cur.execute(
                    "UPDATE ptx SET ptx_code1=%s, ptx_desc=%s, ptx_subdesc=%s, "
                    "ptx_other_data=%s WHERE ptx_key=%s",
                    (
                        _zpad(rec.ptx_code1, 2),
                        _pad(rec.ptx_desc, 25),
                        _pad(rec.ptx_subdesc, 25),
                        _pad(rec.ptx_other_data, 700),
                        _pad(rec.ptx_key, 12),
                    )
                )
                updated = cur.rowcount
            self._conn().commit()
            self.file_status = "00" if updated else "23"
            return updated > 0
        except psycopg2.Error:
            self._conn().rollback()
            self.file_status = "90"
            return False

    # ── DELETE — mirrors: DELETE PTX RECORD INVALID KEY ────────────────────
    def delete(self, ptx_key: str) -> bool:
        try:
            with self._conn().cursor() as cur:
                cur.execute("DELETE FROM ptx WHERE ptx_key = %s", (_pad(ptx_key, 12),))
                deleted = cur.rowcount
            self._conn().commit()
            self.file_status = "00" if deleted else "23"
            return deleted > 0
        except psycopg2.Error:
            self._conn().rollback()
            self.file_status = "90"
            return False

    # ── UNLOCK — mirrors: UNLOCK PTX RECORD (commit releases the lock) ─────
    def unlock(self):
        try:
            self._conn().commit()
        except Exception:
            pass
