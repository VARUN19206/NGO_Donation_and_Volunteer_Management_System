# NGO Donation and Volunteer Management System

A web-based application designed to manage NGO campaigns, donations, and volunteers in one platform.

## Technologies Used

- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: MySQL

## Modules

1. **Authentication Module** – User registration, login, and role-based access.
2. **Campaign Management Module** – Create, view, and manage NGO campaigns.

## User Roles

- Donor
- Volunteer
- Campaign Admin
- Platform Admin

## How to Run the Project

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd ngo_donation_system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy `.env.example` and rename the copy to `.env`.

Update your MySQL database credentials and secret key in `.env`.

### 6. Initialize Database

```bash
python init_db.py
```

### 7. Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Project Status

Modules 1 and 2 are completed. Further modules will be developed incrementally.

## Author

Computer Science and Engineering Student