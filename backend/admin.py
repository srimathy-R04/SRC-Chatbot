
import os
import sqlite3
import uuid
from pathlib import Path
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder="admin_templates",
    url_prefix="/admin",
)

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
KNOWLEDGE_BASE_DIR = PROJECT_DIR / "knowledge_base"
PENDING_DIR = BACKEND_DIR / "pending_uploads"
DATABASE_PATH = BACKEND_DIR / "admin_documents.db"

ALLOWED_EXTENSIONS = {".txt"}
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def initialize_database():
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT
            )
        """)


initialize_database()


def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def admin_configured():
    return all(
        os.getenv(key)
        for key in (
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD_HASH",
            "FLASK_SECRET_KEY",
        )
    )


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if not admin_configured():
        return (
            "Admin configuration is missing. Check your .env file.",
            503,
        )

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        expected_username = os.getenv("ADMIN_USERNAME", "")
        password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")

        if (
            username == expected_username
            and check_password_hash(password_hash, password)
        ):
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            return redirect(url_for("admin.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@admin_bp.route("/")
@admin_required
def dashboard():
    with get_db() as connection:
        documents = connection.execute("""
            SELECT id, original_name, status, uploaded_at
            FROM documents
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "dashboard.html",
        documents=documents,
    )


@admin_bp.route("/upload", methods=["POST"])
@admin_required
def upload_document():
    uploaded_file = request.files.get("document")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please choose a text file.", "error")
        return redirect(url_for("admin.dashboard"))

    original_name = secure_filename(uploaded_file.filename)

    if not original_name:
        flash("The filename is invalid.", "error")
        return redirect(url_for("admin.dashboard"))

    if Path(original_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        flash("Only .txt files are allowed in this version.", "error")
        return redirect(url_for("admin.dashboard"))

    content = uploaded_file.stream.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        flash("The file exceeds the 1 MB limit.", "error")
        return redirect(url_for("admin.dashboard"))

    if not content.strip():
        flash("The uploaded file is empty.", "error")
        return redirect(url_for("admin.dashboard"))

    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        flash("Please upload a UTF-8 encoded text file.", "error")
        return redirect(url_for("admin.dashboard"))

    if "\x00" in text_content:
        flash("The file contains invalid text.", "error")
        return redirect(url_for("admin.dashboard"))

    stored_name = f"{uuid.uuid4().hex}.txt"
    pending_path = PENDING_DIR / stored_name

    try:
        pending_path.write_text(text_content, encoding="utf-8")

        with get_db() as connection:
            connection.execute(
                """
                INSERT INTO documents
                    (original_name, stored_name, status)
                VALUES (?, ?, 'pending')
                """,
                (original_name, stored_name),
            )

    except Exception:
        pending_path.unlink(missing_ok=True)
        raise

    flash(
        "Document uploaded for review. It is not published yet.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/approve/<int:document_id>", methods=["POST"])
@admin_required
def approve_document(document_id):
    with get_db() as connection:
        document = connection.execute(
            """
            SELECT id, original_name, stored_name, status
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

        if document is None:
            flash("Document not found.", "error")
            return redirect(url_for("admin.dashboard"))

        if document["status"] != "pending":
            flash("This document has already been reviewed.", "error")
            return redirect(url_for("admin.dashboard"))

        pending_path = PENDING_DIR / document["stored_name"]

        if not pending_path.is_file():
            flash("The pending file could not be found.", "error")
            return redirect(url_for("admin.dashboard"))

        # Avoid overwriting existing knowledge-base files.
        base_name = Path(document["original_name"]).stem
        safe_stem = secure_filename(base_name) or "src_document"
        destination_name = f"{safe_stem}_{uuid.uuid4().hex[:8]}.txt"
        destination_path = KNOWLEDGE_BASE_DIR / destination_name

        # Publish a copy only after administrator approval.
        destination_path.write_text(
            pending_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        connection.execute(
            """
            UPDATE documents
            SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (document_id,),
        )

        pending_path.unlink(missing_ok=True)

    flash(
        "Document approved and copied to the knowledge base. "
        "Verify that your RAG code reads new files dynamically.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/reject/<int:document_id>", methods=["POST"])
@admin_required
def reject_document(document_id):
    with get_db() as connection:
        document = connection.execute(
            """
            SELECT id, stored_name, status
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

        if document is None:
            flash("Document not found.", "error")
            return redirect(url_for("admin.dashboard"))

        if document["status"] != "pending":
            flash("Only pending documents can be rejected.", "error")
            return redirect(url_for("admin.dashboard"))

        connection.execute(
            """
            UPDATE documents
            SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (document_id,),
        )

        (PENDING_DIR / document["stored_name"]).unlink(missing_ok=True)

    flash("Document rejected.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
