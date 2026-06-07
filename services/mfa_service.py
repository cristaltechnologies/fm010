"""
services/mfa_service.py
All I/O for the MFA (Master File Accounts) ISAM file → PostgreSQL mfa table
Mirrors: selmfa.cp, recmfa.cp
"""
import psycopg2
import psycopg2.extras
from decimal import Decimal
from db.connection import get_conn
from models.mfa import MfaRecord


def _d(v) -> Decimal:
    try: return Decimal(str(v or 0))
    except: return Decimal(0)

def _arr(v) -> list:
    if not v: return [Decimal(0)] * 13
    return [_d(x) for x in v]


class MfaService:

    def __init__(self):
        self.file_status = "00"

    def _conn(self):
        return get_conn()

    def _row_to_rec(self, row: dict) -> MfaRecord:
        return MfaRecord(
            mfa_gan=row["mfa_gan"],
            mfa_gan_desc=row["mfa_gan_desc"],
            mfa_main_desc=row["mfa_main_desc"],
            mfa_dr_cr_flag=int(row["mfa_dr_cr_flag"] or 0),
            mfa_left_chapter=row["mfa_left_chapter"],
            mfa_right_chapter=row["mfa_right_chapter"],
            mfa_currency_code=int(row["mfa_currency_code"] or 0),
            mfa_active_flag=int(row["mfa_active_flag"] or 0),
            mfa_dr=_d(row["mfa_dr"]),
            mfa_cr=_d(row["mfa_cr"]),
            mfa_frn_dr=_d(row["mfa_frn_dr"]),
            mfa_frn_cr=_d(row["mfa_frn_cr"]),
            mfa_dr_lm=_d(row["mfa_dr_lm"]),
            mfa_cr_lm=_d(row["mfa_cr_lm"]),
            mfa_frn_dr_lm=_d(row["mfa_frn_dr_lm"]),
            mfa_frn_cr_lm=_d(row["mfa_frn_cr_lm"]),
            mfa_frn_bal_ly=_d(row["mfa_frn_bal_ly"]),
            mfa_prev_2_years=_d(row["mfa_prev_2_years"]),
            mfa_cy=_arr(row["mfa_cy"]),
            mfa_ly=_arr(row["mfa_ly"]),
            mfa_bud=_arr(row["mfa_bud"]),
            mfa_forcast=_arr(row["mfa_forcast"]),
            mfa_dept=row["mfa_dept"],
            mfa_gan1=row["mfa_gan1"],
        )

    # ── READ by primary key — mirrors: READ MFA KEY IS MFA-GAN ─────────────
    def read_by_key(self, mfa_gan: str) -> MfaRecord | None:
        try:
            with self._conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM mfa WHERE mfa_gan = %s", (mfa_gan.ljust(12)[:12],))
                row = cur.fetchone()
            if row:
                self.file_status = "00"
                return self._row_to_rec(row)
            self.file_status = "23"
            return None
        except psycopg2.Error:
            self.file_status = "90"
            return None

    # ── READ LOCK ───────────────────────────────────────────────────────────
    def read_lock(self, mfa_gan: str) -> MfaRecord | None:
        try:
            with self._conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM mfa WHERE mfa_gan = %s FOR UPDATE NOWAIT",
                    (mfa_gan.ljust(12)[:12],)
                )
                row = cur.fetchone()
            if row:
                self.file_status = "00"
                return self._row_to_rec(row)
            self.file_status = "23"
            return None
        except psycopg2.errors.LockNotAvailable:
            self.file_status = "9B"
            return None
        except psycopg2.Error:
            self.file_status = "90"
            return None

    def unlock(self):
        try: self._conn().commit()
        except: pass
