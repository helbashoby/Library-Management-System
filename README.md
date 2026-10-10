# Library Management System

This project is a simple library database management system built with Python, Flask and MySQL. It is designed for a college DBMS demonstration and keeps the original navy-blue, gold and cream styling while adding a safer and more complete student/admin workflow.

## Important notes

- Student IDs are treated as text strings, not integers.
- Admin passwords are stored with Werkzeug password hashing, not in plaintext.
- The Issue table starts empty on a fresh demo so the team can demonstrate live issue and return operations.
- If the database already exists, the safe seed logic only adds missing rows and updates missing schema details without dropping tables or deleting user data.

## Demo student data

The following sample student records are included in the safe seed process:

- PKD25IT004 - Aadhithya C - IT - Semester 5
- PKD25IT011 - Anaga E S - IT - Semester 5
- PKD25IT034 - Helba Shoby - IT - Semester 5
- PKD25IT050 - Nikhil Chandran - IT - Semester 5
- PKD25CS005 - Megha - CS - Semester 4
- PKD25ME006 - Helena - ME - Semester 4
- PKD25CS007 - Malavika - CS - Semester 5
- PKD25ME008 - Sandhra - ME - Semester 4
- PKD25CS009 - Varsha - CS - Semester 5
- PKD25ME010 - Anjali Menon - ME - Semester 3

Anjali Menon is a temporary sample student used only for demonstration. The four core team members retain the exact IDs requested for the project: PKD25IT004, PKD25IT011, PKD25IT034 and PKD25IT050.

The sample phone numbers and semester values are illustrative demo data only.

## Demo admin account

The initial admin account is:

- Admin ID: LIB123
- Password: 12345678
- Name: Library Admin
- Phone: 9876543210

Additional demo administrators are also seeded with secure hashed passwords. The app does not reset the LIB123 password on every run because the seed process uses an INSERT IF NOT EXISTS pattern and keeps the stored hash.

## Safe initialization and migration

The project intentionally does not execute a destructive DROP DATABASE command. The safe initialization sequence is:

1. Connect to MySQL.
2. Create the database if missing.
3. Create missing tables with the updated text-based student/admin IDs.
4. Apply schema changes such as VARCHAR IDs and total_copy where needed.
5. Insert sample rows only when they are missing.
6. Leave the Issue table empty on first run.

If the database has older integer-based tables, a manual migration may still be needed before production use. The exact SQL to back up and update an existing database is:

```sql
CREATE TABLE backup_student AS SELECT * FROM student;
CREATE TABLE backup_admin AS SELECT * FROM admin;
CREATE TABLE backup_book AS SELECT * FROM book;
CREATE TABLE backup_issue AS SELECT * FROM issue;

ALTER TABLE student MODIFY student_id VARCHAR(15) NOT NULL;
ALTER TABLE admin MODIFY admin_id VARCHAR(20) NOT NULL;
ALTER TABLE admin MODIFY password VARCHAR(255) NOT NULL;
ALTER TABLE issue MODIFY student_id VARCHAR(15) NOT NULL;
ALTER TABLE issue MODIFY admin_id VARCHAR(20) NOT NULL;
ALTER TABLE book ADD COLUMN total_copy INT NOT NULL DEFAULT 0 AFTER available_copy;
UPDATE book SET total_copy = available_copy WHERE total_copy = 0 OR total_copy IS NULL;
```

This is a backup-first migration plan. No data is intentionally deleted by the application.

## Student login detail

The student login is designed as a basic demonstration login and is not strong identity authentication. The application checks the submitted Student ID and Student Name against the Student table, trims whitespace, and stores the session for the dashboard. This is suitable for a learning project, not a production-grade security system.

## Run the app

1. Activate the virtual environment.
2. Install dependencies from requirements.txt.
3. Update .env with your MySQL settings.
4. Start Flask.

## Dependencies

- Flask
- mysql-connector-python
- python-dotenv
- Werkzeug

## Common workflow

1. Open the home page and choose Student Login or Admin Login.
2. Use the demo admin credentials to access the admin dashboard.
3. Add books with category and publisher selections.
4. Issue books to students using the database-backed dropdowns.
5. Record returns to update book stock and issue history.

The project intentionally keeps the Issue table empty on first seed to make the issue/return cycle visible during the demonstration.

## Testing checklist

- Database connection
- Student ID string handling
- Student login and invalid-login checks
- Search by title, author, category and publisher
- Protected admin/student routes
- Secure admin login using hashed passwords
- Book add + issue + return flow
- Stock count maintenance
- Duplicate return prevention
- Safe re-run of the seed logic
