"""
fm010_app.py  —  FM010 PTX Parametric File Maintenance
Converted from COBOL FM010.CBL + all .CP copy files
Modern corporate UI using separate Jinja2 templates.

Run:
    pip install flask psycopg2-binary python-dotenv
    python fm010_app.py
"""
import os
import psycopg2.extras
from datetime import date, datetime
from flask import (Flask, render_template, request,
                   redirect, url_for, flash)

from db.connection import get_conn, close_conn
from models.ptx import PtxRecord, _pad, _zpad
from services.ptx_service import PtxService
from services.mfa_service import MfaService
from services.gan_service import GanValidator
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fm010-secret")

ptx_svc = PtxService()
mfa_svc = MfaService()

OK_STATUS = "00"

# ── helpers ────────────────────────────────────────────────────────────────

def sys_date() -> str:
    return date.today().strftime("%d-%m-%Y")

def render(template, **kw):
    return render_template(template, sys_date=sys_date(), **kw)

def _build_rec_from_form(form, ptx_key, ptx_code):
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
        gan_in = form.get("gan_in", "").strip()
        program_name = form.get("ptx_gan_program_name", "").strip()
        if not gan_in:
            flash("GAN cannot be blank.", "error")
            return None
        v = GanValidator()
        if not v.validate(gan_in):
            flash(v.error_message, "error")
            return None
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
        rec.ptx_short_desc    = _pad(form.get("ptx_short_desc", ""), 4)
        rec.ptx_vansales_ref  = int(form.get("ptx_vansales_ref", 0) or 0)
        rec.ptx_vansales_coll_ref = int(form.get("ptx_vansales_coll_ref", 0) or 0)
        rec.ptx_smansales_ref = int(form.get("ptx_smansales_ref", 0) or 0)
        rec.ptx_icesales_ref  = int(form.get("ptx_icesales_ref", 0) or 0)
        rec.ptx_quoz_itv_ref  = int(form.get("ptx_quoz_itv_ref", 0) or 0)
        rec.ptx_vending_ref   = int(form.get("ptx_vending_ref", 0) or 0)
    return rec

# ── routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def main_menu():
    """PTX records list with optional search/filter."""
    q    = request.args.get("q", "").strip()
    code = request.args.get("code", "").strip()
    try:
        with get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql  = ("SELECT ptx_key, ptx_code, ptx_minor_key, ptx_code1, "
                    "ptx_desc, ptx_subdesc FROM ptx WHERE 1=1")
            args = []
            if q:
                sql += " AND (ptx_key ILIKE %s OR ptx_desc ILIKE %s)"
                args += [f"%{q}%", f"%{q}%"]
            if code:
                sql += " AND ptx_code = %s"
                args.append(_zpad(code, 2))
            sql += " ORDER BY ptx_key LIMIT 200"
            cur.execute(sql, args)
            records = cur.fetchall()
    except Exception:
        records = []
    return render("menu.html", records=records, q=q, code=code)


@app.route("/exit")
def stop_run():
    close_conn()
    return ("<div style='font-family:Segoe UI,sans-serif;padding:40px;"
            "color:#374151'>Program FM010 ended. You may close this tab.</div>")


# ── ADDITIONS ──────────────────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
def additions():
    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render("enter_key.html", mode="Add")
        ptx_key  = PtxRecord.build_key(ptx_code, ptx_type)
        existing = ptx_svc.read_by_key(ptx_key)
        if existing:
            flash("Record already exists on PTX file.", "error")
            return render("enter_key.html", mode="Add")
        return redirect(url_for("add_data_entry",
                                ptx_key=ptx_key,
                                ptx_code=ptx_code,
                                ptx_type=ptx_type))
    return render("enter_key.html", mode="Add")


@app.route("/add/data", methods=["GET", "POST"])
def add_data_entry():
    ptx_key  = request.args.get("ptx_key")  or request.form.get("ptx_key", "")
    ptx_code = int(request.args.get("ptx_code") or request.form.get("ptx_code", 0))
    ptx_type = int(request.args.get("ptx_type") or request.form.get("ptx_type", 0))
    if request.method == "POST":
        rec = _build_rec_from_form(request.form, ptx_key, ptx_code)
        if rec is None:
            return render("data_entry.html", mode="Add",
                          ptx_key=ptx_key, ptx_code=ptx_code,
                          ptx_type=ptx_type, rec=None)
        if not ptx_svc.write(rec):
            flash(f"Record cannot be written (status {ptx_svc.file_status}).", "error")
            return render("data_entry.html", mode="Add",
                          ptx_key=ptx_key, ptx_code=ptx_code,
                          ptx_type=ptx_type, rec=rec)
        flash("Record added successfully.", "info")
        return redirect(url_for("main_menu"))
    return render("data_entry.html", mode="Add",
                  ptx_key=ptx_key, ptx_code=ptx_code,
                  ptx_type=ptx_type, rec=None)


# ── MODIFICATIONS ──────────────────────────────────────────────────────────

@app.route("/modify", methods=["GET", "POST"])
def modifications():
    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render("enter_key.html", mode="Modify")
        ptx_key = PtxRecord.build_key(ptx_code, ptx_type)
        rec = ptx_svc.read_lock(ptx_key)
        if not rec:
            flash("Record is NOT on PTX file.", "error")
            ptx_svc.unlock()
            return render("enter_key.html", mode="Modify")
        return redirect(url_for("modify_data_entry",
                                ptx_key=ptx_key,
                                ptx_code=ptx_code,
                                ptx_type=ptx_type))
    return render("enter_key.html", mode="Modify")


@app.route("/modify/data", methods=["GET", "POST"])
def modify_data_entry():
    ptx_key  = request.args.get("ptx_key")  or request.form.get("ptx_key", "")
    ptx_code = int(request.args.get("ptx_code") or request.form.get("ptx_code", 0))
    ptx_type = int(request.args.get("ptx_type") or request.form.get("ptx_type", 0))
    if request.method == "POST":
        rec = _build_rec_from_form(request.form, ptx_key, ptx_code)
        if rec is None:
            ptx_svc.unlock()
            return redirect(url_for("main_menu"))
        if not ptx_svc.rewrite(rec):
            flash(f"Cannot rewrite record (status {ptx_svc.file_status}).", "error")
        else:
            flash("Record modified successfully.", "info")
        ptx_svc.unlock()
        return redirect(url_for("main_menu"))
    rec = ptx_svc.read_by_key(ptx_key)
    return render("data_entry.html", mode="Modify",
                  ptx_key=ptx_key, ptx_code=ptx_code,
                  ptx_type=ptx_type, rec=rec)


# ── DELETIONS ──────────────────────────────────────────────────────────────

@app.route("/delete", methods=["GET", "POST"])
def deletions():
    # Direct delete from list table (inline button)
    ptx_key_direct = request.form.get("ptx_key_direct")
    if ptx_key_direct:
        rec = ptx_svc.read_by_key(ptx_key_direct)
        if not rec:
            flash("Record not found.", "error")
            return redirect(url_for("main_menu"))
        return render("delete_confirm.html", rec=rec)

    if request.method == "POST":
        ptx_code = int(request.form.get("ptx_code", 0))
        ptx_type = int(request.form.get("ptx_type", 0))
        if not ptx_type:
            flash("Type cannot be zero.", "error")
            return render("enter_key.html", mode="Delete")
        ptx_key = PtxRecord.build_key(ptx_code, ptx_type)
        rec = ptx_svc.read_lock(ptx_key)
        if not rec:
            flash("Record is NOT on PTX file.", "error")
            ptx_svc.unlock()
            return render("enter_key.html", mode="Delete")
        return render("delete_confirm.html", rec=rec)
    return render("enter_key.html", mode="Delete")


@app.route("/delete/confirm", methods=["POST"])
def delete_confirm():
    ptx_key = request.form.get("ptx_key", "")
    confirm = request.form.get("confirm", "N")
    if confirm != "Y":
        ptx_svc.unlock()
        flash("Deletion cancelled.", "info")
        return redirect(url_for("main_menu"))
    ok = ptx_svc.delete(ptx_key)
    ptx_svc.unlock()
    if not ok:
        flash("Record cannot be deleted.", "error")
    else:
        flash("Record deleted successfully.", "info")
    return redirect(url_for("main_menu"))


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        get_conn()
        print("✓ Database connection established (PTX file open).")
    except Exception as e:
        print(f"✗ Cannot connect to database: {e}")
        exit(1)
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"✓ FM010 PTX Maintenance starting on http://localhost:{port}")
    app.run(debug=debug, port=port)
