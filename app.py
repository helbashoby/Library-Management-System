import os
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv

try:
    import bcrypt
except ImportError:
    bcrypt = None

load_dotenv()
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from mysql.connector.errors import IntegrityError
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
    return _parse_iso_date(value)


def _parse_iso_date(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return parsed if parsed.isoformat() == value else None


def _calculate_due_date(issue_date):
    return issue_date + timedelta(days=14)


def _calculate_issue_status(due_date, return_date, today=None):
    if return_date is not None:
        return "Returned (On Time)" if return_date <= due_date else "Returned (Overdue)"
    current_date = today or date.today()
    return "Issued" if current_date <= due_date else "Overdue"


def _add_issue_status(issues):
    for issue in issues:
        issue["status"] = _calculate_issue_status(
            issue["due_date"],
            issue["return_date"],
        )
    return issues


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
                i.return_date
            FROM issue i
            JOIN book b ON i.book_id = b.book_id
            WHERE i.student_id = %s
            ORDER BY i.issue_date DESC
        """

        cursor.execute(query, (student_id,))
        issued_books = _add_issue_status(cursor.fetchall())
        for issued_book in issued_books:
            for field in ("issue_date", "due_date", "return_date"):
                if issued_book[field] is not None:
                    issued_book[field] = issued_book[field].isoformat()

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
        return jsonify({
            "categories": categories,
            "publishers": publishers,
        })
    except Exception:
        return jsonify({"status": "error", "message": "Could not load book options."}), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/admin/students")
@admin_required
def admin_students():
    student_id = (request.args.get("student_id") or "").strip()
    if len(student_id) > 15:
        return jsonify({
            "status": "error",
            "message": "Student ID must be 15 characters or fewer."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        if student_id:
            cursor.execute(
                """
                SELECT student_id, student_name, department, semester, phoneno
                FROM student
                WHERE student_id = %s
                ORDER BY student_id
                """,
                (student_id,),
            )
        else:
            cursor.execute(
                """
                SELECT student_id, student_name, department, semester, phoneno
                FROM student
                ORDER BY student_id
                """
            )
        return jsonify(cursor.fetchall())
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Could not load student records."
        }), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/admin/students", methods=["POST"])
@admin_required
def add_student():
    student_id = (request.form.get("student_id") or "").strip()
    student_name = (request.form.get("student_name") or "").strip()
    department = (request.form.get("department") or "").strip()
    semester_value = (request.form.get("semester") or "").strip()
    phone_number = (request.form.get("phoneno") or "").strip() or None

    try:
        semester = int(semester_value)
    except (TypeError, ValueError):
        semester = None

    if (
        not student_id
        or len(student_id) > 15
        or not student_name
        or len(student_name) > 100
        or not department
        or len(department) > 80
        or semester is None
        or not 1 <= semester <= 12
        or (phone_number is not None and len(phone_number) > 15)
    ):
        return jsonify({
            "status": "error",
            "message": "Enter a valid student ID, name, department, semester (1–12), and phone number."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT student_id FROM student WHERE student_id = %s",
            (student_id,),
        )
        if cursor.fetchone() is not None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "A student with this ID already exists."
            }), 409

        cursor.execute(
            """
            INSERT INTO student
                (student_id, student_name, department, semester, phoneno)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (student_id, student_name, department, semester, phone_number),
        )
        conn.commit()
        return jsonify({
            "status": "success",
            "message": "Student added successfully."
        }), 201
    except IntegrityError as error:
        _rollback(conn)
        if error.errno == 1062:
            return jsonify({
                "status": "error",
                "message": "A student with this ID already exists."
            }), 409
        return jsonify({
            "status": "error",
            "message": "Could not add the student."
        }), 500
    except Exception:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": "Could not add the student."
        }), 500
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
        search_by = request.args.get("search_by", "").strip()
        keyword = request.args.get("q", "").strip()
        search_fields = {
            "book_name": "b.book_name",
            "author_name": "ba.author_name",
            "category": "c.category_name",
            "publisher": "p.publisher_name",
        }
        if search_by and search_by not in search_fields:
            return jsonify({
                "status": "error",
                "message": "Choose a valid book search field."
            }), 400

        filters = []
        params = []
        if keyword:
            field = search_fields.get(search_by, "b.book_name")
            if search_by == "author_name":
                filters.append(
                    """EXISTS (
                        SELECT 1
                        FROM book_author search_author
                        WHERE search_author.book_id = b.book_id
                          AND search_author.author_name LIKE %s
                    )"""
                )
            else:
                filters.append(f"{field} LIKE %s")
            params.append(f"%{keyword}%")
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        cursor.execute(
            f"""
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
                c.category_id,
                c.category_name,
                p.publisher_id,
                p.publisher_name
            FROM book b
            LEFT JOIN book_author ba ON ba.book_id = b.book_id
            JOIN category c ON c.category_id = b.category_id
            JOIN publisher p ON p.publisher_id = b.publisher_id
            {where_clause}
            GROUP BY
                b.book_id,
                b.book_name,
                b.available_copy,
                b.total_copy,
                b.shelf_loc,
                c.category_id,
                c.category_name,
                p.publisher_id,
                p.publisher_name
            ORDER BY b.book_id
            """,
            tuple(params),
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
    search_by = (request.args.get("search_by") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    search_fields = {
        "student_id": "i.student_id",
        "book_id": "i.book_id",
        "issue_date": "i.issue_date",
        "due_date": "i.due_date",
        "status": None,
    }

    if search_by and search_by not in search_fields:
        return jsonify({
            "status": "error",
            "message": "Choose a valid issue-record search field."
        }), 400
    if keyword and not search_by:
        return jsonify({
            "status": "error",
            "message": "Choose a search field before entering a keyword."
        }), 400

    search_value = None
    if keyword and search_by in {"issue_date", "due_date"}:
        search_value = _parse_iso_date(keyword)
        if search_value is None:
            return jsonify({
                "status": "error",
                "message": "Enter a valid date in YYYY-MM-DD format."
            }), 400
    elif keyword and search_by == "book_id":
        search_value = _positive_integer(keyword)
        if search_value is None:
            return jsonify({
                "status": "error",
                "message": "Select a valid book suggestion."
            }), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        if search_by == "student_id" and len(keyword) > 15:
            return jsonify({
                "status": "error",
                "message": "Student ID must be 15 characters or fewer."
            }), 400
        filters = []
        params = []
        if keyword and search_by in {"student_id", "book_id", "issue_date", "due_date"}:
            filters.append(f"{search_fields[search_by]} = %s")
            params.append(
                search_value
                if search_by in {"book_id", "issue_date", "due_date"}
                else keyword
            )
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        cursor.execute(
            f"""
            SELECT i.issue_id, i.student_id, s.student_name, s.department,
                   b.book_name, a.adm_name AS admin_name,
                   i.issue_date, i.due_date, i.return_date
            FROM issue i
            JOIN student s ON s.student_id = i.student_id
            JOIN book b ON b.book_id = i.book_id
            JOIN admin a ON a.admin_id = i.admin_id
            {where_clause}
            ORDER BY i.issue_id DESC
            """,
            tuple(params),
        )
        issues = _add_issue_status(cursor.fetchall())
        if keyword and search_by == "status":
            normalized_keyword = keyword.casefold()
            issues = [
                issue for issue in issues
                if normalized_keyword in issue["status"].casefold()
            ]
        for issue in issues:
            for field in ("issue_date", "due_date", "return_date"):
                if issue[field] is not None:
                    issue[field] = issue[field].isoformat()
        return jsonify(issues)
    except Exception:
        return jsonify({"status": "error", "message": "Could not load issue records."}), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/admin/issues/suggestions")
@admin_required
def admin_issue_suggestions():
    keyword = (request.args.get("q") or "").strip()
    search_type = (request.args.get("type") or "book").strip().lower()
    if len(keyword) > 100:
        return jsonify({
            "status": "error",
            "message": "Search text must be 100 characters or fewer."
        }), 400
    if search_type not in {"book", "student", "category", "publisher", "return_issue"}:
        return jsonify({
            "status": "error",
            "message": "Choose a valid autocomplete type."
        }), 400
    if not keyword:
        return jsonify([])

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        if search_type == "book":
            cursor.execute(
                """
                SELECT 'Book' AS suggestion_type,
                       CAST(book_id AS CHAR) AS suggestion_value,
                       book_name AS suggestion_label,
                       CAST(book_id AS CHAR) AS suggestion_detail,
                       available_copy
                FROM book
                WHERE LEFT(LOWER(book_name), CHAR_LENGTH(%s)) = LOWER(%s)
                   OR LOWER(LEFT(CAST(book_id AS CHAR), CHAR_LENGTH(%s))) = LOWER(%s)
                ORDER BY book_name
                """,
                (keyword, keyword, keyword, keyword),
            )
        elif search_type == "student":
            cursor.execute(
                """
                SELECT 'Student' AS suggestion_type,
                       student_id AS suggestion_value,
                       student_name AS suggestion_label,
                       student_id AS suggestion_detail
                FROM student
                WHERE LEFT(LOWER(student_name), CHAR_LENGTH(%s)) = LOWER(%s)
                   OR LEFT(LOWER(student_id), CHAR_LENGTH(%s)) = LOWER(%s)
                ORDER BY student_name, student_id
                """,
                (keyword, keyword, keyword, keyword),
            )
        elif search_type == "category":
            cursor.execute(
                """
                SELECT 'Category' AS suggestion_type,
                       CAST(category_id AS CHAR) AS suggestion_value,
                       category_name AS suggestion_label,
                       CAST(category_id AS CHAR) AS suggestion_detail
                FROM category
                WHERE LEFT(LOWER(category_name), CHAR_LENGTH(%s)) = LOWER(%s)
                ORDER BY category_name
                """,
                (keyword, keyword),
            )
        elif search_type == "publisher":
            cursor.execute(
                """
                SELECT 'Publisher' AS suggestion_type,
                       CAST(publisher_id AS CHAR) AS suggestion_value,
                       publisher_name AS suggestion_label,
                       CAST(publisher_id AS CHAR) AS suggestion_detail
                FROM publisher
                WHERE LEFT(LOWER(publisher_name), CHAR_LENGTH(%s)) = LOWER(%s)
                ORDER BY publisher_name
                """,
                (keyword, keyword),
            )
        else:
            cursor.execute(
                """
                SELECT 'Issue' AS suggestion_type,
                       CAST(i.issue_id AS CHAR) AS suggestion_value,
                       CONCAT('Issue #', i.issue_id) AS suggestion_label,
                       CONCAT(b.book_name, ' - Student ', i.student_id)
                           AS suggestion_detail
                FROM issue i
                JOIN book b ON b.book_id = i.book_id
                WHERE i.return_date IS NULL
                  AND (
                      LEFT(CAST(i.issue_id AS CHAR), CHAR_LENGTH(%s)) = %s
                      OR LEFT(LOWER(b.book_name), CHAR_LENGTH(%s)) = LOWER(%s)
                      OR LEFT(LOWER(i.student_id), CHAR_LENGTH(%s)) = LOWER(%s)
                  )
                ORDER BY i.issue_id DESC
                """,
                (keyword, keyword, keyword, keyword, keyword, keyword),
            )
        return jsonify(cursor.fetchall())
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Could not load issue-record suggestions."
        }), 500
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


@app.route("/api/books/<int:book_id>", methods=["PUT"])
@admin_required
def update_book(book_id):
    book_name = (request.form.get("book_name") or "").strip()
    author_input = (request.form.get("author_name") or "").strip()
    authors = list(dict.fromkeys(
        name.strip() for name in author_input.split(",") if name.strip()
    ))
    shelf_loc = (request.form.get("shelf_loc") or "").strip() or None
    total_copy = _nonnegative_integer(request.form.get("total_copy"))
    available_copy = _nonnegative_integer(request.form.get("available_copy"))
    category_id = _positive_integer(request.form.get("category_id"))
    publisher_id = _positive_integer(request.form.get("publisher_id"))

    if (
        not book_name
        or len(book_name) > 200
        or not authors
        or any(len(author) > 120 for author in authors)
        or (shelf_loc is not None and len(shelf_loc) > 30)
        or total_copy is None
        or available_copy is None
        or available_copy > total_copy
        or category_id is None
        or publisher_id is None
    ):
        return jsonify({
            "status": "error",
            "message": "Enter valid book details and copy counts."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT book_id FROM book WHERE book_id = %s FOR UPDATE",
            (book_id,),
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Book was not found."
            }), 404

        cursor.execute(
            """
            SELECT COUNT(*) AS issued_count
            FROM issue
            WHERE book_id = %s AND return_date IS NULL
            """,
            (book_id,),
        )
        issued_count = cursor.fetchone()["issued_count"]
        if available_copy + issued_count > total_copy:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": (
                    "Total copies and available copies cannot be less than "
                    "the number of copies currently issued."
                )
            }), 409

        cursor.execute(
            "SELECT category_id FROM category WHERE category_id = %s",
            (category_id,),
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Select a valid category."
            }), 400

        cursor.execute(
            "SELECT publisher_id FROM publisher WHERE publisher_id = %s",
            (publisher_id,),
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Select a valid publisher."
            }), 400

        cursor.execute(
            """
            UPDATE book
            SET book_name = %s, available_copy = %s, total_copy = %s,
                shelf_loc = %s, category_id = %s, publisher_id = %s
            WHERE book_id = %s
            """,
            (
                book_name, available_copy, total_copy, shelf_loc,
                category_id, publisher_id, book_id,
            ),
        )
        cursor.execute("DELETE FROM book_author WHERE book_id = %s", (book_id,))
        for author in authors:
            cursor.execute(
                """
                INSERT INTO book_author (book_id, author_name)
                VALUES (%s, %s)
                """,
                (book_id, author),
            )
        conn.commit()
        return jsonify({
            "status": "success",
            "message": "Book updated successfully."
        })
    except IntegrityError:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": "Book details conflict with an existing database record."
        }), 409
    except Exception:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": "Could not update the book."
        }), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
@admin_required
def delete_book(book_id):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT book_id FROM book WHERE book_id = %s FOR UPDATE",
            (book_id,),
        )
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Book was not found."
            }), 404

        cursor.execute(
            "SELECT COUNT(*) AS issue_count FROM issue WHERE book_id = %s",
            (book_id,),
        )
        if cursor.fetchone()["issue_count"] > 0:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": (
                    "This book cannot be deleted because it has issue history."
                )
            }), 409

        cursor.execute("DELETE FROM book WHERE book_id = %s", (book_id,))
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": "Book was not found."
            }), 404
        conn.commit()
        return jsonify({
            "status": "success",
            "message": "Book deleted successfully."
        })
    except IntegrityError:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": (
                "This book cannot be deleted because related records still exist."
            )
        }), 409
    except Exception:
        _rollback(conn)
        return jsonify({
            "status": "error",
            "message": "Could not delete the book."
        }), 500
    finally:
        _close_db_resources(cursor, conn)


@app.route("/api/issues", methods=["POST"])
@admin_required
def issue_book():
    student_id = (request.form.get("student_id") or "").strip()
    book_id = _positive_integer(request.form.get("book_id"))
    issue_date = _form_date("issue_date")
    due_date = _calculate_due_date(issue_date) if issue_date is not None else None

    if (not student_id or len(student_id) > 15 or book_id is None
            or issue_date is None or issue_date > date.today()):
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
            return jsonify({
                "status": "error",
                "message": "This book is currently not available."
            }), 409

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
            return jsonify({
                "status": "error",
                "message": "This book is currently not available."
            }), 409
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