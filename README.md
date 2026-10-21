# GUIAug

Implementation of the paper **“Semantics-Anchored GUI Test Script Augmentation via Input Variation and Branch Exploration.”** GUIAug treats an existing replayable GUI test script as a **seed script** and derives executable, seed-local variant test cases through **Script Interpretation**, **Input-Aware Augmentation**, and **Intent-Aware Augmentation**.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Features](#core-features)
  - [Script Recording](#1-script-recording)
  - [Intelligent Replay](#2-intelligent-replay)
  - [Semantics-Anchored GUI Test Script Augmentation](#3-semantics-anchored-gui-test-script-augmentation)
- [Project Structure](#project-structure)
- [Subject Apps](#subject-apps)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Running the Application](#running-the-application)

---

## Overview

GUIAug does not generate a complete test suite from scratch. It reuses the workflow, domain-specific inputs, GUI context, and assertions already encoded in a valid seed script, then expands the seed-local testing surface along input and path dimensions.

The current repository provides:

1. Recording and management of GUI operations and assertions.
2. Replay on a physical Android device using visual and layout evidence.
3. Script Interpretation that reconstructs operation descriptors, a scenario abstraction, and state/data/oracle dependencies.
4. Input-Aware Augmentation with semantic input variation and assertion rebinding.
5. Intent-Aware Augmentation with branch-point estimation, branch-goal formulation, runtime widget ranking, progress monitoring, and grounded assertion attachment.

The active backend implementation targets **Android through ADB**. Some HarmonyOS-oriented types and commented integration code remain as historical scaffolding, but they are not part of the active paper-aligned execution path.

---

## Architecture

GUIAug follows a decoupled frontend-backend architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│              Vue 3 + Naive UI + WebSocket                    │
│   Screen mirroring · Seed scripts · Augmentation controls    │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP / WebSocket
┌───────────────────────────▼──────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │   Device     │  │   Record     │  │   Mutate            │ │
│  │  Controller  │  │  Controller  │  │  Controller         │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬─────────────┘ │
│         │                 │                  │               │
│  ┌──────▼─────────────────▼──────────────────▼──────────────┐│
│  │              Service Layer (Abstract + Impl)             ││
│  │ DeviceService · ScriptService · ImageService             ││
│  │ MutationService: interpretation/input-aware/intent-aware ││
│  └──────────────────────────────────────────────────────────┘│
│         │                 │                  │               │
│  ┌──────▼──┐  ┌───────────▼───┐  ┌───────────▼────────────┐  │
│  │   ADB   │  │   MySQL       │  │  LLM APIs              │  │
│  │ Android │  │  (SQLAlchemy) │  │  (GPT-4.1 / Qwen)      │  │
│  └─────────┘  └───────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Vue 3, Naive UI, Axios, WebSocket | Device screen mirroring, script recording/replay UI, mutation interaction |
| **Backend** | FastAPI, Uvicorn | REST API & WebSocket server for device control, script management, mutation logic |
| **Database** | MySQL, SQLAlchemy, PyMySQL | Persistent storage for scripts and operations |
| **AI / LLM** | OpenAI-compatible GPT-4.1 and Qwen clients | Semantic interpretation, input variation, branch exploration, and assertion generation/evaluation |
| **Device Control** | ADB (Android) | Execute operations and capture screenshots/UI hierarchies on a physical device |
| **Image Processing** | OpenCV, PaddleOCR, Pillow | Widget matching (SIFT/FLANN), template matching, OCR, bounding box detection |

---

## Core Features

### 1. Script Recording

Record test scripts by interacting with a real device through the browser:

- **Screen mirroring**: Real-time device screen streaming via WebSocket using [minicap](https://github.com/nickoals/minicap).
- **Supported operations**: Tap, long press, scroll/swipe, text input, and assertion (oracle).
- **Automatic context capture**: For each operation, the system captures:
  - A full screenshot of the current screen
  - The UI layout tree (XML for Android, JSON for HarmonyOS)
  - A cropped image of the target widget
  - Widget metadata (bounding box, description, XPath)
  - Current package name and activity
- **Script management**: Create, rename, describe, insert/remove/edit operations, and discard scripts.
- **Seed semantics**: Generate natural-language operation descriptions and a script-level summary used by the Script Interpretation module.

### 2. Intelligent Replay

Replay scripts with adaptive widget matching to handle UI layout changes across different runs:

The system uses a **three-tier matching strategy** (in priority order):

| Strategy | Method | Description |
|----------|--------|-------------|
| **Image Match** | SIFT + FLANN (OpenCV) | Finds the recorded widget image on the current screen using feature-based matching with homography validation |
| **Layout Match** | Edge detection + structural analysis | Analyzes the visual layout structure of both source and target screenshots to locate corresponding UI regions |
| **Semantic Match** | LLM vision model | Generates a natural language description of the target widget, then asks the LLM to identify the matching widget in a bounding-box-annotated screenshot |

Each match result is validated using `check_match_validity` to ensure spatial consistency before execution.

### 3. Semantics-Anchored GUI Test Script Augmentation

The augmentation workflow follows the three modules described in the paper.

#### 3.1 Script Interpretation

Before augmentation, GUIAug lifts the flat seed trace into a semantic view:

- A sequential local descriptor for every operation, including description, inferred preconditions, expected effects, involved widgets, and references.
- A script-level scenario abstraction containing the interaction goal, important preconditions, reachable GUI states, and assertion targets.
- A lightweight typed dependency graph with **state**, **data**, and **oracle** edges. Invalid identifiers and backward temporal edges are filtered.
- Input positions and branch points used by the two downstream augmentation modules.
- A seed profile summarizing structural depth, input richness, and branchability.

The semantic view is persisted as `backend/data/scripts/<script_id>/semantic_view.json` and can be retrieved with `GET /mutate/semantic_view/{script_id}`.

#### 3.2 Input-Aware Augmentation (`INPUT-DATA`)

For each semantically meaningful text-input operation, GUIAug:

1. Infers the input role and constraint summary from the scenario abstraction, local descriptor, and downstream dependencies.
2. Generates normal, boundary, long, invalid, or domain-specific candidate values.
3. Creates direct-substitution scripts while preserving the seed prefix and suffix.
4. Rebinds assertions that depend on the changed input.
5. Persists augmentation provenance and the pending runtime outcome in `augmentation_context.json`.

The implementation retains the existing content-oriented/business-oriented classifier as the concrete value-generation strategy. Runtime replay can then determine whether the original suffix remains feasible; the persisted outcome metadata is designed for preserved, adapted, or terminal-negative continuations.

#### 3.3 Intent-Aware Augmentation (`PATH`)

For a retained branch point, GUIAug:

1. Reuses the seed prefix that reaches the branch context.
2. Formulates and persists a branch goal from the scenario abstraction, nearby dependencies, current GUI evidence, and reference suffix.
3. Extracts and ranks interactive widgets against the branch goal.
4. Generates one executable action at a time and validates its target/action preconditions before execution.
5. Monitors progress as `SATISFIED` or `ONGOING` under the bounded exploration budget.
6. Stops at the configured exploration budget and attaches an assertion grounded in the terminal screenshot and generated continuation.

Each derived script stores `augmentation_context.json`, including its seed script, source operation, goal, generated operations, status, and assertion evidence. Input-aware scripts can be replay-validated through `GET /mutate/input_complete/{script_id}/{device_id}`; infeasible original suffixes are replaced by one bounded adapted continuation and labeled `ALTERNATIVE`.

---

## Project Structure

```
GUIAug/
├── README.md
├── backend/
│   ├── main.py                                  # Application entry point
│   ├── requirements.txt                         # Python dependencies
│   ├── data/                                    # Runtime data storage
│   │   ├── screenshots/                         #   Device screenshots
│   │   ├── scripts/                             #   Recorded script artifacts (per-operation folders)
│   │   ├── ui_xml/                              #   UI layout dumps
│   │   └── temp/                                #   Temporary files (OCR, bbox images, etc.)
│   └── app/
│       ├── main.py                              # FastAPI app initialization & router registration
│       ├── prompt.py                            # LLM prompt templates (~800 lines)
│       ├── create_tables.py                     # Database table creation script
│       ├── controllers/                         # API endpoint definitions
│       │   ├── device_controller.py             #   Device operations (screen stream, tap, scroll)
│       │   ├── record_controller.py             #   Script recording & replay
│       │   └── mutate_controller.py             #   Script mutation & augmentation
│       ├── services/                            # Business logic (abstract interfaces)
│       │   ├── augmentation_artifacts.py         #   Semantic-view/context persistence and validation
│       │   ├── device_service.py                #   Device interaction abstraction
│       │   ├── script_service.py                #   Script CRUD & recording logic
│       │   ├── image_service.py                 #   Image processing & widget matching
│       │   ├── mutation_service.py              #   Mutation logic abstraction
│       │   ├── dependence.py                    #   Dependency injection
│       │   └── implements/                      #   Concrete implementations
│       │       ├── device_service_impl_adb.py   #     ADB-based device control
│       │       ├── script_service_impl_adb.py   #     Script service for ADB devices
│       │       ├── image_service_impl.py        #     OpenCV + LLM image processing
│       │       └── mutation_service_impl_adb.py #     Paper-aligned augmentation modules
│       ├── models/                              # Data models
│       │   ├── db_models.py                     #   SQLAlchemy ORM models (Script, Operation)
│       │   ├── schemas.py                       #   Pydantic schemas
│       │   └── device.py                        #   Device data model
│       ├── db/                                  # Database layer
│       │   ├── database.py                      #   Engine & session configuration
│       │   └── crud.py                          #   CRUD operations
│       └── utils/                               # Utilities
│           ├── llm.py                           #   LLM API client (OpenAI, Qwen)
│           ├── widget_extract.py                #   Widget extraction from UI trees
│           ├── logger.py                        #   Logging utility
│           ├── main.py                          #   Helper functions
│           └── ui/                              #   UI element detection (bounding boxes)
│               ├── detect.py
│               ├── detect_compo/
│               ├── detect_text/
│               └── detect_merge/
└── frontend/
    ├── package.json                             # Node.js dependencies
    ├── vue.config.js                            # Webpack configuration
    ├── babel.config.js                          # Babel configuration
    ├── public/                                  # Static assets
    └── src/
        ├── main.js                              # Vue app entry point
        ├── App.vue                              # Root component
        ├── api.js                               # Axios HTTP client (base URL: localhost:8000)
        ├── router/index.js                      # Vue Router configuration
        ├── store/index.js                       # Vuex state management
        └── components/
            └── Home.vue                         # Main UI component (~1000 lines)
```

---

## Subject Apps

The Android applications used as subjects in our experiments are available for download:

[**Download Subject Apps (Google Drive)**](https://drive.google.com/file/d/1iaUdI0auMUt44eggFGaIPW-oXPQGcpEz/view?usp=sharing)

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 16+ and npm
- **MySQL** 5.7+ (or compatible)
- **Android device** connected via USB with USB debugging enabled
- **ADB** (Android Debug Bridge) installed and available in PATH
- **[minicap](https://github.com/nickoals/minicap)** installed on the Android device (for screen streaming)
- **LLM API keys**: OpenAI API key and/or Alibaba DashScope API key (configured in `backend/app/utils/llm.py`)

### Backend Setup

1. **Create and activate a Conda environment:**

   ```bash
   conda create -n guiaug python=3.10
   conda activate guiaug
   ```

2. **Install Python dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure the database connection:**

   Edit `backend/app/db/database.py` and update the `DATABASE_URL` to match your MySQL setup:

   ```python
   DATABASE_URL = "mysql+pymysql://<user>:<password>@<host>:<port>/<database>"
   ```

4. **Create database tables:**

   ```bash
   cd backend
   python -m app.create_tables
   ```

5. **Configure LLM API keys:**

   Edit `backend/app/utils/llm.py` and set your API keys for OpenAI and/or Alibaba DashScope (Qwen).

### Frontend Setup

1. **Install Node.js dependencies:**

   ```bash
   cd frontend
   npm install
   ```

### Running the Application

1. **Connect your Android device** and verify it is detected:

   ```bash
   adb devices
   ```

2. **Start the backend server:**

   ```bash
   cd backend
   uvicorn app.main:app --reload
   # or
   python main.py
   ```

   The backend will be available at `http://localhost:8000`.

3. **Start the frontend dev server:**

   ```bash
   cd frontend
   npm run serve
   ```

   The frontend will be available at `http://localhost:8080`.

4. **Open** `http://localhost:8080` in your browser, select a connected device, and start recording or replaying test scripts.
