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

-- Module 2 (Increment 2): Campaign Management
CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  title       VARCHAR(120) NOT NULL,
  description TEXT         NOT NULL,
  category    ENUM('education','food','health','shelter','other') NOT NULL DEFAULT 'other',
  goal_amount DECIMAL(12,2) NOT NULL,
  status      ENUM('active','closed') NOT NULL DEFAULT 'active',
  created_by  INT UNSIGNED NOT NULL,              -- the campaign admin who created it
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (campaign_id),
  KEY idx_campaigns_status (status),
  CONSTRAINT fk_campaigns_user FOREIGN KEY (created_by) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Module 3 (Increment 3): Donation Management
-- Donations are SIMULATED test transactions. No real payment gateway is used.
CREATE TABLE IF NOT EXISTS donations (
  donation_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  campaign_id     INT UNSIGNED  NOT NULL,
  donor_id        INT UNSIGNED  NOT NULL,
  amount          DECIMAL(12,2) NOT NULL,
  transaction_ref VARCHAR(20)   NOT NULL,          -- test reference such as TEST-1A2B3C4D5E
  created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (donation_id),
  UNIQUE KEY uq_donations_ref (transaction_ref),
  KEY idx_donations_campaign (campaign_id),
  KEY idx_donations_donor (donor_id),
  CONSTRAINT fk_donations_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id),
  CONSTRAINT fk_donations_donor FOREIGN KEY (donor_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Module 4 (Increment 4): Volunteer Management
CREATE TABLE IF NOT EXISTS tasks (
  task_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  campaign_id INT UNSIGNED NOT NULL,
  title       VARCHAR(120) NOT NULL,
  description TEXT         NOT NULL,
  due_date    DATE         NULL,
  assigned_to INT UNSIGNED NOT NULL,               -- the volunteer
  status      ENUM('pending','in_progress','completed') NOT NULL DEFAULT 'pending',
  created_by  INT UNSIGNED NOT NULL,               -- the admin who created it
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (task_id),
  KEY idx_tasks_assigned (assigned_to),
  KEY idx_tasks_campaign (campaign_id),
  CONSTRAINT fk_tasks_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id),
  CONSTRAINT fk_tasks_volunteer FOREIGN KEY (assigned_to) REFERENCES users (user_id),
  CONSTRAINT fk_tasks_creator FOREIGN KEY (created_by) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Extra: impact updates (where donations helped) with photo proof
CREATE TABLE IF NOT EXISTS campaign_updates (
  update_id   INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  campaign_id INT UNSIGNED  NOT NULL,
  title       VARCHAR(120)  NOT NULL,
  description TEXT          NOT NULL,
  amount_used DECIMAL(12,2) NULL,                  -- optional: how much was spent on this
  created_by  INT UNSIGNED  NOT NULL,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (update_id),
  KEY idx_updates_campaign (campaign_id),
  CONSTRAINT fk_updates_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id),
  CONSTRAINT fk_updates_creator FOREIGN KEY (created_by) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS update_images (
  image_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  update_id INT UNSIGNED NOT NULL,
  filename  VARCHAR(64)  NOT NULL,                 -- random name of the stored photo
  PRIMARY KEY (image_id),
  UNIQUE KEY uq_update_images_file (filename),
  KEY idx_update_images_update (update_id),
  CONSTRAINT fk_update_images_update FOREIGN KEY (update_id) REFERENCES campaign_updates (update_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One row per email attempt for an update (sent, saved to the outbox folder, or failed)
CREATE TABLE IF NOT EXISTS email_log (
  log_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  update_id  INT UNSIGNED NOT NULL,
  user_id    INT UNSIGNED NOT NULL,
  status     ENUM('sent','saved','failed') NOT NULL,
  error      VARCHAR(255) NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_email_log_update (update_id),
  CONSTRAINT fk_email_log_update FOREIGN KEY (update_id) REFERENCES campaign_updates (update_id),
  CONSTRAINT fk_email_log_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
