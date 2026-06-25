# GUIAug Backend

The backend implements the paper’s seed-based GUI test script augmentation workflow on physical Android devices. Its active execution path uses FastAPI, SQLAlchemy/MySQL, ADB, image/layout matching, and an OpenAI-compatible LLM client.

## Paper-aligned modules

### Script Interpretation

`MutationServiceImpl.prepare` converts a seed script from a flat operation sequence into a semantic view:

- operation-level descriptors: description, preconditions, expected effects, involved widgets, and references;
- scenario abstraction: interaction goal, preconditions, reachable GUI states, and assertion targets;
- typed dependency graph: `state`, `data`, and `oracle` edges;
- augmentation opportunities: input positions and scored branch points.
- seed profile: structural depth, input richness, and branchability.

The result is stored at:

```text
data/scripts/<script_id>/semantic_view.json
```

Relevant endpoints:

```text
GET /mutate/prepare/{script_id}
GET /mutate/semantic_view/{script_id}
GET /mutate/semantic_view/{script_id}?refresh=true
```

### Input-Aware Augmentation

For an `INPUT-DATA` operation, the backend infers the input role and constraints, generates semantically varied candidates, and rebinds dependent assertions. The existing content-oriented/business-oriented classifier is retained as the concrete generation strategy.

Candidate metadata includes:

- `value`
- `category`
- `rationale` (`reason`)
- `expected_effect`
- `input_role`
- `constraint_summary`
- assertion bindings

The original frontend-compatible response remains available:

```text
GET /mutate/input_data/{script_id}/{op_id}
```

The structured response is available with:

```text
GET /mutate/input_data/{script_id}/{op_id}?detailed=true
```

Derived scripts store provenance and runtime-validation state in:

```text
data/scripts/<derived_script_id>/augmentation_context.json
```

Replay validation and suffix adaptation are triggered with:

```text
GET /mutate/input_complete/{derived_script_id}/{device_id}
```

If the original suffix remains feasible, the outcome is `POSITIVE`. Otherwise, the backend synthesizes one bounded adapted continuation and records the outcome as `ALTERNATIVE`.

### Intent-Aware Augmentation

For a `PATH` branch point, the backend:

1. copies the validated seed prefix;
2. retrieves the persisted branch goal;
3. replays the prefix to restore the branch context;
4. ranks current widgets against the goal and reference suffix;
5. validates each generated action before execution;
6. monitors progress as `SATISFIED` or `ONGOING`;
7. stops on goal satisfaction, an invalid generated action, or the exploration budget;
8. attaches an assertion grounded in the terminal screenshot and generated continuation.

The augmentation context records the seed script, source operation, branch goal, generated operations, completion status, and assertion evidence.

## Code structure

```text
app/
├── controllers/
│   ├── device_controller.py
│   ├── record_controller.py
│   └── mutate_controller.py
├── services/
│   ├── augmentation_artifacts.py
│   ├── device_service.py
│   ├── image_service.py
│   ├── mutation_service.py
│   ├── script_service.py
│   └── implements/
│       ├── device_service_impl_adb.py
│       ├── image_service_impl.py
│       ├── mutation_service_impl_adb.py
│       └── script_service_impl_adb.py
├── db/
├── models/
├── utils/
├── prompt.py
└── create_tables.py
```

Runtime artifacts:

```text
data/
├── log/
├── screenshots/
├── scripts/
│   └── <script_id>/
│       ├── <operation_id>/
│       │   ├── screen.jpeg
│       │   ├── widget.jpeg
│       │   └── ui_layout.xml
│       ├── semantic_view.json
│       └── augmentation_context.json
├── temp/
└── ui_xml/
```

## Environment setup

```bash
conda create -n guiaug python=3.10
conda activate guiaug
pip install -r requirements.txt
```

Configure:

- `DATABASE_URL` in `app/db/database.py`;
- the OpenAI-compatible API client in `app/utils/llm.py`;
- an Android device visible through `adb devices`.

Create the database tables:

```bash
python -m app.create_tables
```

Start the backend from the `backend` directory:

```bash
uvicorn app.main:app --reload
# or
python main.py
```

The active implementation is Android/ADB-based. HarmonyOS-related types and commented code are retained only as inactive scaffolding.
