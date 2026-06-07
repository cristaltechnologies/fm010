# FM010 — PTX Parametric File Maintenance
## Converted from COBOL FM010.CBL + 13 copy files

---

## Files Generated

| File | COBOL Source | Purpose |
|---|---|---|
| `schema.sql` | selptx.cp / selmfa.cp / recptx.cp / recmfa.cp | PostgreSQL tables replacing ISAM files |
| `db/connection.py` | selmfa.cp / selptx.cp | DB connection (replaces OPEN/CLOSE) |
| `models/ptx.py` | recptx.cp | PTX record + all REDEFINES as properties |
| `models/mfa.py` | recmfa.cp | MFA record + REDEFINES as properties |
| `services/ptx_service.py` | selptx.cp | PTX ISAM I/O → SQL |
| `services/mfa_service.py` | selmfa.cp | MFA ISAM I/O → SQL |
| `services/gan_service.py` | ganin.cp / ganinws.cp | GAN validation logic |
| `fm010_app.py` | fm010.cbl / mainpd.cp / mfal3.cp / stoprun.cp / procdiv.cp | Main Flask web app |

---

## COBOL → Python Mapping

| COBOL | Python |
|---|---|
| `SCREEN SECTION` | Flask HTML templates (green-on-black terminal style) |
| `DISPLAY MAIN-MENU / ACCEPT` | `GET /` route |
| `PERFORM ADDITIONS` | `POST /add` → `GET /add/data` → `POST /add/data` |
| `PERFORM MODIFICATIONS` | `POST /modify` → `GET /modify/data` → `POST /modify/data` |
| `PERFORM DELETIONS` | `POST /delete` → `POST /delete/confirm` |
| `READ PTX INVALID KEY` | `PtxService.read_by_key()` |
| `READ PTX RECORD LOCK` | `PtxService.read_lock()` (SELECT FOR UPDATE) |
| `WRITE PTX-REC INVALID KEY` | `PtxService.write()` |
| `REWRITE PTX-REC INVALID KEY` | `PtxService.rewrite()` |
| `DELETE PTX RECORD INVALID KEY` | `PtxService.delete()` |
| `UNLOCK PTX RECORD` | `PtxService.unlock()` (commit releases lock) |
| `LOCK MODE IS MANUAL` | PostgreSQL `SELECT FOR UPDATE NOWAIT` |
| `PERFORM CHECK-GANIN` | `GanValidator.validate()` |
| `PERFORM SHIFTING` | Built into `GanValidator.validate()` |
| `PERFORM DISPLAY-MFAL3` | MFA lookup in `_build_rec_from_form()` |
| `PERFORM GET-SYS-DATE` | `get_sys_date()` |
| `PERFORM FIND-CHOICE-LIT` | `choice_lit()` |
| `PROCEDURE DIVISION USING ...` | Flask `session` / function parameters |
| `DECLARATIVES` / error sections | `psycopg2` exception handling |
| `STOP RUN` (stoprun.cp) | `GET /exit` |
| ISAM `fl/ptx` | PostgreSQL `ptx` table |
| ISAM `fl/mfa` | PostgreSQL `mfa` table |
| `PTX-OTHER-DATA REDEFINES` | `@property` accessors in `PtxRecord` |
| `MFA-PASSIVE-DATA REDEFINES` | Individual columns in `mfa` table |

---

## Setup

### 1. Install Python dependencies
```bash
pip install flask psycopg2-binary python-dotenv
```

### 2. Create the database tables
```bash
psql -U postgres -d mydb -f schema.sql
```

### 3. Configure connection — create `.env`
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=postgres
DB_PASSWORD=yourpassword
SECRET_KEY=change-me-in-production
```

### 4. Run the application
```bash
python fm010_app.py
```
Then open **http://localhost:5000** in your browser.

---

## Architecture Notes

- The **green-on-black terminal UI** intentionally mimics the original COBOL screen look
- All ISAM locking (`LOCK MODE IS MANUAL`) is replicated using PostgreSQL `SELECT FOR UPDATE NOWAIT`
- `PTX-OTHER-DATA` (700-byte blob) is stored as `CHAR(700)` in PostgreSQL — Python properties slice it exactly as COBOL `REDEFINES` did, so all sub-record types (TYPE-DATA, GAN-DATA, CC-DATA, etc.) remain compatible
- The `SU-FLAG` / `AUTHORITY-LEVEL` from `linkage.cp` should be wired to your authentication layer (session-based auth in Flask)
- `INFOTECH` guard in `GET-SYS-DATE` (mainpd.cp) is replaced by the DB connection check at startup
