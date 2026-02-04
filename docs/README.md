# TTG Documentation Index

> **Quick Navigation:** Find the right documentation for your needs.

---

## 🎯 Executive Summaries (Root Level)

| Document                                              | Description                                                                             |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [SUPERVISOR_REPORT.md](../SUPERVISOR_REPORT.md)       | Executive summary - quick start guide                                                   |
| [SUPERVISOR_REPORT_M2.md](../SUPERVISOR_REPORT_M2.md) | **Milestone 2 detailed report** - architecture diagrams, demo commands, troubleshooting |
| [README.md](../README.md)                             | Main project README                                                                     |

---

## 📚 Documentation Categories

| Category                          | Purpose                             | Start Here              |
| --------------------------------- | ----------------------------------- | ----------------------- |
| [🏗️ Architecture](#-architecture) | System design & technical decisions | Queue architecture      |
| [📖 Guides](#-guides)             | How to use and operate the system   | Queue mode guide        |
| [🎓 Knowledge](#-knowledge)       | Concepts & tutorials for learning   | Kubernetes explained    |
| [📊 Results](#-results)           | Test results & verification reports | Fault tolerance results |
| [🚀 Setup](#-setup)               | Installation & deployment           | Local K8s setup         |
| [📈 Tracking](#-tracking)         | Project status & milestones         | Project tracker         |

---

## 🏗️ Architecture

_System design, technical decisions, and data flow documentation._

| Document                                                          | Description                                                               |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [M2_QUEUE_ARCHITECTURE.md](architecture/M2_QUEUE_ARCHITECTURE.md) | Redis Streams queue architecture, consumer groups, fault tolerance design |

---

## 📖 Guides

_Operational guides for using the system day-to-day._

| Document                                                | Description                                                          |
| ------------------------------------------------------- | -------------------------------------------------------------------- |
| [CONFIGURATION_GUIDE.md](guides/CONFIGURATION_GUIDE.md) | Environment variables, configuration options, tuning parameters      |
| [QUEUE_MODE_GUIDE.md](guides/QUEUE_MODE_GUIDE.md)       | Complete guide to queue mode operations, monitoring, troubleshooting |

---

## 🎓 Knowledge

_Educational content and tutorials for newcomers._

| Document                                                     | Description                                                     |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| [KIND_EXPLAINED.md](knowledge/KIND_EXPLAINED.md)             | Tutorial: What is Kind? How to use it for local K8s development |
| [KUBERNETES_EXPLAINED.md](knowledge/KUBERNETES_EXPLAINED.md) | Tutorial: Kubernetes concepts explained for beginners           |

---

## 📊 Results

_Test results, verification reports, and metrics._

| Document                                                                         | Description                                                     |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| [TEST_RESULTS_M1_PARALLEL_JOBS.md](results/TEST_RESULTS_M1_PARALLEL_JOBS.md)     | Milestone 1: Parallel jobs verification (v1.1.0)                |
| [TEST_RESULTS_M2_FAULT_TOLERANCE.md](results/TEST_RESULTS_M2_FAULT_TOLERANCE.md) | Milestone 2: Fault tolerance verification (100/100 chunks, 44s) |

---

## 🚀 Setup

_One-time installation and deployment guides._

| Document                                         | Description                             |
| ------------------------------------------------ | --------------------------------------- |
| [AZURE_AKS_GUIDE.md](setup/AZURE_AKS_GUIDE.md)   | Azure AKS deployment guide (production) |
| [KUBERNETES_SETUP.md](setup/KUBERNETES_SETUP.md) | Local Kubernetes setup with Kind        |

---

## 📈 Tracking

_Project management, milestones, and status tracking._

| Document                                                      | Description                                                                                                            |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| [PROJECT_STATUS_REPORT.md](tracking/PROJECT_STATUS_REPORT.md) | **Project Manager report** (M1+M2 complete) - also available as [.docx](tracking/TTG_Project_Status_Report_M1_M2.docx) |
| [PROJECT_OVERVIEW.md](tracking/PROJECT_OVERVIEW.md)           | High-level project overview, goals, and context                                                                        |
| [PROJECT_TRACKER.md](tracking/PROJECT_TRACKER.md)             | Milestone tracking, sprint status, deliverables                                                                        |

---

## 🔍 Quick Links by Role

### For New Team Members

1. Start with [KUBERNETES_EXPLAINED.md](knowledge/KUBERNETES_EXPLAINED.md) to understand K8s basics
2. Then read [KIND_EXPLAINED.md](knowledge/KIND_EXPLAINED.md) for local development
3. Follow [KUBERNETES_SETUP.md](setup/KUBERNETES_SETUP.md) to set up your environment

### For Operators

1. [QUEUE_MODE_GUIDE.md](guides/QUEUE_MODE_GUIDE.md) - Running the system
2. [CONFIGURATION_GUIDE.md](guides/CONFIGURATION_GUIDE.md) - Tuning and config
3. [TEST_RESULTS_M2_FAULT_TOLERANCE.md](results/TEST_RESULTS_M2_FAULT_TOLERANCE.md) - Expected behavior

### For Architects/Developers

1. [M2_QUEUE_ARCHITECTURE.md](architecture/M2_QUEUE_ARCHITECTURE.md) - System design
2. [PROJECT_OVERVIEW.md](tracking/PROJECT_OVERVIEW.md) - Project context
3. [PROJECT_TRACKER.md](tracking/PROJECT_TRACKER.md) - Current status

---

## 📁 Directory Structure

```
docs/
├── README.md                              # This file - Documentation index
│
├── architecture/                          # 🏗️ System Design
│   └── M2_QUEUE_ARCHITECTURE.md
│
├── guides/                                # 📖 Operational Guides
│   ├── CONFIGURATION_GUIDE.md
│   └── QUEUE_MODE_GUIDE.md
│
├── knowledge/                             # 🎓 Concepts & Tutorials
│   ├── KIND_EXPLAINED.md
│   └── KUBERNETES_EXPLAINED.md
│
├── results/                               # 📊 Test Results
│   ├── TEST_RESULTS_M1_PARALLEL_JOBS.md
│   └── TEST_RESULTS_M2_FAULT_TOLERANCE.md
│
├── setup/                                 # 🚀 Installation & Setup
│   ├── AZURE_AKS_GUIDE.md
│   └── KUBERNETES_SETUP.md
│
└── tracking/                              # 📈 Project Status
    ├── PROJECT_OVERVIEW.md
    └── PROJECT_TRACKER.md
```

---

_Last Updated: February 3, 2026_
