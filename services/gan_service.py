"""
services/gan_service.py
GAN (General Account Number) validation — mirrors COBOL ganin.cp + ganinws.cp

GAN format:  NNN.XXXXXX   where NNN = 100-499, XXXXXX = 6-digit sub-account
Examples:    341.010070   201.001000
"""
import re


class GanValidator:
    """
    Mirrors COBOL CHECK-GANIN / SHIFTING paragraphs from ganin.cp.

    Usage:
        v = GanValidator()
        ok = v.validate("341.010070")
        if ok:
            gan_out = v.gan_out   # formatted GAN string
        else:
            print(v.error_message)
    """

    def __init__(self):
        self.gan_out:      str  = ""
        self.error_flag:   int  = 0
        self.error_message: str = ""

    def validate(self, gan_in: str) -> bool:
        """
        Full GAN validation — mirrors CHECK-GANIN paragraph.
        Sets self.gan_out, self.error_flag, self.error_message.
        Returns True if valid.
        """
        self.error_flag = 0
        self.error_message = ""
        self.gan_out = ""

        gan_in = (gan_in or "").strip()

        # ── Decompose input into GAN-MAIN-IN + GAN-POINT-IN + GAN-SUB-IN ──
        # COBOL GAN-IN is X(10): first 3 = main, char 4 = point, chars 5-10 = sub (6 chars)
        if len(gan_in) > 10:
            gan_in = gan_in[:10]

        # Pad to 10 chars (COBOL PIC X(10) behavior)
        gan_padded = gan_in.ljust(10)

        gan_main_in  = gan_padded[0:3]   # PIC X(3)
        gan_point_in = gan_padded[3:4]   # PIC X
        gan_sub_in   = list(gan_padded[4:10])   # PIC X OCCURS 6 — indices 1-6

        # ── Validate decimal point ──────────────────────────────────────────
        if gan_point_in != ".":
            return self._error("Invalid Entry of GAN")

        # ── Validate main account (100-499, numeric) ────────────────────────
        main_str = gan_main_in.strip()
        if not main_str.isdigit():
            return self._error("Invalid Entry of GAN")
        main_int = int(main_str)
        if main_int < 100 or main_int > 499:
            return self._error("Invalid Entry of GAN")

        # ── SHIFTING logic — right-align sub account ────────────────────────
        # Count trailing spaces from right in sub to determine IND
        ind = 0
        if gan_sub_in[5] == " ": ind = 1
        if gan_sub_in[4] == " " and gan_sub_in[5] == " ": ind = 2
        if gan_sub_in[3] == " " and gan_sub_in[4] == " " and gan_sub_in[5] == " ": ind = 3
        if (gan_sub_in[2] == " " and gan_sub_in[3] == " " and
                gan_sub_in[4] == " " and gan_sub_in[5] == " "): ind = 4
        if (gan_sub_in[1] == " " and gan_sub_in[2] == " " and
                gan_sub_in[3] == " " and gan_sub_in[4] == " " and
                gan_sub_in[5] == " "): ind = 5

        # Perform SHIFTING — shift digits right by IND positions
        gan_sub_out = [" "] * 6
        lgan = 7
        kgan = 7
        while kgan != 0:
            lgan -= 1
            kgan = lgan - ind
            if kgan == 0:
                break
            gan_sub_out[lgan - 1] = gan_sub_in[kgan - 1]

        sub_str = "".join(gan_sub_out)

        # ── Validate sub account ────────────────────────────────────────────
        if all(c == " " for c in gan_sub_in):
            return self._error("Invalid Entry of GAN")

        if all(c == "0" for c in gan_sub_in if c != " "):
            return self._error("Invalid Entry of GAN")

        sub_numeric = sub_str.strip()
        if not sub_numeric.isdigit() or int(sub_str.replace(" ", "0") or "0") == 0:
            return self._error("Invalid Entry of GAN")

        # ── Build GAN-OUT ───────────────────────────────────────────────────
        self.gan_out = f"{main_int:03d}.{sub_str}"
        self.error_flag = 0
        return True

    def _error(self, msg: str) -> bool:
        self.error_flag = 1
        self.error_message = msg
        return False
