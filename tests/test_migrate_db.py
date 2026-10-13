import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import migrate_db


class MigrationPlanTests(unittest.TestCase):
    def _column(self, table, column, data_type, length=None, nullable="NO"):
        return {
            "TABLE_NAME": table,
            "COLUMN_NAME": column,
            "DATA_TYPE": data_type,
            "CHARACTER_MAXIMUM_LENGTH": length,
            "IS_NULLABLE": nullable,
        }

    def _legacy_columns(self, include_total_copy=False):
        columns = [
            self._column("student", "student_id", "int"),
            self._column("admin", "admin_id", "int"),
            self._column("admin", "password", "varchar", 50),
            self._column("issue", "student_id", "int"),
            self._column("issue", "admin_id", "int"),
            self._column("book", "available_copy", "int"),
        ]
        if include_total_copy:
            columns.append(self._column("book", "total_copy", "int"))
        return columns

    def _current_columns(self):
        return [
            self._column("student", "student_id", "varchar", 15),
            self._column("admin", "admin_id", "varchar", 20),
            self._column("admin", "password", "varchar", 255),
            self._column("issue", "student_id", "varchar", 15),
            self._column("issue", "admin_id", "varchar", 20),
            self._column("book", "available_copy", "int"),
            self._column("book", "total_copy", "int"),
        ]

    def test_plan_preserves_ids_passwords_and_inventory_values(self):
        plan = migrate_db.build_migration_plan(self._legacy_columns(), [])

        self.assertEqual(len(plan), 6)
        self.assertIn(
            "ALTER TABLE book ADD COLUMN total_copy INT NULL DEFAULT NULL AFTER available_copy",
            plan,
        )
        self.assertIn(
            "ALTER TABLE admin MODIFY COLUMN password VARCHAR(255) NOT NULL",
            plan,
        )
        self.assertFalse(any("UPDATE" in statement.upper() for statement in plan))
        self.assertFalse(any("DROP FOREIGN KEY" in statement.upper() for statement in plan))
        self.assertFalse(any("IF NOT EXISTS" in statement.upper() for statement in plan))

    def test_plan_refuses_identifier_changes_when_actual_foreign_keys_exist(self):
        foreign_keys = [
            {
                "TABLE_NAME": "issue",
                "CONSTRAINT_NAME": "fk_issue_student",
                "COLUMN_NAME": "student_id",
                "REFERENCED_TABLE_NAME": "student",
                "REFERENCED_COLUMN_NAME": "student_id",
            },
            {
                "TABLE_NAME": "issue",
                "CONSTRAINT_NAME": "fk_issue_admin",
                "COLUMN_NAME": "admin_id",
                "REFERENCED_TABLE_NAME": "admin",
                "REFERENCED_COLUMN_NAME": "admin_id",
            },
        ]

        with self.assertRaisesRegex(migrate_db.MigrationSafetyError, "fk_issue_student"):
            migrate_db.build_migration_plan(self._legacy_columns(), foreign_keys)

    def test_current_schema_needs_no_changes(self):
        foreign_keys = [
            {
                "TABLE_NAME": "issue",
                "CONSTRAINT_NAME": "fk_issue_student",
                "COLUMN_NAME": "student_id",
                "REFERENCED_TABLE_NAME": "student",
                "REFERENCED_COLUMN_NAME": "student_id",
            },
            {
                "TABLE_NAME": "issue",
                "CONSTRAINT_NAME": "fk_issue_admin",
                "COLUMN_NAME": "admin_id",
                "REFERENCED_TABLE_NAME": "admin",
                "REFERENCED_COLUMN_NAME": "admin_id",
            },
        ]

        plan = migrate_db.build_migration_plan(self._current_columns(), foreign_keys)
        self.assertEqual(plan, [])

    def test_runner_stops_before_ddl_when_foreign_keys_block_id_changes(self):
        columns = self._legacy_columns()
        foreign_keys = [
            {
                "TABLE_NAME": "issue",
                "CONSTRAINT_NAME": "fk_issue_student",
                "COLUMN_NAME": "student_id",
                "REFERENCED_TABLE_NAME": "student",
                "REFERENCED_COLUMN_NAME": "student_id",
            },
        ]

        class FakeCursor:
            def __init__(self):
                self.statements = []
                self.rows = []

            def execute(self, statement):
                self.statements.append(statement)
                if statement == migrate_db.COLUMN_METADATA_QUERY:
                    self.rows = columns
                elif statement == migrate_db.FOREIGN_KEY_METADATA_QUERY:
                    self.rows = foreign_keys

            def fetchall(self):
                return list(self.rows)

            def close(self):
                pass

        class FakeConnection:
            def __init__(self):
                self.fake_cursor = FakeCursor()

            def cursor(self, dictionary=False):
                return self.fake_cursor

            def close(self):
                pass

        connection = FakeConnection()
        with patch("migrate_db.get_connection", return_value=connection):
            with self.assertRaises(migrate_db.MigrationSafetyError):
                migrate_db.migrate_database()

        self.assertEqual(
            connection.fake_cursor.statements,
            [migrate_db.COLUMN_METADATA_QUERY, migrate_db.FOREIGN_KEY_METADATA_QUERY],
        )

    def test_manual_author_migration_backfills_without_replacing_existing_links(self):
        backfill = " ".join(migrate_db.AUTHOR_BACKFILL_SQL.lower().split())
        self.assertIn("insert into book_author (book_id, author_name)", backfill)
        self.assertIn("where not exists", backfill)
        self.assertIn("ba.author_name = b.author_name", backfill)
        self.assertNotIn("delete from book_author", backfill)

        output = StringIO()
        with redirect_stdout(output):
            migrate_db.print_author_migration_sql()
        printed_sql = output.getvalue()
        self.assertLess(
            printed_sql.index(migrate_db.AUTHOR_BACKFILL_SQL.strip()),
            printed_sql.index(migrate_db.AUTHOR_COVERAGE_CHECK_SQL.strip()),
        )
        self.assertLess(
            printed_sql.index(migrate_db.AUTHOR_COVERAGE_CHECK_SQL.strip()),
            printed_sql.index(migrate_db.AUTHOR_COLUMN_DROP_SQL),
        )
        self.assertIn("books_without_authors is 0", printed_sql)


if __name__ == "__main__":
    unittest.main()
