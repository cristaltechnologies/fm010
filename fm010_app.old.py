"""
fm010_app.py
FM010 — PTX Parametric File Maintenance
Converted from COBOL FM010.CBL + all .CP copy files

Web UI (Flask) replaces the COBOL SCREEN SECTION (scrn.cp + inline screens).
All PROCEDURE DIVISION paragraphs are faithfully converted:
  BEGIN / INIT / PROCESS / ENTER-KEY / ADDITIONS / MODIFICATIONS /
  DELETIONS / DATA-ENTRY / ENTER-GAN-DATA + copy routines from ganin.cp,
  mfal3.cp, mainpd.cp

Run:
    pip install flask psycopg2-binary python-dotenv
    python fm010_app.py
"""
import os
from datetime import date, datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

from db.connection import get_conn, close_conn
from models.ptx import PtxRecord, _pad, _zpad
from models.mfa import MfaRecord
from services.ptx_service import PtxService
from services.mfa_service import MfaService
from services.gan_service import GanValidator
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fm010-secret")

# ── Shared service instances (mirrors OPEN I-O PTX / MFA) ──────────────────
ptx_svc = PtxService()
mfa_svc = MfaService()
gan_val = GanValidator()

OK_STATUS = "00"

# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY — mirrors MAINPD.CP helper paragraphs
# ══════════════════════════════════════════════════════════════════════════════

def get_sys_date() -> dict:
    """Mirrors GET-SYS-DATE — returns today's date components."""
    today = date.today()
    now   = datetime.now()
    return {
        "dd": today.day, "mm": today.month, "yy": today.year,
        "hrs": now.hour, "mins": now.minute,
        "sys_date_str": today.strftime("%d-%m-%Y"),
    }

def choice_lit(choice: int) -> str:
    """Mirrors FIND-CHOICE-LIT paragraph."""
    return {1: "Additions", 2: "Modifications", 3: "Deletions"}.get(choice, "")

def validate_date(dd: int, mm: int, yy: int) -> bool:
    """Mirrors VAL-DATE paragraph — returns True if valid."""
    import calendar
    if dd == 0 or mm == 0: return False
    if yy < 1970: return False
    if yy // 100 not in (19, 20): return False
    if mm > 12: return False
    try:
        _, max_day = calendar.monthrange(yy, mm)
        return 1 <= dd <= max_day
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  HTML TEMPLATES  (replaces COBOL SCREEN SECTION + scrn.cp)
# ══════════════════════════════════════════════════════════════════════════════

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>FM010 — PTX Maintenance</title>
  <style>
    body { font-family: monospace; background: #0a0a0a; color: #00ff41;
           max-width: 800px; margin: 40px auto; padding: 20px; }
    h1 { border-bottom: 1px solid #00ff41; padding-bottom: 8px; }
    .scrn-hdr { display: flex; justify-content: space-between;
                border-bottom: 1px solid #555; margin-bottom: 20px;
                font-size: 0.85em; color: #888; }
    label { display: block; margin-top: 12px; color: #aaffaa; }
    input, select { background: #111; color: #00ff41; border: 1px solid #444;
                    padding: 4px 8px; font-family: monospace; width: 300px; }
    button { margin-top: 16px; padding: 8px 20px; background: #003300;
             color: #00ff41; border: 1px solid #00ff41; cursor: pointer;
             font-family: monospace; font-size: 1em; }
    button:hover { background: #005500; }
    .flash-err  { color: #ff4444; border: 1px solid #ff4444;
                  padding: 8px; margin: 10px 0; }
    .flash-info { color: #ffff44; border: 1px solid #ffff44;
                  padding: 8px; margin: 10px 0; }
    .menu-item { margin: 8px 0; }
    a { color: #00ff41; }
    table { border-collapse: collapse; width: 100%; }
    td, th { border: 1px solid #444; padding: 4px 8px; text-align: left; }
    th { color: #aaffaa; }
    .rec-display { background: #0d1a0d; border: 1px solid #333;
                   padding: 12px; margin: 12px 0; }
  </style>
</head>
<body>
  <div class="scrn-hdr">
    <span>FM010 — PTX File Maintenance</span>
    <span>{{ sys_date }}</span>
  </div>
  {% for msg in get_flashed_messages(category_filter=["error"]) %}
    <div class="flash-err">⚠ {{ msg }}</div>
  {% endfor %}
  {% for msg in get_flashed_messages(category_filter=["info"]) %}
    <div class="flash-info">ℹ {{ msg }}</div>
  {% endfor %}
  {% block content %}{% endblock %}
</body>
</html>
"""

MAIN_MENU_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<h1>PTX File Maintenance</h1>
<p>Choices Available Are the Following:</p>
<div class="menu-item"><a href="{{ url_for('additions') }}">1. Add a Record</a></div>
<div class="menu-item"><a href="{{ url_for('modifications') }}">2. Modify a Record</a></div>
<div class="menu-item"><a href="{{ url_for('deletions') }}">3. Delete a Record</a></div>
<div class="menu-item" style="margin-top:20px">
  <a href="{{ url_for('stop_run') }}" style="color:#ff8844">99. Exit Program</a>
</div>
{% endblock %}
""")

ENTER_KEY_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<h1>{{ mode }} — Enter PTX Key</h1>
<form method="POST">
  <label>PTX Code:</label>
  <select name="ptx_code">
    <option value="1">1. JVX Type</option>
    <option value="2">2. CLTX Type</option>
    <option value="3">3. STX Type</option>
    <option value="9">9. Parametric GAN's</option>
    <option value="10">10. WH Codes</option>
  </select>
  <label>Type (3 digit):</label>
  <input name="ptx_type" type="number" min="1" max="999" required>
  <button type="submit">Next →</button>
  <a href="{{ url_for('main_menu') }}" style="margin-left:20px">← Back</a>
</form>
{% endblock %}
""")

DATA_ENTRY_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<h1>{{ mode }} — Data Entry</h1>
{% if rec %}
<div class="rec-display">
  <strong>Key:</strong> {{ rec.ptx_key }}<br>
  <strong>Code:</strong> {{ rec.ptx_code }} &nbsp;
  <strong>Type:</strong> {{ rec.ptx_type }}
</div>
{% endif %}
<form method="POST">
  <input type="hidden" name="ptx_key" value="{{ ptx_key }}">
  <input type="hidden" name="ptx_code" value="{{ ptx_code }}">
  <input type="hidden" name="ptx_type" value="{{ ptx_type }}">

  <label>Description (25 chars):</label>
  <input name="ptx_desc" maxlength="25" value="{{ rec.ptx_desc.strip() if rec else '' }}" required>

  {% if ptx_code|int != 9 %}
  <label>Short Description (4 chars):</label>
  <input name="ptx_short_desc" maxlength="4"
         value="{{ rec.ptx_short_desc.strip() if rec else '' }}">

  {% if ptx_code|int != 1 %}
  <label>VanSales / Booking &amp; Ship Ref:</label>
  <input name="ptx_vansales_ref" type="number"
         value="{{ rec.ptx_vansales_ref if rec else 0 }}">
  <label>SmanSales Reference:</label>
  <input name="ptx_smansales_ref" type="number"
         value="{{ rec.ptx_smansales_ref if rec else 0 }}">
  <label>IceSales / Manual Ref:</label>
  <input name="ptx_icesales_ref" type="number"
         value="{{ rec.ptx_icesales_ref if rec else 0 }}">
  <label>Al Quoz ITV Ref:</label>
  <input name="ptx_quoz_itv_ref" type="number"
         value="{{ rec.ptx_quoz_itv_ref if rec else 0 }}">
  <label>Vending INV Ref:</label>
  <input name="ptx_vending_ref" type="number"
         value="{{ rec.ptx_vending_ref if rec else 0 }}">
  {% else %}
  <label>Vansales Collection Ref:</label>
  <input name="ptx_vansales_coll_ref" type="number"
         value="{{ rec.ptx_vansales_coll_ref if rec else 0 }}">
  {% endif %}
  {% else %}
  {# GAN data entry — mirrors ENTER-GAN-DATA paragraph #}
  <label>GAN (format: NNN.XXXXXX):</label>
  <input name="gan_in" maxlength="10"
         value="{{ rec.ptx_gan.strip() if rec else '' }}" required>
  <label>Program Name (10 chars):</label>
  <input name="ptx_gan_program_name" maxlength="10"
         value="{{ rec.ptx_gan_program_name.strip() if rec else '' }}" required>
  {% endif %}

  <button type="submit">Save Record</button>
  <a href="{{ url_for('main_menu') }}" style="margin-left:20px">← Cancel</a>
</form>
{% endblock %}
""")

DELETE_CONFIRM_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<h1>Delete PTX Record</h1>
<div class="rec-display">
  <strong>Key:</strong> {{ rec.ptx_key }}<br>
  <strong>Description:</strong> {{ rec.ptx_desc.strip() }}<br>
  <strong>Sub Description:</strong> {{ rec.ptx_subdesc.strip() }}
</div>
<p style="color:#ff4444">⚠ Are you sure you want to DELETE this record?</p>
<form method="POST">
  <input type="hidden" name="ptx_key" value="{{ rec.ptx_key }}">
  <button type="submit" name="confirm" value="Y"
          style="background:#330000; border-color:#ff4444; color:#ff4444">
    Yes — Delete
  </button>
  <a href="{{ url_for('main_menu') }}" style="margin-left:20px">No — Cancel</a>
</form>
{% endblock %}
""")


def render(template: str, **kwargs):
    sys_info = get_sys_date()
    return render_template_string(template, sys_date=sys_info["sys_date_str"], **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES  (mirrors PROCEDURE DIVISION paragraphs)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def main_menu():
    """Mirrors PROCESS paragraph — DISPLAY MAIN-MENU / ACCEPT MAIN-MENU."""
    return render(MAIN_MENU_HTML)


@app.route("/exit")
def stop_run():
    """Mirrors EXIT-PROGRAM / STOP RUN (stoprun.cp)."""
    close_conn()
    return "<pre style='font-family:monospace;color:green'>Program FM010 ended. Goodbye.</pre>"


# ── ADDITIONS ──────────────────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
def additions():
    """Mirrors ADDITIONS paragraph."""
    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render(ENTER_KEY_HTML, mode="Add")
        ptx_key = PtxRecord.build_key(ptx_code, ptx_type)
        # READ — check if record already exists (mirrors READ PTX INVALID KEY)
        existing = ptx_svc.read_by_key(ptx_key)
        if existing:
            flash("Record Already on PTX File.", "error")
            return render(ENTER_KEY_HTML, mode="Add")
        # Redirect to data entry
        return redirect(url_for("add_data_entry",
                                ptx_key=ptx_key,
                                ptx_code=ptx_code,
                                ptx_type=ptx_type))
    return render(ENTER_KEY_HTML, mode="Add")


@app.route("/add/data", methods=["GET", "POST"])
def add_data_entry():
    """Mirrors DATA-ENTRY paragraph (for additions)."""
    ptx_key  = request.args.get("ptx_key") or request.form.get("ptx_key", "")
    ptx_code = int(request.args.get("ptx_code") or request.form.get("ptx_code", 0))
    ptx_type = int(request.args.get("ptx_type") or request.form.get("ptx_type", 0))

    if request.method == "POST":
        rec = _build_rec_from_form(request.form, ptx_key, ptx_code)
        if rec is None:
            return render(DATA_ENTRY_HTML, mode="Add", ptx_key=ptx_key,
                          ptx_code=ptx_code, ptx_type=ptx_type, rec=None)
        # WRITE PTX-REC INVALID KEY
        ok = ptx_svc.write(rec)
        if not ok:
            flash(f"Record CANNOT be Written on PTX (status {ptx_svc.file_status}).", "error")
            return render(DATA_ENTRY_HTML, mode="Add", ptx_key=ptx_key,
                          ptx_code=ptx_code, ptx_type=ptx_type, rec=rec)
        flash("Record added successfully.", "info")
        return redirect(url_for("main_menu"))

    return render(DATA_ENTRY_HTML, mode="Add", ptx_key=ptx_key,
                  ptx_code=ptx_code, ptx_type=ptx_type, rec=None)


# ── MODIFICATIONS ──────────────────────────────────────────────────────────

@app.route("/modify", methods=["GET", "POST"])
def modifications():
    """Mirrors MODIFICATIONS paragraph."""
    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render(ENTER_KEY_HTML, mode="Modify")
        ptx_key = PtxRecord.build_key(ptx_code, ptx_type)
        rec = ptx_svc.read_lock(ptx_key)    # READ PTX RECORD LOCK
        if not rec:
            flash("Record is NOT on PTX File.", "error")
            ptx_svc.unlock()
            return render(ENTER_KEY_HTML, mode="Modify")
        return redirect(url_for("modify_data_entry",
                                ptx_key=ptx_key,
                                ptx_code=ptx_code,
                                ptx_type=ptx_type))
    return render(ENTER_KEY_HTML, mode="Modify")


@app.route("/modify/data", methods=["GET", "POST"])
def modify_data_entry():
    """Mirrors DATA-ENTRY paragraph (for modifications)."""
    ptx_key  = request.args.get("ptx_key") or request.form.get("ptx_key", "")
    ptx_code = int(request.args.get("ptx_code") or request.form.get("ptx_code", 0))
    ptx_type = int(request.args.get("ptx_type") or request.form.get("ptx_type", 0))

    if request.method == "POST":
        rec = _build_rec_from_form(request.form, ptx_key, ptx_code)
        if rec is None:
            ptx_svc.unlock()
            return redirect(url_for("main_menu"))
        # REWRITE PTX-REC INVALID KEY
        ok = ptx_svc.rewrite(rec)
        ptx_svc.unlock()
        if not ok:
            flash(f"Cannot Rewrite Record on PTX File (status {ptx_svc.file_status}).", "error")
            return redirect(url_for("main_menu"))
        flash("Record modified successfully.", "info")
        return redirect(url_for("main_menu"))

    # Load existing record for display
    rec = ptx_svc.read_by_key(ptx_key)
    return render(DATA_ENTRY_HTML, mode="Modify", ptx_key=ptx_key,
                  ptx_code=ptx_code, ptx_type=ptx_type, rec=rec)


# ── DELETIONS ──────────────────────────────────────────────────────────────

@app.route("/delete", methods=["GET", "POST"])
def deletions():
    """Mirrors DELETIONS paragraph."""
    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render(ENTER_KEY_HTML, mode="Delete")
        ptx_key = PtxRecord.build_key(ptx_code, ptx_type)
        rec = ptx_svc.read_lock(ptx_key)
        if not rec:
            flash("Record is NOT on PTX File.", "error")
            ptx_svc.unlock()
            return render(ENTER_KEY_HTML, mode="Delete")
        return render(DELETE_CONFIRM_HTML, rec=rec)
    return render(ENTER_KEY_HTML, mode="Delete")


@app.route("/delete/confirm", methods=["POST"])
def delete_confirm():
    """Mirrors DELETE-YN paragraph — Y/N confirmation before DELETE."""
    ptx_key = request.form.get("ptx_key", "")
    confirm = request.form.get("confirm", "N")
    if confirm != "Y":
        ptx_svc.unlock()
        flash("Deletion cancelled.", "info")
        return redirect(url_for("main_menu"))
    ok = ptx_svc.delete(ptx_key)
    ptx_svc.unlock()
    if not ok:
        flash("Record CANNOT be Deleted.", "error")
    else:
        flash("Record deleted successfully.", "info")
    return redirect(url_for("main_menu"))


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_rec_from_form(form, ptx_key: str, ptx_code: int) -> PtxRecord | None:
    """
    Build a PtxRecord from POST form data.
    Mirrors DATA-ENTRY + ENTER-GAN-DATA paragraphs.
    Returns None on validation error (flash message set).
    """
    ptx_desc = form.get("ptx_desc", "").strip()
    if not ptx_desc:
        flash("Description cannot be blank.", "error")
        return None

    rec = PtxRecord()
    rec.ptx_key   = ptx_key
    rec.ptx_code1 = _zpad(ptx_code, 2)
    rec.ptx_desc  = _pad(ptx_desc, 25)
    rec.ptx_subdesc = ""

    if ptx_code == 9:
        # ── ENTER-GAN-DATA path ────────────────────────────────────────────
        gan_in = form.get("gan_in", "").strip()
        program_name = form.get("ptx_gan_program_name", "").strip()
        if not gan_in:
            flash("GAN cannot be blank.", "error")
            return None
        v = GanValidator()
        if not v.validate(gan_in):
            flash(v.error_message, "error")
            return None
        # Verify GAN exists in MFA (mirrors READ MFA INVALID KEY in ENTER-GAN-DATA)
        mfa_rec = mfa_svc.read_by_key(v.gan_out)
        if not mfa_rec:
            flash("Record Not On MFA.", "error")
            return None
        if not program_name:
            flash("Program Name cannot be blank.", "error")
            return None
        rec.ptx_gan = v.gan_out
        rec.ptx_gan_program_name = program_name
        rec.ptx_gan_filler = " " * 678
    else:
        # ── TYPE-DATA path ─────────────────────────────────────────────────
        rec.ptx_short_desc   = _pad(form.get("ptx_short_desc", ""), 4)
        rec.ptx_vansales_ref = int(form.get("ptx_vansales_ref", 0) or 0)
        rec.ptx_vansales_coll_ref = int(form.get("ptx_vansales_coll_ref", 0) or 0)
        rec.ptx_smansales_ref = int(form.get("ptx_smansales_ref", 0) or 0)
        rec.ptx_icesales_ref  = int(form.get("ptx_icesales_ref", 0) or 0)
        rec.ptx_quoz_itv_ref  = int(form.get("ptx_quoz_itv_ref", 0) or 0)
        rec.ptx_vending_ref   = int(form.get("ptx_vending_ref", 0) or 0)

    return rec


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT  (mirrors BEGIN paragraph + INIT)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Mirrors INIT paragraph — verify DB is accessible (like OPEN I-O PTX)
    try:
        conn = get_conn()
        print("✓ Database connection established (PTX file open).")
    except Exception as e:
        print(f"✗ Cannot connect to database: {e}")
        print("  Check your .env file and PostgreSQL settings.")
        exit(1)

    print("✓ FM010 PTX Maintenance starting on http://localhost:5000")
    app.run(debug=True, port=5000)
