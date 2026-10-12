import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as library_app


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = library_app.app.test_client()
        database_guard = patch(
            "app.get_connection",
            side_effect=AssertionError("Test attempted an unmocked database connection"),
        )
        database_guard.start()
        self.addCleanup(database_guard.stop)

    def _fake_conn(self, rows=None):
        class FakeCursor:
            def __init__(self, rows):
                self.rows = rows or []
                self._index = 0
                self.statements = []
                self.lastrowid = 101
                self.rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params=None):
                self.statements.append((query, params))
                self._index = 0

            def fetchone(self):
                if not self.rows:
                    return None
                row = self.rows[0]
                self.rows = self.rows[1:]
                return row

            def fetchall(self):
                rows = list(self.rows)
                self.rows = []
                return rows

            def close(self):
                pass

        class FakeConnection:
            def __init__(self, rows):
                self.cursor_obj = FakeCursor(rows)

            def cursor(self, dictionary=False):
                return self.cursor_obj

            def start_transaction(self):
                pass

            def close(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                pass

        return FakeConnection(rows)

    def test_student_login_sets_session_for_string_id(self):
        fake_row = {
            "student_id": "PKD25IT004",
            "student_name": "Adithyan C",
            "department": "IT",
            "semester": 5,
            "phoneno": "9876543210",
        }
        with patch("app.get_connection", return_value=self._fake_conn([fake_row])):
            response = self.client.post(
                "/api/student/login",
                data={"student_id": "PKD25IT004", "student_name": "Adithyan C"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/student-dashboard")
        with self.client.session_transaction() as current_session:
            self.assertEqual(current_session["student_id"], "PKD25IT004")
            self.assertEqual(current_session["student_name"], "Adithyan C")

    def _assert_admin_login_sets_session(self, password_hash, password):
        fake_row = {
            "admin_id": "LIB123",
            "adm_name": "Library Admin",
            "password": password_hash,
        }
        with patch("app.get_connection", return_value=self._fake_conn([fake_row])):
            response = self.client.post(
                "/api/admin/login",
                data={"admin_id": "LIB123", "password": password},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/admin-dashboard")
        with self.client.session_transaction() as current_session:
            self.assertEqual(current_session["admin_id"], "LIB123")
            self.assertEqual(current_session["admin_name"], "Library Admin")
            self.assertNotIn("admin_phone_no", current_session)

    def test_admin_login_accepts_werkzeug_hash_and_sets_session(self):
        password = "correct-password"
        self._assert_admin_login_sets_session(generate_password_hash(password), password)

    @unittest.skipIf(library_app.bcrypt is None, "bcrypt dependency is not installed")
    def test_admin_login_accepts_bcrypt_hash_and_sets_session(self):
        password = "correct-password"
        password_hash = library_app.bcrypt.hashpw(
            password.encode("utf-8"), library_app.bcrypt.gensalt()
        ).decode("utf-8")
        self._assert_admin_login_sets_session(password_hash, password)

    def test_admin_login_rejects_incorrect_password(self):
        fake_row = {
            "admin_id": "LIB123",
            "adm_name": "Library Admin",
            "password": generate_password_hash("correct-password"),
        }
        with patch("app.get_connection", return_value=self._fake_conn([fake_row])):
            response = self.client.post(
                "/api/admin/login",
                data={"admin_id": "LIB123", "password": "wrong-password"},
            )

        self.assertEqual(response.status_code, 401)
        with self.client.session_transaction() as current_session:
            self.assertNotIn("admin_id", current_session)

    def test_admin_dashboard_requires_admin_session(self):
        response = self.client.get("/admin-dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/admin-login")

        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        admin_row = {
            "adm_name": "Library Admin",
            "phone_no": "9876543210",
        }
        with patch("app.get_connection", return_value=self._fake_conn([admin_row])):
            response = self.client.get("/admin-dashboard")
        self.assertEqual(response.status_code, 200)

    def test_admin_logout_preserves_student_session(self):
        with self.client.session_transaction() as current_session:
            current_session["student_id"] = "STU001"
            current_session["student_name"] = "Student"
            current_session["admin_id"] = "LIB123"
            current_session["admin_name"] = "Library Admin"
            current_session["admin_phone_no"] = "legacy-value"

        response = self.client.get("/admin-logout")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as current_session:
            self.assertNotIn("admin_id", current_session)
            self.assertNotIn("admin_name", current_session)
            self.assertNotIn("admin_phone_no", current_session)
            self.assertEqual(current_session["student_id"], "STU001")
            self.assertEqual(current_session["student_name"], "Student")

    def test_student_logout_preserves_admin_session(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"
            current_session["student_id"] = "STU001"
            current_session["student_name"] = "Student"

        response = self.client.get("/student-logout")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as current_session:
            self.assertNotIn("student_id", current_session)
            self.assertNotIn("student_name", current_session)
            self.assertEqual(current_session["admin_id"], "LIB123")

    def test_add_book_saves_all_authors_only_in_book_author(self):
        connection = self._fake_conn([
            {"category_id": 1},
            {"publisher_id": 2},
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/books",
                data={
                    "book_name": "Collaborative Algorithms",
                    "author_name": "Author One, Author Two, Author One",
                    "total_copy": "4",
                    "available_copy": "4",
                    "category_id": "1",
                    "publisher_id": "2",
                },
            )

        self.assertEqual(response.status_code, 201)
        book_insert, book_params = next(
            statement for statement in connection.cursor_obj.statements
            if statement[0].lstrip().upper().startswith("INSERT INTO BOOK")
        )
        self.assertNotIn("author_name", book_insert.lower())
        self.assertEqual(
            book_params,
            ("Collaborative Algorithms", 4, 4, None, 1, 2),
        )
        author_inserts = [
            statement for statement in connection.cursor_obj.statements
            if statement[0].lstrip().upper().startswith("INSERT INTO BOOK_AUTHOR")
        ]
        self.assertEqual(
            [statement[1] for statement in author_inserts],
            [(101, "Author One"), (101, "Author Two")],
        )

    def test_student_author_search_uses_book_author_links(self):
        connection = self._fake_conn([{
            "book_id": 7,
            "book_name": "Collaborative Algorithms",
            "author_name": "Author One, Author Two",
            "category": "Computer Science",
            "publisher": "Example Press",
            "available_copy": 2,
            "shelf_loc": "A-01",
        }])
        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/books/search?search_by=author_name&q=Author%20Two"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["author_name"], "Author One, Author Two")
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("ba2.author_name", query)
        self.assertIn("LEFT JOIN book_author ba2", query)
        self.assertNotIn("b.author_name", query)
        self.assertEqual(params, ("%Author Two%",))

    def test_admin_book_listing_aggregates_linked_authors(self):
        connection = self._fake_conn([{
            "book_id": 7,
            "book_name": "Collaborative Algorithms",
            "author_name": "Author One, Author Two",
            "available_copy": 2,
            "total_copy": 4,
            "shelf_loc": "A-01",
            "category_name": "Computer Science",
            "publisher_name": "Example Press",
        }])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get("/api/admin/books")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["author_name"], "Author One, Author Two")
        query = connection.cursor_obj.statements[0][0]
        self.assertIn("DISTINCT ba.author_name", query)
        self.assertIn("LEFT JOIN book_author ba", query)
        self.assertNotIn("b.author_name", query)


if __name__ == "__main__":
    unittest.main()
