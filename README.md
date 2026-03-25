# GUIAug

An LLM-powered platform for **recording**, **replaying**, and **automatically augmenting** mobile GUI test scripts. GUIAug enables testers to record a single test script on a real device, then leverages large language models (GPT-4, Qwen) to intelligently mutate the script — generating a diverse set of new test cases that improve test coverage with minimal manual effort.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Features](#core-features)
  - [Script Recording](#1-script-recording)
  - [Intelligent Replay](#2-intelligent-replay)
  - [Script Mutation / Augmentation](#3-script-mutation--augmentation)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Running the Application](#running-the-application)

---

## Overview

GUIAug addresses the challenge of creating comprehensive mobile GUI test suites. Manually writing test scripts is time-consuming and often results in limited coverage. GUIAug solves this by:

1. **Recording** user interactions on a real Android or HarmonyOS device via a browser-based interface.
2. **Replaying** recorded scripts with intelligent widget matching that adapts to UI changes.
3. **Augmenting** scripts automatically through LLM-driven mutation — producing new test cases by varying input data and exploring alternative interaction paths.

The platform supports both **Android** (via ADB) and **HarmonyOS** devices.

---

## Architecture

GUIAug follows a decoupled frontend-backend architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│              Vue 3 + Naive UI + WebSocket                    │
│    Screen mirroring · Script management · Mutation UI        │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP / WebSocket
┌───────────────────────────▼──────────────────────────────────┐
│                     Backend (FastAPI)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │   Device     │  │   Record     │  │   Mutate            │ │
│  │  Controller  │  │  Controller  │  │  Controller         │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────────────┘ │
│         │                 │                  │                │
│  ┌──────▼─────────────────▼──────────────────▼──────────────┐│
│  │              Service Layer (Abstract + Impl)             ││
│  │  DeviceService · ScriptService · ImageService            ││
│  │  MutationService                                         ││
│  └──────────────────────────────────────────────────────────┘│
│         │                 │                  │                │
│  ┌──────▼──┐  ┌───────────▼───┐  ┌──────────▼─────────────┐ │
│  │  ADB /  │  │   MySQL       │  │  LLM APIs              │ │
│  │  HDC    │  │  (SQLAlchemy) │  │  (GPT-4 / Qwen)        │ │
│  └─────────┘  └───────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Vue 3, Naive UI, Axios, WebSocket | Device screen mirroring, script recording/replay UI, mutation interaction |
| **Backend** | FastAPI, Uvicorn | REST API & WebSocket server for device control, script management, mutation logic |
| **Database** | MySQL, SQLAlchemy, PyMySQL | Persistent storage for scripts and operations |
| **AI / LLM** | OpenAI GPT-4o/4.1, Alibaba Qwen (via DashScope) | Intent description, input mutation, path mutation, semantic matching, assertion verification |
| **Device Control** | ADB (Android), HDC (HarmonyOS) | Send commands to physical devices (tap, scroll, screenshot, UI dump) |
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
- **LLM-generated descriptions**: Automatically generate natural language descriptions for each operation step and an overall script summary using LLMs.

### 2. Intelligent Replay

Replay scripts with adaptive widget matching to handle UI layout changes across different runs:

The system uses a **three-tier matching strategy** (in priority order):

| Strategy | Method | Description |
|----------|--------|-------------|
| **Image Match** | SIFT + FLANN (OpenCV) | Finds the recorded widget image on the current screen using feature-based matching with homography validation |
| **Layout Match** | Edge detection + structural analysis | Analyzes the visual layout structure of both source and target screenshots to locate corresponding UI regions |
| **Semantic Match** | LLM vision model | Generates a natural language description of the target widget, then asks the LLM to identify the matching widget in a bounding-box-annotated screenshot |

Each match result is validated using `check_match_validity` to ensure spatial consistency before execution.

### 3. Script Mutation / Augmentation

The core innovation of GUIAug — automatically derive new test cases from a single recorded script:

#### 3.1 Input Data Mutation (`INPUT-DATA`)

Mutates text input operations using LLM-generated alternatives:

1. **Input type classification**: The LLM analyzes the script context to determine if each input is:
   - **Content-oriented**: Free-form text (e.g., comments, nicknames) — any value is acceptable
   - **Business-oriented**: Constrained input (e.g., phone numbers, search queries) — must follow specific rules

2. **Mutation generation**:
   - *Content-oriented*: Length variation, language variation, character variation (emojis, special characters)
   - *Business-oriented*: Rule-conforming mutations (valid alternatives) and rule-violating mutations (for testing validation logic)

3. **Assertion binding**: The LLM identifies which assertions are causally linked to the mutated input and automatically adjusts their expected outcomes to match the new input.

#### 3.2 Path Mutation (`PATH`)

Explores alternative interaction paths from a mutation point:

1. **Mutation point detection**: The LLM evaluates each tap operation in the script and scores its "branching value" — how likely it is that choosing a different action here would lead to interesting new behavior.

2. **Goal generation**: A test goal is generated for the mutated path based on the original script context.

3. **Autonomous exploration**: Starting from the mutation point, the LLM acts as a test agent:
   - Observes the current screen (annotated with bounding boxes and widget indices)
   - Decides the next action (tap, input, long press, back, or end)
   - Executes up to 10 new steps

4. **Assertion injection**: After exploration completes, the system automatically injects an assertion to verify the final state of the mutated path.

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
│       │   ├── device_service.py                #   Device interaction abstraction
│       │   ├── script_service.py                #   Script CRUD & recording logic
│       │   ├── image_service.py                 #   Image processing & widget matching
│       │   ├── mutation_service.py              #   Mutation logic abstraction
│       │   ├── dependence.py                    #   Dependency injection
│       │   └── implements/                      #   Concrete implementations
│       │       ├── device_service_impl_adb.py   #     ADB-based device control
│       │       ├── script_service_impl_adb.py   #     Script service for ADB devices
│       │       ├── image_service_impl.py        #     OpenCV + LLM image processing
│       │       └── mutation_service_impl_adb.py #     LLM-driven mutation engine
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
