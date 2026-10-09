-- ============================================================
-- Library Database Management System
-- College DBMS Project - MySQL Schema
-- Matches the ER diagram: 6 entities only
--   Student, Admin, Issue, Book, Category, Publisher
--
-- Team:
--   Adithyan C      - PKD25IT004
--   Anagha E S      - PKD25IT011
--   Helba Shoby     - PKD25IT034
--   Nikhil Chandran - PKD25IT050
-- ============================================================

DROP DATABASE IF EXISTS library_db;
CREATE DATABASE library_db;
USE library_db;

-- ------------------------------------------------------------
-- 1. ADMIN
-- Admin 1 : M Issue
-- ------------------------------------------------------------
CREATE TABLE admin (
    admin_id    INT           NOT NULL AUTO_INCREMENT,
    adm_name    VARCHAR(100)  NOT NULL,
    password    VARCHAR(50)   NOT NULL,
    phone_no    VARCHAR(15),

    PRIMARY KEY (admin_id)
);

-- ------------------------------------------------------------
-- 2. STUDENT
-- Student 1 : M Issue
-- ------------------------------------------------------------
CREATE TABLE student (
    student_id    INT           NOT NULL AUTO_INCREMENT,
    student_name  VARCHAR(100)  NOT NULL,
    department    VARCHAR(80)   NOT NULL,
    semester      TINYINT       NOT NULL,
    phoneno       VARCHAR(15),

    PRIMARY KEY (student_id)
);

-- ------------------------------------------------------------
-- 3. CATEGORY
-- Category 1 : M Book
-- ------------------------------------------------------------
CREATE TABLE category (
    category_id    INT          NOT NULL AUTO_INCREMENT,
    category_name  VARCHAR(80)  NOT NULL,

    PRIMARY KEY (category_id),
    UNIQUE (category_name)
);

-- ------------------------------------------------------------
-- 4. PUBLISHER
-- Publisher 1 : M Book
-- ------------------------------------------------------------
CREATE TABLE publisher (
    publisher_id    INT           NOT NULL AUTO_INCREMENT,
    publisher_name  VARCHAR(120)  NOT NULL,

    PRIMARY KEY (publisher_id),
    UNIQUE (publisher_name)
);

-- ------------------------------------------------------------
-- 5. BOOK
-- author_name is an attribute of Book (not a separate entity)
-- Each book belongs to one category and one publisher
-- ------------------------------------------------------------
CREATE TABLE book (
    book_id         INT            NOT NULL AUTO_INCREMENT,
    book_name       VARCHAR(200)   NOT NULL,
    author_name     VARCHAR(120)   NOT NULL,
    available_copy  INT            NOT NULL,
    shelf_loc       VARCHAR(30),
    category_id     INT            NOT NULL,
    publisher_id    INT            NOT NULL,

    PRIMARY KEY (book_id),
    FOREIGN KEY (category_id) REFERENCES category (category_id),
    FOREIGN KEY (publisher_id) REFERENCES publisher (publisher_id)
);

-- ------------------------------------------------------------
-- 6. ISSUE
-- Each issue belongs to one student, one admin, and one book
-- ------------------------------------------------------------
CREATE TABLE issue (
    issue_id     INT   NOT NULL AUTO_INCREMENT,
    issue_date   DATE  NOT NULL,
    due_date     DATE  NOT NULL,
    return_date  DATE,
    student_id   INT   NOT NULL,
    admin_id     INT   NOT NULL,
    book_id      INT   NOT NULL,

    PRIMARY KEY (issue_id),
    FOREIGN KEY (student_id) REFERENCES student (student_id),
    FOREIGN KEY (admin_id) REFERENCES admin (admin_id),
    FOREIGN KEY (book_id) REFERENCES book (book_id)
);

-- ============================================================
-- SAMPLE DATA
-- Insert parent tables first, then Book, then Issue
-- ============================================================

INSERT INTO admin (adm_name, password, phone_no) VALUES
('Library Admin', 'admin123', '9876543210'),
('Helba Shoby', 'lib123', '9876543211');

INSERT INTO student (student_name, department, semester, phoneno) VALUES
('Adithyan C', 'IT', 3, '9000000001'),
('Anagha E S', 'IT', 3, '9000000002'),
('Helba Shoby', 'IT', 3, '9000000003'),
('Nikhil Chandran', 'IT', 3, '9000000004');

INSERT INTO category (category_name) VALUES
('Computer Science'),
('Fiction'),
('Mathematics'),
('Electronics');

INSERT INTO publisher (publisher_name) VALUES
('McGraw Hill'),
('Pearson'),
('PHI Learning');

INSERT INTO book (book_name, author_name, available_copy, shelf_loc, category_id, publisher_id) VALUES
('Database System Concepts', 'Abraham Silberschatz', 4, 'A-12', 1, 1),
('Programming in ANSI C', 'E. Balagurusamy', 8, 'A-08', 1, 1),
('Computer Fundamentals', 'R. S. Salaria', 4, 'A-03', 1, 3),
('Harry Potter and the Philosopher''s Stone', 'J. K. Rowling', 5, 'B-21', 2, 2),
('Higher Engineering Mathematics', 'B. S. Grewal', 10, 'C-05', 3, 3),
('Operating System Concepts', 'Abraham Silberschatz', 2, 'A-14', 1, 2);

INSERT INTO issue (issue_date, due_date, return_date, student_id, admin_id, book_id) VALUES
('2026-09-01', '2026-09-15', NULL, 1, 1, 1),
('2026-09-05', '2026-09-19', '2026-09-18', 2, 1, 2),
('2026-09-10', '2026-09-24', NULL, 4, 2, 4),
('2026-08-20', '2026-09-03', NULL, 3, 1, 6);
