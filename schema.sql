-- NGO Donation and Volunteer Management System
-- Module 1 (Increment 1): Database and User Authentication
-- Works on MySQL 5.7+, MySQL 8 and MariaDB 10.x

CREATE DATABASE IF NOT EXISTS ngo_donation_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ngo_donation_db;

-- One table for every person who can log in.
-- Roles follow the approved PPT: Donor, Volunteer, Campaign Admin, Platform Admin.
CREATE TABLE IF NOT EXISTS users (
  user_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,            -- salted hash, never the real password
  role          ENUM('donor','volunteer','campaign_admin','platform_admin')
                NOT NULL DEFAULT 'donor',
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
