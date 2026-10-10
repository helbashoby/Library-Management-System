
from db import get_connection

COLUMN_METADATA_QUERY = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
           IS_NULLABLE
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME IN ('student', 'admin', 'issue', 'book')
"""

FOREIGN_KEY_METADATA_QUERY = """
    SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND REFERENCED_TABLE_NAME IS NOT NULL
      AND (
          (TABLE_NAME = 'issue' AND COLUMN_NAME IN ('student_id', 'admin_id'))
          OR (REFERENCED_TABLE_NAME = 'student' AND REFERENCED_COLUMN_NAME = 'student_id')
          OR (REFERENCED_TABLE_NAME = 'admin' AND REFERENCED_COLUMN_NAME = 'admin_id')
      )
"""

ID_COLUMN_TARGETS = (
    ("student", "student_id", 15),
    ("admin", "admin_id", 20),
    ("issue", "student_id", 15),
    ("issue", "admin_id", 20),
)

REQUIRED_COLUMNS = (
    ("student", "student_id"),
    ("admin", "admin_id"),
    ("admin", "password"),
    ("issue", "student_id"),
    ("issue", "admin_id"),
    ("book", "available_copy"),
)


class MigrationSafetyError(RuntimeError):
    """Raised when metadata does not support a safe automatic migration."""


def build_migration_plan(column_rows, foreign_key_rows):
    columns = {
        (row["TABLE_NAME"], row["COLUMN_NAME"]): row
        for row in column_rows
    }
    missing_columns = [key for key in REQUIRED_COLUMNS if key not in columns]
    if missing_columns:
        missing = ", ".join(f"{table}.{column}" for table, column in missing_columns)
        raise MigrationSafetyError(
            f"Required schema metadata is missing for: {missing}. No changes were applied."
        )

    plan = []
    changed_id_columns = set()
    integer_types = {"tinyint", "smallint", "mediumint", "int", "bigint"}

    for table, column, target_length in ID_COLUMN_TARGETS:
        metadata = columns[(table, column)]
        data_type = metadata["DATA_TYPE"].lower()
        if metadata["IS_NULLABLE"] == "YES":
            raise MigrationSafetyError(
                f"{table}.{column} allows NULL; review its data and constraints before migration."
            )

        if data_type == "varchar":
            current_length = metadata["CHARACTER_MAXIMUM_LENGTH"]
            if current_length is None:
                raise MigrationSafetyError(
                    f"Could not determine the length of {table}.{column}."
                )
            needs_change = current_length < target_length
        elif data_type in integer_types:
            needs_change = True
        else:
            raise MigrationSafetyError(
                f"Unsupported identifier type for {table}.{column}: {data_type}."
            )

        if needs_change:
            plan.append(
                f"ALTER TABLE {table} MODIFY COLUMN {column} VARCHAR({target_length}) NOT NULL"
            )
            changed_id_columns.add((table, column))

    if changed_id_columns:
        related_constraints = []
        for foreign_key in foreign_key_rows:
            child_column = (foreign_key["TABLE_NAME"], foreign_key["COLUMN_NAME"])
            parent_column = (
                foreign_key["REFERENCED_TABLE_NAME"],
                foreign_key["REFERENCED_COLUMN_NAME"],
            )
            if child_column in changed_id_columns or parent_column in changed_id_columns:
                related_constraints.append(
                    f"{foreign_key['TABLE_NAME']}.{foreign_key['CONSTRAINT_NAME']}"
                )

        if related_constraints:
            constraints = ", ".join(sorted(set(related_constraints)))
            raise MigrationSafetyError(
                "Identifier columns need type changes but are used by foreign keys: "
                f"{constraints}. This migration will not drop or recreate constraints; "
                "review their actual definitions and prepare an explicit plan. No changes were applied."
            )

    password_metadata = columns[("admin", "password")]
    if password_metadata["DATA_TYPE"].lower() != "varchar":
        raise MigrationSafetyError(
            "admin.password is not VARCHAR; review its type before widening it."
        )
    password_length = password_metadata["CHARACTER_MAXIMUM_LENGTH"]
    if password_length is None:
        raise MigrationSafetyError("Could not determine the length of admin.password.")
    if password_length < 255:
        nullability = "NULL" if password_metadata["IS_NULLABLE"] == "YES" else "NOT NULL"
        plan.append(
            f"ALTER TABLE admin MODIFY COLUMN password VARCHAR(255) {nullability}"
        )

    total_copy = columns.get(("book", "total_copy"))
    if total_copy is None:
        plan.append(
            "ALTER TABLE book ADD COLUMN total_copy INT NULL DEFAULT NULL AFTER available_copy"
        )
    elif total_copy["DATA_TYPE"].lower() not in integer_types:
        raise MigrationSafetyError(
            f"Unsupported type for book.total_copy: {total_copy['DATA_TYPE']}."
        )

    return plan


def migrate_database():
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(COLUMN_METADATA_QUERY)
        column_rows = cursor.fetchall()
        cursor.execute(FOREIGN_KEY_METADATA_QUERY)
        foreign_key_rows = cursor.fetchall()

        plan = build_migration_plan(column_rows, foreign_key_rows)
        if not plan:
            print("No schema changes are needed.")
            return

        for statement in plan:
            cursor.execute(statement)

        print("Migration completed. Existing IDs and password values were not changed.")
        print(
            "book.total_copy was added as NULL where missing; reconcile inventory "
            "and outstanding issues before setting totals."
        )
    except MigrationSafetyError:
        raise
    except Exception as error:
        raise RuntimeError(
            "Migration stopped. MySQL may have implicitly committed earlier DDL; "
            "inspect the schema before retrying and do not assume rollback is possible."
        ) from error
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as error:
        print(f"Migration not completed: {error}")
        raise SystemExit(1)