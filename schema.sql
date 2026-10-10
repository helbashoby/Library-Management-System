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
    author_name VARCHAR(120) NOT NULL,
    available_copy INT NOT NULL,
    total_copy INT NOT NULL DEFAULT 0,
    shelf_loc VARCHAR(30),
    category_id INT NOT NULL,
    publisher_id INT NOT NULL,
    PRIMARY KEY (book_id),
    CONSTRAINT fk_book_category FOREIGN KEY (category_id) REFERENCES category(category_id),
    CONSTRAINT fk_book_publisher FOREIGN KEY (publisher_id) REFERENCES publisher(publisher_id)
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
SELECT seed.admin_id, seed.adm_name, seed.password, seed.phone_no
FROM (
    SELECT 'LIB123' AS admin_id, 'Library Admin' AS adm_name, '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q' AS password, '9876543210' AS phone_no
    UNION ALL SELECT 'ADM001', 'Helba Shoby', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543211'
    UNION ALL SELECT 'ADM002', 'Adithyan C', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543212'
    UNION ALL SELECT 'ADM003', 'Anagha E S', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543213'
    UNION ALL SELECT 'ADM004', 'Nikhil Chandran', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543214'
    UNION ALL SELECT 'ADM005', 'Megha', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543215'
    UNION ALL SELECT 'ADM006', 'Helena', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543216'
    UNION ALL SELECT 'ADM007', 'Malavika', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543217'
    UNION ALL SELECT 'ADM008', 'Sandhra', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543218'
    UNION ALL SELECT 'ADM009', 'Varsha', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543219'
    UNION ALL SELECT 'ADM010', 'Anjali Menon', '$2b$12$J4ARHj8v0e4cDqzNwfhjEuzZ8uDgB1/5Jg0EjQH.2zqj5VxA4L39q', '9876543220'
) AS seed
WHERE NOT EXISTS (
    SELECT 1 FROM admin existing WHERE existing.admin_id = seed.admin_id
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

INSERT INTO book (book_name, author_name, available_copy, total_copy, shelf_loc, category_id, publisher_id)
SELECT seed.book_name, seed.author_name, seed.available_copy, seed.total_copy, seed.shelf_loc, c.category_id, p.publisher_id
FROM (
    SELECT 'Database System Concepts' AS book_name, 'Abraham Silberschatz' AS author_name, 6 AS available_copy, 6 AS total_copy, 'A-12' AS shelf_loc, 'Computer Science' AS category_name, 'McGraw Hill' AS publisher_name
    UNION ALL SELECT 'Programming in ANSI C', 'E. Balagurusamy', 8, 8, 'A-08', 'Programming', 'Pearson'
    UNION ALL SELECT 'Operating System Concepts', 'Abraham Silberschatz', 5, 5, 'A-14', 'Operating Systems', 'McGraw Hill'
    UNION ALL SELECT 'Data Structures and Algorithms', 'Sartaj Sahni', 7, 7, 'B-02', 'Data Structures', 'PHI Learning'
    UNION ALL SELECT 'Higher Engineering Mathematics', 'B. S. Grewal', 9, 9, 'C-05', 'Mathematics', 'Oxford University Press'
    UNION ALL SELECT 'Computer Fundamentals', 'R. S. Salaria', 4, 4, 'A-03', 'Computer Science', 'PHI Learning'
    UNION ALL SELECT 'Introduction to Algorithms', 'Thomas H. Cormen', 6, 6, 'B-08', 'Data Structures', 'Addison-Wesley'
    UNION ALL SELECT 'Digital Logic and Computer Design', 'M. Morris Mano', 5, 5, 'D-04', 'Electronics', 'Wiley'
    UNION ALL SELECT 'Fundamentals of Database Systems', 'Ramez Elmasri', 4, 4, 'A-22', 'Database Management', 'Cengage'
    UNION ALL SELECT 'Engineering Mechanics', 'S. S. Bhavikatti', 3, 3, 'E-11', 'Mechanical Engineering', 'Tata McGraw-Hill'
) AS seed
JOIN category c ON c.category_name = seed.category_name
JOIN publisher p ON p.publisher_name = seed.publisher_name
WHERE NOT EXISTS (
    SELECT 1
    FROM book existing
    WHERE existing.book_name = seed.book_name
      AND existing.author_name = seed.author_name
);

-- ISSUES: intentionally left at zero during the initial demo run.
-- The team can issue and return books live after login and testing.
