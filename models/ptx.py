"""
models/ptx.py
PTX record — mirrors COBOL recptx.cp

The COBOL PTX-OTHER-DATA (700 bytes) is stored as a plain CHAR(700) in
PostgreSQL.  Each "REDEFINES" overlay (PTX-TYPE-DATA, PTX-GAN-DATA, etc.)
is exposed here as a property that slices / packs the raw bytes, preserving
exact backward compatibility with the file layout.
"""
from dataclasses import dataclass, field
from decimal import Decimal


# ── PTX-CODE values (from recptx.cp comments) ──────────────────────────────
PTX_CODE_JVX            = 1
PTX_CODE_CLTX           = 2
PTX_CODE_STX            = 3
PTX_CODE_FIXED_ASSETS   = 4
PTX_CODE_JOBS           = 5
PTX_CODE_PAYROLL        = 6
PTX_CODE_COMP           = 7
PTX_CODE_PASS           = 8
PTX_CODE_GAN            = 9
PTX_CODE_WH             = 10
PTX_CODE_CLIENT_AREA    = 11
PTX_CODE_CLIENT_TYPE    = 12
PTX_CODE_SALESMAN       = 13
PTX_CODE_BRAND          = 14
PTX_CODE_CURRENCY       = 15


def _pad(s: str, length: int, char: str = " ") -> str:
    """Left-justify and pad/truncate to exact length, like COBOL PIC X(n)."""
    return str(s or "").ljust(length, char)[:length]

def _zpad(n, length: int) -> str:
    """Right-justify numeric string and zero-fill, like COBOL PIC 9(n)."""
    return str(int(n or 0)).zfill(length)[:length]


@dataclass
class PtxRecord:
    """
    Mirrors COBOL PTX-REC (recptx.cp).

    Storage layout (total = 762 bytes):
        ptx_key         [0:12]   X(12)  primary key
        ptx_code1      [12:14]   99     alternate-key byte 1-2
        ptx_desc       [14:39]   X(25)  alternate-key byte 3-27
        ptx_subdesc    [39:64]   X(25)  alternate-key byte 28-52
        ptx_other_data [64:764]  X(700) payload
    """
    # ── Core fields stored in DB ────────────────────────────────────────────
    ptx_key:        str = ""          # PIC X(12)
    ptx_code1:      str = "00"        # PIC 99  (part of alt key)
    ptx_desc:       str = ""          # PIC X(25)
    ptx_subdesc:    str = ""          # PIC X(25)
    ptx_other_data: str = ""          # PIC X(700)

    # ── PTX-KEY REDEFINES ───────────────────────────────────────────────────

    @property
    def ptx_code(self) -> str:
        """PTX-CODE PIC 99 — first 2 chars of ptx_key"""
        return self.ptx_key[:2]

    @ptx_code.setter
    def ptx_code(self, value):
        self.ptx_key = _zpad(value, 2) + self.ptx_minor_key

    @property
    def ptx_minor_key(self) -> str:
        """PTX-MINOR-KEY PIC X(10) — chars 3-12 of ptx_key"""
        return self.ptx_key[2:12]

    @ptx_minor_key.setter
    def ptx_minor_key(self, value):
        self.ptx_key = self.ptx_code + _pad(value, 10)

    @property
    def ptx_type(self) -> int:
        """PTX-TYPE PIC 999 — first 3 chars of ptx_minor_key"""
        try:
            return int(self.ptx_minor_key[:3])
        except ValueError:
            return 0

    @ptx_type.setter
    def ptx_type(self, value):
        mk = _zpad(value, 3) + self.ptx_minor_key[3:]
        self.ptx_key = self.ptx_code + _pad(mk, 10)

    @property
    def ptx_type_filler(self) -> str:
        return self.ptx_minor_key[3:]

    @ptx_type_filler.setter
    def ptx_type_filler(self, value):
        mk = self.ptx_minor_key[:3] + _pad(value, 7)
        self.ptx_key = self.ptx_code + _pad(mk, 10)

    # ── PTX-OTHER-DATA REDEFINES (TYPE 1-3: PTX-TYPE-DATA) ─────────────────
    # Layout: short_desc[0:4] vansales_ref[4:10] grpa_link[10:13]
    #         grpb_link[13:16] smansales_ref[16:22] icesales_ref[22:28]
    #         quoz_itv_ref[28:34] vending_ref[34:40] filler[40:700]

    def _od(self) -> str:
        """Return ptx_other_data padded to 700."""
        return _pad(self.ptx_other_data, 700)

    def _set_od(self, value: str):
        self.ptx_other_data = _pad(value, 700)

    @property
    def ptx_short_desc(self) -> str:
        return self._od()[0:4]

    @ptx_short_desc.setter
    def ptx_short_desc(self, v):
        od = list(self._od())
        s = _pad(v, 4)
        od[0:4] = list(s)
        self._set_od("".join(od))

    @property
    def ptx_vansales_ref(self) -> int:
        try: return int(self._od()[4:10])
        except: return 0

    @ptx_vansales_ref.setter
    def ptx_vansales_ref(self, v):
        od = list(self._od())
        od[4:10] = list(_zpad(v, 6))
        self._set_od("".join(od))

    @property
    def ptx_vansales_coll_ref(self) -> int:
        """PTX-VANSALES-COLL-REF REDEFINES PTX-VANSALES-REF"""
        return self.ptx_vansales_ref

    @ptx_vansales_coll_ref.setter
    def ptx_vansales_coll_ref(self, v):
        self.ptx_vansales_ref = v

    @property
    def ptx_smansales_ref(self) -> int:
        try: return int(self._od()[16:22])
        except: return 0

    @ptx_smansales_ref.setter
    def ptx_smansales_ref(self, v):
        od = list(self._od())
        od[16:22] = list(_zpad(v, 6))
        self._set_od("".join(od))

    @property
    def ptx_icesales_ref(self) -> int:
        try: return int(self._od()[22:28])
        except: return 0

    @ptx_icesales_ref.setter
    def ptx_icesales_ref(self, v):
        od = list(self._od())
        od[22:28] = list(_zpad(v, 6))
        self._set_od("".join(od))

    @property
    def ptx_quoz_itv_ref(self) -> int:
        try: return int(self._od()[28:34])
        except: return 0

    @ptx_quoz_itv_ref.setter
    def ptx_quoz_itv_ref(self, v):
        od = list(self._od())
        od[28:34] = list(_zpad(v, 6))
        self._set_od("".join(od))

    @property
    def ptx_vending_ref(self) -> int:
        try: return int(self._od()[34:40])
        except: return 0

    @ptx_vending_ref.setter
    def ptx_vending_ref(self, v):
        od = list(self._od())
        od[34:40] = list(_zpad(v, 6))
        self._set_od("".join(od))

    # ── PTX-GAN-DATA REDEFINES PTX-OTHER-DATA ──────────────────────────────
    # gan[0:12] gan_program_name[12:22] filler[22:700]

    @property
    def ptx_gan(self) -> str:
        return self._od()[0:12]

    @ptx_gan.setter
    def ptx_gan(self, v):
        od = list(self._od())
        od[0:12] = list(_pad(v, 12))
        self._set_od("".join(od))

    @property
    def ptx_gan_program_name(self) -> str:
        return self._od()[12:22]

    @ptx_gan_program_name.setter
    def ptx_gan_program_name(self, v):
        od = list(self._od())
        od[12:22] = list(_pad(v, 10))
        self._set_od("".join(od))

    @property
    def ptx_gan_filler(self) -> str:
        return self._od()[22:700]

    @ptx_gan_filler.setter
    def ptx_gan_filler(self, v):
        od = list(self._od())
        od[22:700] = list(_pad(v, 678))
        self._set_od("".join(od))

    # ── PTX-CC-DATA REDEFINES PTX-OTHER-DATA ───────────────────────────────
    @property
    def ptx_cc_desc(self) -> str:
        return self._od()[0:4]

    @ptx_cc_desc.setter
    def ptx_cc_desc(self, v):
        od = list(self._od())
        od[0:4] = list(_pad(v, 4))
        self._set_od("".join(od))

    @property
    def ptx_cc_rate(self) -> Decimal:
        try: return Decimal(self._od()[4:11]) / Decimal("10000")
        except: return Decimal(0)

    # ── Build ptx_key from ptx_code + ptx_type ─────────────────────────────
    @classmethod
    def build_key(cls, ptx_code: int, ptx_type: int) -> str:
        return _zpad(ptx_code, 2) + _zpad(ptx_type, 3) + " " * 7

    def __repr__(self):
        return (f"PtxRecord(key={self.ptx_key!r}, code={self.ptx_code}, "
                f"desc={self.ptx_desc.strip()!r})")
