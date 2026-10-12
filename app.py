import os
from datetime import date, datetime
from functools import wraps

from dotenv import load_dotenv

try:
    import bcrypt
except ImportError:
    bcrypt = None

load_dotenv()
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

from db import get_connection


app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({
                    "status": "error",
                    "message": "Administrator login is required."
                }), 401
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)

    return wrapped


def verify_admin_password(stored_hash, password):
    if not stored_hash:
        return False

    try:
        if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
            if bcrypt is None:
                return False
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        if stored_hash.startswith(("scrypt:", "pbkdf2:")):
            return check_password_hash(stored_hash, password)
    except (TypeError, ValueError):
        return False

    return False


def _positive_integer(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_integer(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _form_date(field_name):
    value = (request.form.get(field_name) or "").strip()
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _close_db_resources(cursor, conn):
    if cursor is not None:
        try:
            cursor.close()
        except Exception:
            pass
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _rollback(conn):
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/student-login")
def student_login():
    return render_template("student_login.html")


@app.route("/api/student/login", methods=["POST"])
def student_login_api():
    student_id = request.form.get("student_id")
    student_name = request.form.get("student_name")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT student_id, student_name, department, semester, phoneno
            FROM student
            WHERE student_id = %s AND student_name = %s
        """

        cursor.execute(query, (student_id, student_name))
        student = cursor.fetchone()

        cursor.close()
        conn.close()

        if student:
            session["student_id"] = student["student_id"]
            session["student_name"] = student["student_name"]
            return redirect(url_for("student_dashboard"))

        return "Invalid Student ID or Student Name", 401

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "Student login failed.",
            "error": str(error)
        }), 500


@app.route("/api/books/search")
def search_books():
    search_by = request.args.get("search_by", "book_name")
    keyword = request.args.get("q", "").strip()
    allowed_fields = {
        "book_name": "b2.book_name",
        "author_name": "ba2.author_name",
        "category": "c2.category_name",
        "publisher": "p2.publisher_name"
    }

    field = allowed_fields.get(search_by, "b2.book_name")


    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"""
            SELECT
                b.book_id,
                b.book_name,
                GROUP_CONCAT(
                    DISTINCT ba.author_name
                    ORDER BY ba.author_name
                    SEPARATOR ', '
                ) AS author_name,
                c.category_name AS category,
                p.publisher_name AS publisher,
                b.available_copy,
                b.shelf_loc
            FROM book b
            LEFT JOIN book_author ba ON ba.book_id = b.book_id
            JOIN category c ON b.category_id = c.category_id
            JOIN publisher p ON b.publisher_id = p.publisher_id
            WHERE b.book_id IN (
                SELECT DISTINCT b2.book_id
                FROM book b2
                LEFT JOIN book_author ba2
                    ON ba2.book_id = b2.book_id
                JOIN category c2
                    ON b2.category_id = c2.category_id
                JOIN publisher p2
                    ON b2.publisher_id = p2.publisher_id
                WHERE {field} LIKE %s
            )
            GROUP BY
                b.book_id,
                b.book_name,
                c.category_name,
                p.publisher_name,
                b.available_copy,
                b.shelf_loc
            ORDER BY b.book_id
        """


        cursor.execute(query, (f"%{keyword}%",))
        books = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(books)

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "Book search failed.",
            "error": str(error)
        }), 500


@app.route("/api/student/issued-books")
def student_issued_books():
    student_id = session.get("student_id")

    if not student_id:
        return jsonify({
            "status": "error",
            "message": "Student is not logged in."
        }), 401

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT
                i.issue_id,
                b.book_name,
                i.issue_date,
                i.due_date,
                i.return_date,
                CASE
                    WHEN i.return_date IS NULL THEN 'Issued'
                    ELSE 'Returned'
                END AS status
            FROM issue i
            JOIN book b ON i.book_id = b.book_id
            WHERE i.student_id = %s
            ORDER BY i.issue_date DESC
        """

        cursor.execute(query, (student_id,))
        issued_books = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(issued_books)

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Could not load issued books."
        }), 500



@app.route("/student-dashboard")
def student_dashboard():
    if "student_id" not in session:
        return redirect(url_for("student_login"))

    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name")
    )


@app.route("/student-logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_name", None)
    return redirect(url_for("home"))


@app.route("/admin-login")
def admin_login():
    return render_template("admin_login.html")


@app.route("/api/admin/login", methods=["POST"])
def admin_login_api():
    admin_id = (request.form.get("admin_id") or "").strip()
    password = request.form.get("password") or ""

    if not admin_id or not password:
        return "Invalid Admin ID or Password", 401

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT admin_id, adm_name, password
            FROM admin
            WHERE admin_id = %s
        """

        cursor.execute(query, (admin_id,))
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin and verify_admin_password(admin["password"], password):
            session["admin_id"] = admin["admin_id"]
            session["admin_name"] = admin["adm_name"]
            return redirect(url_for("admin_dashboard"))

        return "Invalid Admin ID or Password", 401

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Admin login failed."
        }), 500


@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    session.pop("admin_phone_no", None)
    return redirect(url_for("home"))


@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT adm_name, phone_no FROM admin WHERE admin_id = %s",
            (session["admin_id"],),
        )
        admin = cursor.fetchone()
        if admin is None:
            session.pop("admin_id", None)
            session.pop("admin_name", None)
            return redirect(url_for("admin_login"))

        session["admin_name"] = admin["adm_name"]
        return render_template(
            "admin_dashboard.html",
            admin_name=admin["adm_name"],
            admin_phone=admin["phone_no"],
        )
    except Exception:
        return "Could not load the admin dashboard.", 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/admin/book-options")
@admin_required
def admin_book_options():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.execute("SELECT publisher_id, publisher_name FROM publisher ORDER BY publisher_name")
        publishers = cursor.fetchall()
        cursor.execute("SELECT student_id, student_name FROM student ORDER BY student_name")
        students = cursor.fetchall()
        return jsonify({
            "categories": categories,
            "publishers": publishers,
            "students": students,
        })
    except Exception:
        return jsonify({"status": "error", "message": "Could not load book options."}), 500
    finally:
        _close_db_resources(cursor, conn)



@app.route("/api/admin/books")
@admin_required
def admin_books():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                b.book_id,
                b.book_name,
                GROUP_CONCAT(
                    DISTINCT ba.author_name
                    ORDER BY ba.author_name
                    SEPARATOR ', '
                ) AS author_name,
                b.available_copy,
                b.total_copy,
                b.shelf_loc,
                c.category_name,
                p.publisher_name
            FROM book b
            LEFT JOIN book_author ba ON ba.book_id = b.book_id
            JOIN category c ON c.category_id = b.category_id
            JOIN publisher p ON p.publisher_id = b.publisher_id
            GROUP BY
                b.book_id,
                b.book_name,
                b.available_copy,
                b.total_copy,
                b.shelf_loc,
                c.category_name,
                p.publisher_name
            ORDER BY b.book_id
            """
        )
        return jsonify(cursor.fetchall())
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Could not load books."
        }), 500
    finally:
        _close_db_resources(cursor, conn)
@app.route("/api/admin/issues")
@admin_required
def admin_issues():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT i.issue_id, i.student_id, s.student_name, s.department,
                   b.book_name, a.adm_name AS admin_name,
                   i.issue_date, i.due_date, i.return_date,
                   CASE WHEN i.return_date IS NULL THEN 'Issued' ELSE 'Returned' END AS status
            FROM issue i
            JOIN student s ON s.student_id = i.student_id
            JOIN book b ON b.book_id = i.book_id
            JOIN admin a ON a.admin_id = i.admin_id
            ORDER BY i.issue_id DESC
            """
        )
        issues = cursor.fetchall()
        for issue in issues:
            for field in ("issue_date", "due_date", "return_date"):
                if issue[field] is not None:
                    issue[field] = issue[field].isoformat()
        return jsonify(issues)
    except Exception:
        return jsonify({"status": "error", "message": "Could not load issue records."}), 500
    finally:
        _close_db_resources(cursor, conn)
@app.route("/api/books", methods=["POST"])
@admin_required
def add_book():
    book_name = (request.form.get("book_name") or "").strip()
    author_input = (request.form.get("author_name") or "").strip()
    authors = list(dict.fromkeys(
        name.strip() for name in author_input.split(",") if name.strip()
    ))

    shelf_loc = (request.form.get("shelf_loc") or "").strip() or None
    total_copy = _positive_integer(request.form.get("total_copy"))
    available_copy = _nonnegative_integer(request.form.get("available_copy"))
    category_id = _positive_integer(request.form.get("category_id"))
    publisher_id = _positive_integer(request.form.get("publisher_id"))

    if (
        not book_name
        or len(book_name) > 200
        or not authors
        or any(len(name) > 120 for name in authors)
        or (shelf_loc is not None and len(shelf_loc) > 30)
        or total_copy is None
        or available_copy is None
        or available_copy > total_copy
        or category_id is None
        or publisher_id is None
    ):
        return jsonify({
            "status": "error",
            "message": "Enter valid book details, author names, and copy counts."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT category_id FROM category WHERE category_id = %s",
            (category_id,)
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Select a valid category."
            }), 400

        cursor.execute(
            "SELECT publisher_id FROM publisher WHERE publisher_id = %s",
            (publisher_id,)
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Select a valid publisher."
            }), 400

        cursor.execute(
            """
            INSERT INTO book
                (book_name, available_copy, total_copy, shelf_loc,
                 category_id, publisher_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                book_name, available_copy, total_copy, shelf_loc,
                category_id, publisher_id
            )
        )

        new_book_id = cursor.lastrowid

        for author in authors:
            cursor.execute(
                """
                INSERT INTO book_author (book_id, author_name)
                VALUES (%s, %s)
                """,
                (new_book_id, author)
            )

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Book added successfully."
        }), 201

    except Exception:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": "Could not add the book."
        }), 500

    finally:
        _close_db_resources(cursor, conn)
@app.route("/api/issues", methods=["POST"])
@admin_required
def issue_book():
    student_id = (request.form.get("student_id") or "").strip()
    book_id = _positive_integer(request.form.get("book_id"))
    issue_date = _form_date("issue_date")
    due_date = _form_date("due_date")

    if (not student_id or len(student_id) > 15 or book_id is None
            or issue_date is None or due_date is None
            or issue_date > date.today() or due_date < issue_date):
        return jsonify({"status": "error", "message": "Enter valid student, book, and issue dates."}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id FROM student WHERE student_id = %s", (student_id,))
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({"status": "error", "message": "Select a valid student."}), 400

        cursor.execute(
            "SELECT book_id, available_copy FROM book WHERE book_id = %s FOR UPDATE",
            (book_id,),
        )
        book = cursor.fetchone()
        if book is None:
            conn.rollback()
            return jsonify({"status": "error", "message": "Select a valid book."}), 400
        if book["available_copy"] <= 0:
            conn.rollback()
            return jsonify({"status": "error", "message": "No copies are currently available."}), 409

        cursor.execute(
            """
            INSERT INTO issue (issue_date, due_date, return_date, student_id, admin_id, book_id)
            VALUES (%s, %s, NULL, %s, %s, %s)
            """,
            (issue_date, due_date, student_id, session["admin_id"], book_id),
        )
        cursor.execute(
            "UPDATE book SET available_copy = available_copy - 1 WHERE book_id = %s AND available_copy > 0",
            (book_id,),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({"status": "error", "message": "No copies are currently available."}), 409
        conn.commit()
        return jsonify({"status": "success", "message": "Book issued successfully."}), 201
    except Exception:
        _rollback(conn)
        return jsonify({"status": "error", "message": "Could not issue the book."}), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/issues/return", methods=["POST"])
@admin_required
def return_book():
    issue_id = _positive_integer(request.form.get("issue_id"))
    return_date = _form_date("return_date")
    if issue_id is None or return_date is None or return_date > date.today():
        return jsonify({"status": "error", "message": "Enter a valid issue and return date."}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT issue_id, book_id, issue_date, return_date FROM issue WHERE issue_id = %s FOR UPDATE",
            (issue_id,),
        )
        issue = cursor.fetchone()
        if issue is None:
            conn.rollback()
            return jsonify({"status": "error", "message": "Issue record was not found."}), 404
        if issue["return_date"] is not None:
            conn.rollback()
            return jsonify({"status": "error", "message": "This book has already been returned."}), 409
        if return_date < issue["issue_date"]:
            conn.rollback()
            return jsonify({"status": "error", "message": "Return date cannot precede the issue date."}), 400

        cursor.execute(
            "UPDATE issue SET return_date = %s WHERE issue_id = %s AND return_date IS NULL",
            (return_date, issue_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({"status": "error", "message": "This book has already been returned."}), 409
        cursor.execute(
            "UPDATE book SET available_copy = available_copy + 1 WHERE book_id = %s",
            (issue["book_id"],),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({"status": "error", "message": "Book inventory could not be updated."}), 409
        conn.commit()
        return jsonify({"status": "success", "message": "Book return recorded successfully."})
    except Exception:
        _rollback(conn)
        return jsonify({"status": "error", "message": "Could not record the book return."}), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/test-db")
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Flask connected to MySQL successfully.",
            "database": db_name
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "Could not connect to MySQL.",
            "error": str(error)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)