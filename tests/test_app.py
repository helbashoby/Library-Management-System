import unittest
from datetime import date, timedelta
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

    def _transaction_fake_conn(self, query_rows):
        class FakeCursor:
            def __init__(self, query_rows):
                self.query_rows = iter(query_rows)
                self.rows = []
                self.statements = []
                self.rowcount = 1

            def execute(self, query, params=None):
                self.statements.append((query, params))
                self.rows = list(next(self.query_rows, []))

            def fetchone(self):
                return self.rows.pop(0) if self.rows else None

            def fetchall(self):
                rows, self.rows = self.rows, []
                return rows

            def close(self):
                pass

        class FakeConnection:
            def __init__(self, query_rows):
                self.cursor_obj = FakeCursor(query_rows)
                self.committed = False
                self.rolled_back = False

            def cursor(self, dictionary=False):
                return self.cursor_obj

            def start_transaction(self):
                pass

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

            def close(self):
                pass

        return FakeConnection(query_rows)

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
        self.assertEqual(response.json[0]["available_copy"], 2)

    def test_update_book_replaces_authors_and_preserves_selected_database_ids(self):
        connection = self._transaction_fake_conn([
            [{"book_id": 7}],
            [{"issued_count": 2}],
            [{"category_id": 3}],
            [{"publisher_id": 4}],
            [],
            [],
            [],
            [],
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.put(
                "/api/books/7",
                data={
                    "book_name": "Updated Algorithms",
                    "author_name": "Author One, Author Two, Author One",
                    "total_copy": "5",
                    "available_copy": "3",
                    "shelf_loc": "B-12",
                    "category_id": "3",
                    "publisher_id": "4",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(connection.committed)
        statements = connection.cursor_obj.statements
        update_statement = next(
            statement for statement in statements
            if statement[0].lstrip().upper().startswith("UPDATE BOOK")
        )
        self.assertEqual(
            update_statement[1],
            ("Updated Algorithms", 3, 5, "B-12", 3, 4, 7),
        )
        author_inserts = [
            statement for statement in statements
            if statement[0].lstrip().upper().startswith("INSERT INTO BOOK_AUTHOR")
        ]
        self.assertEqual(
            [statement[1] for statement in author_inserts],
            [(7, "Author One"), (7, "Author Two")],
        )

    def test_update_book_rejects_invalid_copy_counts(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        response = self.client.put(
            "/api/books/7",
            data={
                "book_name": "Updated Algorithms",
                "author_name": "Author One",
                "total_copy": "-1",
                "available_copy": "0",
                "category_id": "3",
                "publisher_id": "4",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid book details", response.json["message"])

    def test_update_book_rejects_unknown_book_id(self):
        connection = self._transaction_fake_conn([[]])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.put(
                "/api/books/999",
                data={
                    "book_name": "Updated Algorithms",
                    "author_name": "Author One",
                    "total_copy": "5",
                    "available_copy": "5",
                    "category_id": "3",
                    "publisher_id": "4",
                },
            )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any(
            query.lstrip().upper().startswith("UPDATE BOOK")
            for query, _ in connection.cursor_obj.statements
        ))

    def test_update_book_cannot_reduce_stock_below_issued_copies(self):
        connection = self._transaction_fake_conn([
            [{"book_id": 7}],
            [{"issued_count": 2}],
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.put(
                "/api/books/7",
                data={
                    "book_name": "Updated Algorithms",
                    "author_name": "Author One",
                    "total_copy": "5",
                    "available_copy": "4",
                    "category_id": "3",
                    "publisher_id": "4",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any(
            query.lstrip().upper().startswith("UPDATE BOOK")
            for query, _ in connection.cursor_obj.statements
        ))

    def test_delete_book_without_issue_history_succeeds(self):
        connection = self._transaction_fake_conn([
            [{"book_id": 7}],
            [{"issue_count": 0}],
            [],
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.delete("/api/books/7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(connection.committed)
        delete_statement = connection.cursor_obj.statements[-1]
        self.assertEqual(
            delete_statement[0],
            "DELETE FROM book WHERE book_id = %s",
        )
        self.assertEqual(delete_statement[1], (7,))
        history_query = connection.cursor_obj.statements[1][0]
        self.assertIn("FROM issue WHERE book_id = %s", history_query)
        self.assertNotIn("return_date", history_query.lower())

    def test_delete_book_is_blocked_by_any_issue_history(self):
        connection = self._transaction_fake_conn([
            [{"book_id": 7}],
            [{"issue_count": 1}],
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.delete("/api/books/7")

        self.assertEqual(response.status_code, 409)
        self.assertIn("issue history", response.json["message"])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any(
            query.lstrip().upper().startswith("DELETE FROM BOOK")
            for query, _ in connection.cursor_obj.statements
        ))

    def test_book_update_and_delete_require_admin_authentication(self):
        update_response = self.client.put("/api/books/7", data={})
        delete_response = self.client.delete("/api/books/7")

        self.assertEqual(update_response.status_code, 401)
        self.assertEqual(delete_response.status_code, 401)

    def test_admin_book_search_filters_all_supported_fields(self):
        search_cases = (
            ("book_name", "b.book_name LIKE %s"),
            ("author_name", "search_author.author_name LIKE %s"),
            ("category", "c.category_name LIKE %s"),
            ("publisher", "p.publisher_name LIKE %s"),
        )

        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        for search_by, expected_fragment in search_cases:
            with self.subTest(search_by=search_by):
                connection = self._fake_conn([])
                with patch("app.get_connection", return_value=connection):
                    response = self.client.get(
                        "/api/admin/books",
                        query_string={"search_by": search_by, "q": "Example"},
                    )

                self.assertEqual(response.status_code, 200)
                query, params = connection.cursor_obj.statements[0]
                self.assertIn(expected_fragment, query)
                self.assertEqual(params, ("%Example%",))

    def test_admin_issue_search_matches_student_id_exactly(self):
        issue_date = date.today()
        connection = self._fake_conn([{
            "issue_id": 17,
            "student_id": "PKD25IT034",
            "student_name": "Student",
            "department": "IT",
            "book_name": "Example Book",
            "admin_name": "Library Admin",
            "issue_date": issue_date,
            "due_date": issue_date + timedelta(days=14),
            "return_date": None,
        }])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues",
                query_string={"search_by": "student_id", "keyword": "PKD25IT034"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["student_id"], "PKD25IT034")
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("i.student_id = %s", query)
        self.assertIn("SELECT i.issue_id, i.student_id, s.student_name", query)
        self.assertIn("JOIN student s ON s.student_id = i.student_id", query)
        self.assertEqual(params, ("PKD25IT034",))

    def test_admin_issue_suggestions_search_student_names_and_ids_by_prefix(self):
        suggestion = {
            "suggestion_type": "Student",
            "suggestion_value": "PKD25IT034",
            "suggestion_label": "Helba Shoby",
            "suggestion_detail": "PKD25IT034",
        }
        connection = self._fake_conn([suggestion])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "hE", "type": "student"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [suggestion])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("FROM student", query)
        self.assertIn("LEFT(LOWER(student_name), CHAR_LENGTH(%s)) = LOWER(%s)", query)
        self.assertIn("LEFT(LOWER(student_id), CHAR_LENGTH(%s)) = LOWER(%s)", query)
        self.assertNotIn("FROM book", query)
        self.assertEqual(params, ("hE", "hE", "hE", "hE"))

    def test_admin_issue_suggestions_search_book_titles_by_prefix(self):
        suggestion = {
            "suggestion_type": "Book",
            "suggestion_value": "12",
            "suggestion_label": "Database System Concepts",
            "suggestion_detail": "12",
            "available_copy": 0,
        }
        connection = self._fake_conn([suggestion])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "Database", "type": "book"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [suggestion])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("FROM book", query)
        self.assertIn("LEFT(LOWER(book_name), CHAR_LENGTH(%s)) = LOWER(%s)", query)
        self.assertIn("available_copy", query)
        self.assertNotIn("FROM student", query)
        self.assertNotIn("LIKE", query)
        self.assertEqual(params, ("Database", "Database", "Database", "Database"))

    def test_add_book_autocomplete_suggestions_use_prefix_searches(self):
        cases = (
            (
                "category",
                {"suggestion_type": "Category", "suggestion_value": "3",
                 "suggestion_label": "Science", "suggestion_detail": "3"},
                "FROM category",
                ("sC", "sC"),
            ),
            (
                "publisher",
                {"suggestion_type": "Publisher", "suggestion_value": "8",
                 "suggestion_label": "Sage Publishing", "suggestion_detail": "8"},
                "FROM publisher",
                ("sC", "sC"),
            ),
        )
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        for search_type, suggestion, expected_table, expected_params in cases:
            with self.subTest(search_type=search_type):
                connection = self._fake_conn([suggestion])
                with patch("app.get_connection", return_value=connection):
                    response = self.client.get(
                        "/api/admin/issues/suggestions",
                        query_string={"q": "sC", "type": search_type},
                    )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, [suggestion])
                query, params = connection.cursor_obj.statements[0]
                self.assertIn(expected_table, query)
                self.assertIn("LEFT(LOWER(", query)
                self.assertEqual(params, expected_params)

    def test_issue_autocomplete_book_id_prefix_is_parameterized(self):
        suggestion = {
            "suggestion_type": "Book",
            "suggestion_value": "12",
            "suggestion_label": "Example Book",
            "suggestion_detail": "12",
        }
        connection = self._fake_conn([suggestion])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "1", "type": "book"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [suggestion])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("LOWER(LEFT(CAST(book_id AS CHAR)", query)
        self.assertEqual(params, ("1", "1", "1", "1"))

    def test_return_autocomplete_only_searches_unreturned_issues(self):
        suggestion = {
            "suggestion_type": "Issue",
            "suggestion_value": "41",
            "suggestion_label": "Issue #41",
            "suggestion_detail": "Data Systems - Student PKD25IT034",
        }
        connection = self._fake_conn([suggestion])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "Data", "type": "return_issue"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [suggestion])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("FROM issue i", query)
        self.assertIn("JOIN book b ON b.book_id = i.book_id", query)
        self.assertIn("i.return_date IS NULL", query)
        self.assertIn("LEFT(CAST(i.issue_id AS CHAR)", query)
        self.assertIn("b.book_name", query)
        self.assertIn("i.student_id", query)
        self.assertEqual(params, ("Data", "Data", "Data", "Data", "Data", "Data"))

    def test_admin_issue_suggestions_empty_and_no_match_results(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection") as get_connection:
            empty_response = self.client.get("/api/admin/issues/suggestions")
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json, [])
        get_connection.assert_not_called()

        connection = self._fake_conn([])
        with patch("app.get_connection", return_value=connection):
            no_match_response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "NoMatch"},
            )
        self.assertEqual(no_match_response.status_code, 200)
        self.assertEqual(no_match_response.json, [])

    def test_admin_issue_suggestions_reject_invalid_search_type(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection") as get_connection:
            response = self.client.get(
                "/api/admin/issues/suggestions",
                query_string={"q": "B", "type": "everything"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["status"], "error")
        get_connection.assert_not_called()

    def test_admin_issue_records_filter_by_selected_book_suggestion(self):
        issue_date = date.today()
        connection = self._fake_conn([{
            "issue_id": 21,
            "student_id": "PKD25IT034",
            "student_name": "Helba Shoby",
            "department": "IT",
            "book_name": "Database System Concepts",
            "admin_name": "Library Admin",
            "issue_date": issue_date,
            "due_date": issue_date + timedelta(days=14),
            "return_date": None,
        }])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues",
                query_string={"search_by": "book_id", "keyword": "12"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["book_name"], "Database System Concepts")
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("i.book_id = %s", query)
        self.assertEqual(params, (12,))

    def test_admin_dashboard_renders_separate_student_id_column(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        admin_row = {"adm_name": "Library Admin", "phone_no": "555"}
        with patch("app.get_connection", return_value=self._fake_conn([admin_row])):
            response = self.client.get("/admin-dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<th>Student ID</th>", response.data)
        for section_label in (
            b"Dashboard / Overview",
            b"Student Management",
            b"Book Management",
            b"Issue Book",
            b"Return Book",
            b"Issue Records",
        ):
            self.assertIn(section_label, response.data)
        self.assertIn(b'id="add-student-form"', response.data)
        self.assertIn(b'id="student-search-form"', response.data)
        self.assertIn(b'id="issue-suggestion-query"', response.data)
        self.assertIn(b'id="issue-search-type"', response.data)
        self.assertIn(b'<option value="book" selected>Books</option>', response.data)
        self.assertIn(b'aria-autocomplete="list"', response.data)
        self.assertIn(b'id="issue-student-query"', response.data)
        self.assertIn(b'placeholder="Type student name or ID..."', response.data)
        self.assertIn(b'id="issue_student_id" name="student_id"', response.data)
        self.assertNotIn(b'<select id="issue_student_id"', response.data)
        self.assertIn(b'id="clear-issue-student"', response.data)
        self.assertIn(b'id="issue-book-query"', response.data)
        self.assertIn(b'id="issue_book_id" name="book_id"', response.data)
        self.assertNotIn(b'<select id="issue_book_id"', response.data)
        self.assertIn(b'id="category-query"', response.data)
        self.assertIn(b'id="category_id" name="category_id"', response.data)
        self.assertNotIn(b'<select id="category_id"', response.data)
        self.assertIn(b'id="publisher-query"', response.data)
        self.assertIn(b'id="publisher_id" name="publisher_id"', response.data)
        self.assertNotIn(b'<select id="publisher_id"', response.data)
        self.assertIn(b'id="return-issue-query"', response.data)
        self.assertIn(b'id="issue_id" name="issue_id"', response.data)
        self.assertNotIn(b'<select id="issue_id"', response.data)

    def test_admin_book_options_do_not_load_student_list_for_issue_selection(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        connection = self._fake_conn([])
        with patch("app.get_connection", return_value=connection):
            response = self.client.get("/api/admin/book-options")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"categories": [], "publishers": []})
        executed_queries = [query for query, _ in connection.cursor_obj.statements]
        self.assertEqual(len(executed_queries), 2)
        self.assertTrue(all("FROM student" not in query for query in executed_queries))

    def test_admin_student_listing_returns_student_fields(self):
        student = {
            "student_id": "PKD25IT034",
            "student_name": "Helba Shoby",
            "department": "IT",
            "semester": 5,
            "phoneno": "9876543003",
        }
        connection = self._fake_conn([student])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get("/api/admin/students")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [student])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("SELECT student_id, student_name, department, semester, phoneno", query)
        self.assertIn("FROM student", query)
        self.assertIsNone(params)

    def test_admin_student_search_uses_exact_student_id(self):
        student = {
            "student_id": "PKD25IT034",
            "student_name": "Helba Shoby",
            "department": "IT",
            "semester": 5,
            "phoneno": "9876543003",
        }
        connection = self._fake_conn([student])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/students",
                query_string={"student_id": "PKD25IT034"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [student])
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("WHERE student_id = %s", query)
        self.assertEqual(params, ("PKD25IT034",))

    def test_admin_add_student_inserts_valid_record(self):
        connection = self._fake_conn([None])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/admin/students",
                data={
                    "student_id": "PKD25IT099",
                    "student_name": "New Student",
                    "department": "IT",
                    "semester": "2",
                    "phoneno": "9876543999",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "success")
        insert_query, params = connection.cursor_obj.statements[1]
        self.assertIn("INSERT INTO student", insert_query)
        self.assertEqual(
            params,
            ("PKD25IT099", "New Student", "IT", 2, "9876543999"),
        )

    def test_admin_add_student_rejects_duplicate_id(self):
        connection = self._fake_conn([{"student_id": "PKD25IT099"}])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/admin/students",
                data={
                    "student_id": "PKD25IT099",
                    "student_name": "New Student",
                    "department": "IT",
                    "semester": "2",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json["message"])
        self.assertEqual(len(connection.cursor_obj.statements), 1)

    def test_admin_add_student_rejects_invalid_fields_without_database_access(self):
        valid_student = {
            "student_id": "PKD25IT099",
            "student_name": "New Student",
            "department": "IT",
            "semester": "2",
            "phoneno": "9876543999",
        }
        invalid_students = (
            {**valid_student, "student_id": ""},
            {**valid_student, "student_id": "S" * 16},
            {**valid_student, "student_name": " "},
            {**valid_student, "department": ""},
            {**valid_student, "semester": "0"},
            {**valid_student, "semester": "13"},
            {**valid_student, "semester": "two"},
            {**valid_student, "phoneno": "1" * 16},
        )
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        for student_data in invalid_students:
            with self.subTest(student_data=student_data):
                with patch("app.get_connection") as get_connection:
                    response = self.client.post(
                        "/api/admin/students",
                        data=student_data,
                    )
                self.assertEqual(response.status_code, 400)
                get_connection.assert_not_called()

    def test_admin_issue_search_matches_issue_date_exactly(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        issue_date = date(2026, 3, 1)
        connection = self._fake_conn([])
        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues",
                query_string={
                    "search_by": "issue_date",
                    "keyword": issue_date.isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("i.issue_date = %s", query)
        self.assertEqual(params, (issue_date,))

    def test_admin_issue_search_matches_due_date_exactly(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        due_date = date(2026, 3, 15)
        connection = self._fake_conn([])
        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues",
                query_string={
                    "search_by": "due_date",
                    "keyword": due_date.isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)
        query, params = connection.cursor_obj.statements[0]
        self.assertIn("i.due_date = %s", query)
        self.assertEqual(params, (due_date,))

    def test_admin_issue_status_search_is_case_insensitive_substring(self):
        due_date = date.today()
        connection = self._fake_conn([
            {
                "issue_id": 17,
                "student_id": "PKD25IT034",
                "student_name": "Student",
                "department": "IT",
                "book_name": "Example Book",
                "admin_name": "Library Admin",
                "issue_date": due_date - timedelta(days=20),
                "due_date": due_date - timedelta(days=6),
                "return_date": due_date - timedelta(days=5),
            },
            {
                "issue_id": 18,
                "student_id": "PKD25IT011",
                "student_name": "Another Student",
                "department": "IT",
                "book_name": "Another Book",
                "admin_name": "Library Admin",
                "issue_date": due_date - timedelta(days=20),
                "due_date": due_date - timedelta(days=6),
                "return_date": None,
            },
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.get(
                "/api/admin/issues",
                query_string={
                    "search_by": "status",
                    "keyword": "rEtUrNeD (oVeRdUe)",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)
        self.assertEqual(response.json[0]["status"], "Returned (Overdue)")
        self.assertEqual(response.json[0]["student_id"], "PKD25IT034")
        self.assertEqual(connection.cursor_obj.statements[0][1], ())

    def test_admin_issue_search_rejects_invalid_dates_and_fields(self):
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        for query_string in (
            {"search_by": "issue_date", "keyword": "2026-02-30"},
            {"search_by": "due_date", "keyword": "2026-2-03"},
            {"search_by": "not_a_field", "keyword": "value"},
            {"keyword": "PKD25IT034"},
        ):
            with self.subTest(query_string=query_string):
                with patch("app.get_connection") as get_connection:
                    response = self.client.get(
                        "/api/admin/issues",
                        query_string=query_string,
                    )
                self.assertEqual(response.status_code, 400)
                get_connection.assert_not_called()

    def test_issue_due_date_is_calculated_as_fourteen_calendar_days(self):
        issue_date = date(2026, 12, 25)
        self.assertEqual(
            library_app._calculate_due_date(issue_date),
            date(2027, 1, 8),
        )

    def test_issue_endpoint_ignores_submitted_due_date(self):
        issue_date = date.today()
        connection = self._fake_conn([
            {"student_id": "STU001"},
            {"book_id": 9, "available_copy": 2},
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/issues",
                data={
                    "student_id": "STU001",
                    "book_id": "9",
                    "issue_date": issue_date.isoformat(),
                    "due_date": "2099-01-01",
                },
            )

        self.assertEqual(response.status_code, 201)
        insert_statement = next(
            statement for statement in connection.cursor_obj.statements
            if statement[0].lstrip().upper().startswith("INSERT INTO ISSUE")
        )
        self.assertEqual(
            insert_statement[1],
            (
                issue_date,
                issue_date + timedelta(days=14),
                "STU001",
                "LIB123",
                9,
            ),
        )

    def test_issue_endpoint_rejects_book_with_zero_available_copies(self):
        connection = self._fake_conn([
            {"student_id": "STU001"},
            {"book_id": 9, "available_copy": 0},
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/issues",
                data={
                    "student_id": "STU001",
                    "book_id": "9",
                    "issue_date": date.today().isoformat(),
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json["message"],
            "This book is currently not available.",
        )
        statements = connection.cursor_obj.statements
        self.assertFalse(any(
            query.lstrip().upper().startswith("INSERT INTO ISSUE")
            for query, _ in statements
        ))
        stock_updates = [
            query for query, _ in statements
            if query.lstrip().upper().startswith("UPDATE BOOK")
        ]
        self.assertEqual(stock_updates, [])

    def test_issue_endpoint_decrement_is_guarded_against_negative_stock(self):
        issue_date = date.today()
        connection = self._fake_conn([
            {"student_id": "STU001"},
            {"book_id": 9, "available_copy": 1},
        ])
        with self.client.session_transaction() as current_session:
            current_session["admin_id"] = "LIB123"

        with patch("app.get_connection", return_value=connection):
            response = self.client.post(
                "/api/issues",
                data={
                    "student_id": "STU001",
                    "book_id": "9",
                    "issue_date": issue_date.isoformat(),
                },
            )

        self.assertEqual(response.status_code, 201)
        decrement_query, decrement_params = next(
            (query, params) for query, params in connection.cursor_obj.statements
            if query.lstrip().upper().startswith("UPDATE BOOK")
        )
        self.assertIn("available_copy > 0", decrement_query)
        self.assertEqual(decrement_params, (9,))

    def test_issue_status_rules_cover_active_and_returned_records(self):
        today = date(2026, 10, 12)
        due_date = today
        cases = (
            (due_date, None, "Issued"),
            (today - timedelta(days=1), None, "Overdue"),
            (due_date, due_date, "Returned (On Time)"),
            (due_date, due_date + timedelta(days=1), "Returned (Overdue)"),
        )

        for issue_due_date, return_date, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                self.assertEqual(
                    library_app._calculate_issue_status(
                        issue_due_date,
                        return_date,
                        today=today,
                    ),
                    expected_status,
                )


if __name__ == "__main__":
    unittest.main()
