"""
models/mfa.py
MFA — Master File Accounts record (recmfa.cp)
"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class MfaRecord:
    """
    Mirrors COBOL MFA-REC (recmfa.cp).
    Passive data, active balances, and 13-period monthly tables.
    """
    mfa_gan:            str     = ""          # PIC X(12) — primary key
    mfa_gan_desc:       str     = ""          # PIC X(25)
    mfa_main_desc:      str     = ""          # PIC X(25)
    mfa_dr_cr_flag:     int     = 0           # PIC 9
    mfa_left_chapter:   str     = ""          # PIC X(8)
    mfa_right_chapter:  str     = ""          # PIC X(8)
    mfa_currency_code:  int     = 0           # PIC 99
    mfa_active_flag:    int     = 0           # PIC 9

    # Active balances
    mfa_dr:         Decimal = Decimal(0)
    mfa_cr:         Decimal = Decimal(0)
    mfa_frn_dr:     Decimal = Decimal(0)
    mfa_frn_cr:     Decimal = Decimal(0)
    mfa_dr_lm:      Decimal = Decimal(0)
    mfa_cr_lm:      Decimal = Decimal(0)
    mfa_frn_dr_lm:  Decimal = Decimal(0)
    mfa_frn_cr_lm:  Decimal = Decimal(0)
    mfa_frn_bal_ly: Decimal = Decimal(0)
    mfa_prev_2_years: Decimal = Decimal(0)

    # Monthly tables (13 periods each — MFA-CY, MFA-LY, MFA-BUD, MFA-FORCAST)
    mfa_cy:      list = field(default_factory=lambda: [Decimal(0)] * 13)
    mfa_ly:      list = field(default_factory=lambda: [Decimal(0)] * 13)
    mfa_bud:     list = field(default_factory=lambda: [Decimal(0)] * 13)
    mfa_forcast: list = field(default_factory=lambda: [Decimal(0)] * 13)

    # Alternate key
    mfa_dept:    str  = "000000"   # PIC 9(6)
    mfa_gan1:    str  = ""         # PIC X(12)

    # ── MFA-GAN REDEFINES ───────────────────────────────────────────────────
    @property
    def mfa_main(self) -> str:
        """MFA-MAIN PIC 999 — first 3 chars of mfa_gan"""
        return self.mfa_gan[:3]

    @property
    def mfa_statement_code(self) -> int:
        """MFA-STATEMENT-CODE PIC 9 — first digit of mfa_main"""
        try: return int(self.mfa_gan[0])
        except: return 0

    @property
    def mfa_aux(self) -> str:
        """MFA-AUX PIC 9(6) — chars 5-10 of mfa_gan"""
        return self.mfa_gan[4:10]

    def __repr__(self):
        return (f"MfaRecord(gan={self.mfa_gan!r}, "
                f"desc={self.mfa_gan_desc.strip()!r})")
