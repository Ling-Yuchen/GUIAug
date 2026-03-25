### Code Structure

- **app/** — Backend source code

    - **controllers/** — API endpoint definitions and implementations (interfacing with the frontend)

        - `device_controller.py` — Physical device operations
        - `record_controller.py` — Script recording and replay operations
        - `mutate_controller.py` — Script augmentation / mutation operations

    - **services/** — Service interface definitions and implementations

        - `device_service.py` — Physical device operations
        - `image_service.py` — Image processing operations
        - `script_service.py` — Script recording and replay operations
        - `mutation_service.py` — Script augmentation / mutation operations
        - **implements/** — Concrete implementations of the service interfaces

    - **db/** — Database connection and database operations

    - **models/** — Data structure definitions

    - **utils/** — Utility functions including Java function calls and widget extraction

    - `create_tables.py` — Creates database tables based on the defined schema

- `main.py` — FastAPI application entry point

- **data/** — Stores data recorded during script recording, such as screenshots, widget images, layout files, etc.
```text
 ├─log
 ├─screenshots
 ├─scripts
 ├─temp
  ├─ip
  ├─merge
  ├─ocr
  ├─draw
 ├─ui_xml
```

### Environment Setup

- `conda create -n guiaug python=3.10`
- `conda activate guiaug`
- `pip install -r requirements.txt`

- Run `create_tables.py` to create the database tables

### Starting the Backend

- Connect a device and make sure `adb devices` can detect it
- Run the following command from the project root: `uvicorn app.main:app --reload` or `python main.py`
