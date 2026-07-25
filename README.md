# QueueSmart — Smart Queue Management Application

QueueSmart is a smart queue management application designed to reduce wait-time frustration and give organizations better tools to manage demand. This document presents the initial design: the problem, key features, development approach, and a high-level system architecture.

---

## Table of Contents

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

The team will follow an **iterative, incremental development** process:

1. **Design (A1)** — problem definition, features, and architecture *(this document)*
2. **Core setup** — authentication, roles, and database schema
3. **Service & queue features** — service management and the queue engine
4. **Notifications & history** — alerts and usage tracking
5. **Testing & refinement** — validation against requirements

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML / CSS / JavaScript |
| Backend | Python / Flask |
| Database | In-memory for now (database in Assignment 4) |
| Authentication | Token-based auth |

---

## Team

| Name | Role |
|------|------|
| Vasavi Chenna|----------|
| Nehaa Balaji|-----------|
| Samuel Parsons|---------|
| Mahmoud Masoud|---------|
