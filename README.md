# QueueSmart — Smart Queue Management Application

QueueSmart is a smart queue management application designed to reduce wait-time frustration and give organizations better tools to manage demand.

**Team:** Vasavi Chenna · Nehaa Balaji · Samuel Parsons · Mahmoud Masoud

---

## Getting started (everyone — do this once)

Flask and other Python packages are **not** stored in GitHub. Each teammate installs them locally.

### 1. Clone the repo

```bash
git clone https://github.com/nehaabalaji/Software-Design-Project.git
cd Software-Design-Project
```

### 2. Run setup

**Mac / Linux**

```bash
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
```

**Windows (Command Prompt)**

```bat
setup.bat
.venv\Scripts\activate.bat
```

If you see `No module named 'flask'`, the virtual environment is not active or setup was skipped. Run setup again, then activate `.venv` before `python run.py`.

### 3. Start the backend API

```bash
python run.py
```

API: [http://127.0.0.1:5000](http://127.0.0.1:5000)  
Health check: [http://127.0.0.1:5000/api/health](http://127.0.0.1:5000/api/health)

### 4. Open the frontend

Open these files in a browser (or use a simple static server):

- `index.html` / `login.html` / `register.html`
- `homescreen.html` (user)
- `admin.html` (admin)

Login/register UI now calls the live auth API under `/api/auth` (see below); the backend must be running for these pages to work.

### 5. Run tests

```bash
source .venv/bin/activate   # or .venv\Scripts\activate.bat on Windows
pytest -v
```

---

## What’s in this repo

| Area | Status | Where to work |
|------|--------|----------------|
| Frontend (HTML/CSS/JS) | Assignment 2 UI | `*.html`, `css/`, `js/` |
| Auth API | Assignment 3 — done | `app/auth.py`, `app/store.py`, `app/utils.py` |
| Services | Stub for team | `app/services.py` |
| Queues / wait time | Stub for team | `app/queues.py` |
| Notifications | Stub for team | `app/notifications.py` |
| History | Stub for team | `app/history.py` |
| Database | Next (Assignment 4) | Replace in-memory `InMemoryStore` |

### Wiring a new backend module

1. Implement the blueprint in the stub file (e.g. `app/queues.py`).
2. Register it in `app/__init__.py` (same pattern as auth).
3. Reuse `login_required` / `admin_required` from `app/utils.py`.
4. Store data on `InMemoryStore` in `app/store.py` until A4 adds a real database.

---

## Auth API (Assignment 3)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/auth/register` | Body: `email`, `password`, optional `role` (`User` or `Administrator`) |
| POST | `/api/auth/login` | Returns `token` |
| GET | `/api/auth/me` | Needs `Authorization: Bearer <token>` |
| POST | `/api/auth/logout` | Needs bearer token |

Password must be at least 8 characters. Data is in memory only while the server is running (no database yet).

Register example:

```json
{
  "email": "user@test.com",
  "password": "password123",
  "role": "User"
}
```

---

## Table of Contents (design)

- [Problem Statement](#problem-statement)
- [Proposed Solution](#proposed-solution)
- [Key Features](#key-features)
- [User Roles](#user-roles)
- [Application Requirements](#application-requirements)
- [System Architecture](#system-architecture)
- [Development Approach](#development-approach)
- [Technology Stack](#technology-stack)
- [Team](#team)

---

## Problem Statement

Many organizations — student service centers, clinics, advising offices, and help desks — struggle with long queues and poor visibility into wait times. Users often do not know how long they will wait, and staff have limited tools to manage demand efficiently.

QueueSmart addresses this by giving **users** real-time visibility into their queue position and estimated wait, and giving **administrators** the tools to create services, monitor queues, and improve service efficiency.

---

## Proposed Solution

QueueSmart is a web/mobile application that lets users join queues or book appointments, track their position and estimated wait time, and receive notifications as their turn approaches. Administrators can define services, manage queue priorities, and review usage statistics to make service delivery more efficient.

---

## Key Features

**For Users**
- Join a queue or book an appointment
- View current position and estimated wait time
- Receive notifications when their turn is approaching
- View personal queue participation history

**For Administrators**
- Create and manage services
- Monitor queues and set priorities
- View usage data and statistics to improve efficiency

---

## User Roles

| Role | Capabilities |
|------|--------------|
| **User** | Join/leave queues, view status and wait times, receive notifications, view history |
| **Administrator** | Create and manage services, manage queues and priorities, view usage data |

---

## Application Requirements

### 1. Login and Registration
- User and administrator registration
- Basic authentication via username/email and password
- Email verification *(design only)*

### 2. User Roles
- **User** — join queues, view status, receive notifications
- **Administrator** — create services, manage queues, view usage data

### 3. Service Management (Admin)
Administrators can create services and define:
- Service name and description
- Expected service duration
- Priority level (low / medium / high)

### 4. Queue Management
- Users can join or leave a queue
- Users can view current position and estimated wait time
- Queue ordering is based on **arrival time and priority**

### 5. Notifications
Users are notified when:
- They are close to being served
- Queue status changes

Notifications may be delivered by email or in-app *(design choice)*.

### 6. History
- Track user queue participation history
- Administrators can view basic usage statistics

---

## System Architecture

QueueSmart follows a three-tier client–server architecture:

```
┌─────────────────────────────────────────────┐
│                Client Layer                  │
│      (Web / Mobile UI — User & Admin)        │
│  Login · Queue View · Notifications · Admin  │
└───────────────────────┬─────────────────────┘
                        │  REST API / HTTPS
┌───────────────────────┴─────────────────────┐
│              Application Layer               │
│  Auth · Service Mgmt · Queue Engine ·        │
│  Notification Service · History/Analytics    │
└───────────────────────┬─────────────────────┘
                        │
┌───────────────────────┴─────────────────────┐
│                 Data Layer                   │
│   Database: Users · Services · Queues ·      │
│   Queue Entries · Notifications · History    │
└─────────────────────────────────────────────┘
```

**Core components**
- **Authentication Service** — registration, login, role management, email verification
- **Service Management** — CRUD for services, durations, and priority levels
- **Queue Engine** — handles join/leave, ordering by arrival time + priority, position and wait-time calculation
- **Notification Service** — triggers email/in-app alerts on turn approach and status changes
- **History & Analytics** — stores participation records and produces admin usage statistics

---

## Development Approach

The team follows an **iterative, incremental development** process:

1. **Design (A1)** — problem definition, features, and architecture
2. **Frontend (A2)** — UI screens for user and admin
3. **Backend auth (A3)** — Flask authentication API *(done)*
4. **Database (A4)** — data design and database implementation *(next)*
5. **Service & queue features** — service management and the queue engine
6. **Notifications & history** — alerts and usage tracking
7. **Testing & refinement** — validation against requirements

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML / CSS / JavaScript |
| Backend | Python / Flask |
| Database | In-memory store for now; real DB in Assignment 4 |
| Authentication | Token-based (`Authorization: Bearer <token>`) |

Dependencies are listed in `requirements.txt`. Install with `./setup.sh` or `setup.bat`.
| Frontend | HTML / CSS / JavaScript |
| Backend | Python / Flask |
| Database | In-memory for now (database in Assignment 4) |
| Authentication | Token-based auth |

---

## Team

| Name | Role |
|------|------|
| Vasavi Chenna |  |
| Nehaa Balaji |  |
| Samuel Parsons |  |
| Mahmoud Masoud |  |
