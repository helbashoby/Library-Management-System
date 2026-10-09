import os
from dotenv import load_dotenv

load_dotenv()
from flask import Flask, jsonify, render_template, request, redirect, url_for, session

from db import get_connection


app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

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
        "book_name": "b.book_name",
        "author_name": "b.author_name",
        "category": "c.category_name",
        "publisher": "p.publisher_name"
    }

    field = allowed_fields.get(search_by, "b.book_name")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT
                b.book_id,
                b.book_name,
                b.author_name,
                c.category_name AS category,
                p.publisher_name AS publisher,
                b.available_copy,
                b.shelf_loc
            FROM book b
            JOIN category c ON b.category_id = c.category_id
            JOIN publisher p ON b.publisher_id = p.publisher_id
            WHERE {field} LIKE %s
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
        issued_books = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(issued_books)

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "Could not load issued books.",
            "error": str(error)
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
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin-login")
def admin_login():
    return render_template("admin_login.html")


@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("admin_dashboard.html")


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