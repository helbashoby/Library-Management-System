-- ============================================================
-- Library Management System - Safe MySQL Schema
-- This script does not drop the database or delete user data.
-- It creates missing tables and seeds demo records only when absent.
-- For existing legacy databases, review and run migrate_db.py separately first.
-- ============================================================

CREATE DATABASE IF NOT EXISTS library_db;
USE library_db;

CREATE TABLE IF NOT EXISTS admin (
    admin_id VARCHAR(20) NOT NULL,
    adm_name VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone_no VARCHAR(15),
    PRIMARY KEY (admin_id)
);

CREATE TABLE IF NOT EXISTS student (
    student_id VARCHAR(15) NOT NULL,
    student_name VARCHAR(100) NOT NULL,
    department VARCHAR(80) NOT NULL,
    semester TINYINT NOT NULL,
    phoneno VARCHAR(15),
    PRIMARY KEY (student_id)
);

CREATE TABLE IF NOT EXISTS category (
    category_id INT NOT NULL AUTO_INCREMENT,
    category_name VARCHAR(80) NOT NULL,
    PRIMARY KEY (category_id),
    UNIQUE (category_name)
);

CREATE TABLE IF NOT EXISTS publisher (
    publisher_id INT NOT NULL AUTO_INCREMENT,
    publisher_name VARCHAR(120) NOT NULL,
    PRIMARY KEY (publisher_id),
    UNIQUE (publisher_name)
);

CREATE TABLE IF NOT EXISTS book (
    book_id INT NOT NULL AUTO_INCREMENT,
    book_name VARCHAR(200) NOT NULL,
    available_copy INT NOT NULL,
    total_copy INT NOT NULL DEFAULT 0,
    shelf_loc VARCHAR(30),
    category_id INT NOT NULL,
    publisher_id INT NOT NULL,
    PRIMARY KEY (book_id),
    CONSTRAINT fk_book_category FOREIGN KEY (category_id) REFERENCES category(category_id),
    CONSTRAINT fk_book_publisher FOREIGN KEY (publisher_id) REFERENCES publisher(publisher_id)
);

CREATE TABLE IF NOT EXISTS book_author (
    book_id INT NOT NULL,
    author_name VARCHAR(120) NOT NULL,
    PRIMARY KEY (book_id, author_name),
    CONSTRAINT fk_book_author_book
        FOREIGN KEY (book_id)
        REFERENCES book(book_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS issue (
    issue_id INT NOT NULL AUTO_INCREMENT,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    return_date DATE,
    student_id VARCHAR(15) NOT NULL,
    admin_id VARCHAR(20) NOT NULL,
    book_id INT NOT NULL,
    PRIMARY KEY (issue_id),
    CONSTRAINT fk_issue_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_issue_admin FOREIGN KEY (admin_id) REFERENCES admin(admin_id),
    CONSTRAINT fk_issue_book FOREIGN KEY (book_id) REFERENCES book(book_id)
);

-- ============================================================
-- Demo Seed Data
-- The Issue table intentionally starts empty for live demonstration.
-- ============================================================


INSERT INTO admin (admin_id, adm_name, password, phone_no)
SELECT
    'LIB123',
    'Library Admin',
    '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q',
    '9876543210'
WHERE NOT EXISTS (
    SELECT 1
    FROM admin
    WHERE admin_id = 'LIB123'
);

INSERT INTO student (student_id, student_name, department, semester, phoneno)
SELECT seed.student_id, seed.student_name, seed.department, seed.semester, seed.phoneno
FROM (
    SELECT 'PKD25IT004' AS student_id, 'Aadhithya C' AS student_name, 'IT' AS department, 5 AS semester, '9876543001' AS phoneno
    UNION ALL SELECT 'PKD25IT011', 'Anaga E S', 'IT', 5, '9876543002'
    UNION ALL SELECT 'PKD25IT034', 'Helba Shoby', 'IT', 5, '9876543003'
    UNION ALL SELECT 'PKD25IT050', 'Nikhil Chandran', 'IT', 5, '9876543004'
    UNION ALL SELECT 'PKD25CS005', 'Megha', 'CS', 4, '9876543005'
    UNION ALL SELECT 'PKD25ME006', 'Helena', 'ME', 4, '9876543006'
    UNION ALL SELECT 'PKD25CS007', 'Malavika', 'CS', 5, '9876543007'
    UNION ALL SELECT 'PKD25ME008', 'Sandhra', 'ME', 4, '9876543008'
    UNION ALL SELECT 'PKD25CS009', 'Varsha', 'CS', 5, '9876543009'
    UNION ALL SELECT 'PKD25ME010', 'Anjali Menon', 'ME', 3, '9876543010'
) AS seed
WHERE NOT EXISTS (
    SELECT 1 FROM student existing WHERE existing.student_id = seed.student_id
);

INSERT INTO category (category_name)
SELECT seed.category_name
FROM (
    SELECT 'Computer Science' AS category_name
    UNION ALL SELECT 'Data Structures'
    UNION ALL SELECT 'Database Management'
    UNION ALL SELECT 'Operating Systems'
    UNION ALL SELECT 'Programming'
    UNION ALL SELECT 'Mathematics'
    UNION ALL SELECT 'Electronics'
    UNION ALL SELECT 'Mechanical Engineering'
    UNION ALL SELECT 'Civil Engineering'
    UNION ALL SELECT 'Fiction'
    UNION ALL SELECT 'Literature'
) AS seed
WHERE NOT EXISTS (
    SELECT 1 FROM category existing WHERE existing.category_name = seed.category_name
);

INSERT INTO publisher (publisher_name)
SELECT seed.publisher_name
FROM (
    SELECT 'McGraw Hill' AS publisher_name
    UNION ALL SELECT 'Pearson'
    UNION ALL SELECT 'PHI Learning'
    UNION ALL SELECT 'Oxford University Press'
    UNION ALL SELECT 'Wiley'
    UNION ALL SELECT 'Schaum\'s Outline'
    UNION ALL SELECT 'Addison-Wesley'
    UNION ALL SELECT 'Cengage'
    UNION ALL SELECT 'Tata McGraw-Hill'
    UNION ALL SELECT 'Springer'
) AS seed
WHERE NOT EXISTS (
    SELECT 1 FROM publisher existing WHERE existing.publisher_name = seed.publisher_name
);

INSERT INTO book (book_name, available_copy, total_copy, shelf_loc, category_id, publisher_id)
SELECT seed.book_name, seed.available_copy, seed.total_copy, seed.shelf_loc, c.category_id, p.publisher_id
FROM (
    SELECT 'Database System Concepts' AS book_name, 10 AS available_copy, 10 AS total_copy, 'A-12' AS shelf_loc, 'Computer Science' AS category_name, 'McGraw Hill' AS publisher_name
    UNION ALL SELECT 'Programming in ANSI C', 9, 10, 'A-08', 'Computer Science', 'McGraw Hill'
    UNION ALL SELECT 'Computer Fundamentals', 10, 10, 'A-03', 'Computer Science', 'PHI Learning'
    UNION ALL SELECT 'Harry Potter and the Philosopher\'s Stone', 10, 10, 'B-21', 'Fiction', 'Pearson'
    UNION ALL SELECT 'Higher Engineering Mathematics', 10, 10, 'C-05', 'Mathematics', 'PHI Learning'
    UNION ALL SELECT 'Operating System Concepts', 10, 10, 'A-14', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Data Structures and Algorithms', 9, 10, 'B-02', 'Fiction', 'PHI Learning'
    UNION ALL SELECT 'Introduction to Algorithms', 10, 10, 'B-08', 'Fiction', 'Addison-Wesley'
    UNION ALL SELECT 'Digital Logic and Computer Design', 10, 10, 'D-04', 'Operating Systems', 'Schaum\'s Outline'
    UNION ALL SELECT 'Fundamentals of Database Systems', 10, 10, 'A-22', 'Mathematics', 'Cengage'
    UNION ALL SELECT 'Engineering Mechanics', 10, 10, 'E-11', 'Programming', 'Tata McGraw-Hill'
    UNION ALL SELECT 'Database System Concepts', 5, 5, 'A-01', 'Database Management', 'McGraw Hill'
    UNION ALL SELECT 'Computer Networking: A Top-Down Approach', 5, 5, 'A-15', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Artificial Intelligence: A Modern Approach', 4, 4, 'A-16', 'Computer Science', 'Pearson'
) AS seed
JOIN category c ON c.category_name = seed.category_name
JOIN publisher p ON p.publisher_name = seed.publisher_name
LEFT JOIN book existing
    ON existing.book_name = seed.book_name
   AND existing.category_id = c.category_id
   AND existing.publisher_id = p.publisher_id
WHERE existing.book_id IS NULL;

INSERT INTO book_author (book_id, author_name)
SELECT b.book_id, seed.author_name
FROM (
    SELECT 'Database System Concepts' AS book_name, 'Abraham Silberschatz' AS author_name, 'Computer Science' AS category_name, 'McGraw Hill' AS publisher_name
    UNION ALL SELECT 'Programming in ANSI C', 'E. Balagurusamy', 'Computer Science', 'McGraw Hill'
    UNION ALL SELECT 'Computer Fundamentals', 'R. S. Salaria', 'Computer Science', 'PHI Learning'
    UNION ALL SELECT 'Harry Potter and the Philosopher\'s Stone', 'J. K. Rowling', 'Fiction', 'Pearson'
    UNION ALL SELECT 'Higher Engineering Mathematics', 'B. S. Grewal', 'Mathematics', 'PHI Learning'
    UNION ALL SELECT 'Operating System Concepts', 'Abraham Silberschatz', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Data Structures and Algorithms', 'Sartaj Sahni', 'Fiction', 'PHI Learning'
    UNION ALL SELECT 'Introduction to Algorithms', 'Thomas H. Cormen', 'Fiction', 'Addison-Wesley'
    UNION ALL SELECT 'Digital Logic and Computer Design', 'M. Morris Mano', 'Operating Systems', 'Schaum\'s Outline'
    UNION ALL SELECT 'Fundamentals of Database Systems', 'Ramez Elmasri', 'Mathematics', 'Cengage'
    UNION ALL SELECT 'Engineering Mechanics', 'S. S. Bhavikatti', 'Programming', 'Tata McGraw-Hill'
    UNION ALL SELECT 'Database System Concepts', 'Abraham Silberschatz', 'Database Management', 'McGraw Hill'
    UNION ALL SELECT 'Database System Concepts', 'Henry F. Korth', 'Database Management', 'McGraw Hill'
    UNION ALL SELECT 'Database System Concepts', 'S. Sudarshan', 'Database Management', 'McGraw Hill'
    UNION ALL SELECT 'Computer Networking: A Top-Down Approach', 'James F. Kurose', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Computer Networking: A Top-Down Approach', 'Keith W. Ross', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Artificial Intelligence: A Modern Approach', 'Peter Norvig', 'Computer Science', 'Pearson'
    UNION ALL SELECT 'Artificial Intelligence: A Modern Approach', 'Stuart Russell', 'Computer Science', 'Pearson'
) AS seed
JOIN category c ON c.category_name = seed.category_name
JOIN publisher p ON p.publisher_name = seed.publisher_name
JOIN book b
    ON b.book_name = seed.book_name
   AND b.category_id = c.category_id
   AND b.publisher_id = p.publisher_id
LEFT JOIN book_author ba
    ON ba.book_id = b.book_id
   AND ba.author_name = seed.author_name
WHERE ba.book_id IS NULL;

-- ISSUES: intentionally left at zero during the initial demo run.
-- The team can issue and return books live after login and testing.
