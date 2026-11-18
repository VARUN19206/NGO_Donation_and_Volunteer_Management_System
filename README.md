# NGO Donation and Volunteer Management System

## Module 1 – Database and User Authentication

A web-based NGO management application developed using:

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python Flask
- **Database:** MySQL

## Features

- User Registration and Login
- Password Hashing
- Role-Based Authentication
- Donor Account
- Volunteer Account
- Campaign Admin Account
- Platform Admin Account
- Secure Login Sessions
- CSRF Protection

## Requirements

Install the following software before running the project:

- Python 3
- MySQL Server
- Visual Studio Code

## Installation and Setup

### Step 1: Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

Open the downloaded project folder in VS Code.

### Step 2: Create a Virtual Environment

```bash
python -m venv venv
```

### Step 3: Activate Virtual Environment

For Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 5: Configure Environment Variables

Create a `.env` file:

```powershell
copy .env.example .env
```

Open `.env` and enter your MySQL credentials:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ngo_module1_auth_db

SECRET_KEY=your_generated_secret_key
```

Replace the example values with your own MySQL password and a secure random Flask secret key.

### Step 6: Initialize the Database

Make sure your MySQL server is running.

Execute:

```bash
python init_db.py
```

This creates the database, users table and four demo accounts.

### Step 7: Run the Application

```bash
python app.py
```

Open your browser:

http://127.0.0.1:5000

## Demo Login Credentials

Password for all demo accounts: `Demo@1234`

| Role | Email |
|---|---|
| Donor | donor@example.com |
| Volunteer | volunteer@example.com |
| Campaign Admin | campaign.admin@example.com |
| Platform Admin | platform.admin@example.com |

These accounts are for testing purposes only.

## Project Structure

```text
ngo_donation_system/
│
├── app.py
├── auth.py
├── config.py
├── db.py
├── init_db.py
├── schema.sql
├── requirements.txt
├── .env.example
├── .gitignore
│
├── templates/
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
└── tests/
```

## Run Tests

```bash
python -m unittest discover -s tests -v
```

## Security Notes

- Passwords are stored as secure hashes.
- Database credentials are stored in `.env`.
- The `.env` file must never be uploaded to GitHub.
- The virtual environment folder is excluded from GitHub.

## Development Methodology

This project follows the **Iterative and Incremental Development Model**.

The application is developed in small modules, tested and gradually integrated to build the complete system.

---

**Project:** NGO Donation and Volunteer Management System

**Module 1:** Database and User Authentication