import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Union
from app.utils.main import scroll_direction
from app.db.crud import *
from app.models.db_models import Operation
from app.models.schemas import ScriptModel, OperationModel
from app.services.script_service import ScriptService
from app.utils.llm import query
from app.utils.main import gen_step_id, timeit
from app.utils.widget_extract import HarmonyWidgetExtractor
from app.prompt import *


class HarmonyScriptServiceImpl(ScriptService):

    script_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "scripts"
    perf_path: Path = Path(__file__).parent.parent.parent.parent.resolve()
    extractor: HarmonyWidgetExtractor = HarmonyWidgetExtractor()
    widget_for_input: List[str] = ["SearchField", "TextInput", "TextArea", "RichEditor"]

    @timeit
    def init_script(self, db: Session, script_name: str, device_id: str, app_id: str, mutate_master: Optional[str] = None, mutating: bool = False) -> Dict[str, Any]:
        script_id = f"{int(time.time() * 1000)}"
        script_name = f"script-{script_id}" if script_name == "new_script" else script_name
        mutate_master = "" if mutate_master is None else mutate_master
        script = ScriptModel(
            script_id=script_id,
            script_name=script_name,
            device_id=device_id,
            app_id=app_id,
            script_folder=script_id,
            timestamp=datetime.now(),
            description="",
            mutate_ready=False,
            mutating=mutating,
            mutate_master=mutate_master,
        )
        db_script = create_script(db, script)
        script_folder = self.script_path / script_id
        script_folder.mkdir(parents=True)
        print(f"new script created: {script_id}")
        script_dict = {
            "script_id": db_script.script_id, "script_name": db_script.script_name,
            "device_id": db_script.device_id, "description": db_script.description,
            "mutate_ready": db_script.mutate_ready,
        }
        return script_dict

    @timeit
    def record_tap(
            self,
            db: Session,
            script_id: str,
            x: int,
            y: int,
            script_folder: str,
            screen_path: str,
            ui_dump_path: str,
            package: str,
            activity: str,
            op_prev: Optional[str],
            op_next: Optional[str],
            intent: str = ""
    ):
        step_id = gen_step_id(op_prev, op_next)
        script_folder = self.script_path / script_folder
        step_folder = script_folder / step_id
        step_folder.mkdir(exist_ok=True)
        shutil.move(screen_path, str(step_folder / "screen.jpeg"))
        shutil.move(ui_dump_path, str(step_folder / "ui_layout.json"))
        widget_path = step_folder / f"widget.jpeg"
        screen_path = step_folder / "screen.jpeg"
        ui_dump_path = step_folder / "ui_layout.json"
        widget_type, widget_desc, widget_bbox = self.extractor.extract(
            x, y, str(ui_dump_path), str(screen_path),
            str(widget_path), ["clickable"])

        tap_step = OperationModel(
            script_id=script_id,
            op_id=step_id,
            op_type="tap",
            op_params=json.dumps([x, y]),
            widget_bbox=str(widget_bbox),
            widget_desc=str(widget_desc),
            op_folder=step_id,
            timestamp=datetime.now(),
            package=package,
            activity=activity,
            intent=intent,
            mutate_type="NONE",
            mutate_reason="",
        )
        create_operation(db, tap_step)
        tap_step_dict = {
            "op_id": step_id, "op_params": [x, y],
            "op_type": "tap", "widget_desc": widget_desc,
            "package": package, "activity": activity,
            "op_folder": str(step_folder), "script_folder": str(script_folder),
            "widget_img": str(widget_path), "require_input": widget_type in self.widget_for_input
        }
        return tap_step_dict

    @timeit
    def record_scroll(
            self,
            db: Session,
            script_id: str,
            x1: int,
            y1: int,
            x2: int,
            y2: int,
            duration: int,
            script_folder: str,
            screen_path: str,
            ui_dump_path: str,
            package: str,
            activity: str,
            op_prev: Optional[str],
            op_next: Optional[str],
            intent: str = ""
    ):
        step_id = gen_step_id(op_prev, op_next)
        script_folder = self.script_path / script_folder
        step_folder = script_folder / step_id
        step_folder.mkdir(exist_ok=True)
        shutil.move(screen_path, str(step_folder / "screen.jpeg"))
        shutil.move(ui_dump_path, str(step_folder / "ui_layout.json"))
        widget_path = step_folder / "widget.jpeg"
        screen_path = step_folder / "screen.jpeg"
        ui_dump_path = step_folder / "ui_layout.json"
        _, widget_desc, widget_bbox = self.extractor.extract(
            (x1, x2), (y1, y2), str(ui_dump_path),
            str(screen_path), str(widget_path), ["scrollable"])

        scroll_step = OperationModel(
            script_id=script_id,
            op_id=step_id,
            op_type="scroll",
            op_params=json.dumps([x1, y1, x2, y2, duration]),
            widget_bbox=str(widget_bbox),
            widget_desc=str(widget_desc),
            op_folder=step_id,
            timestamp=datetime.now(),
            package=package,
            activity=activity,
            intent=intent,
            mutate_type="NONE",
            mutate_reason="",
        )
        create_operation(db, scroll_step)
        scroll_step_dict = {
            "op_id": step_id, "op_params": [x1, y1, x2, y2, duration],
            "op_type": "scroll", "widget_desc": widget_desc,
            "package": package, "activity": activity,
            "op_folder": str(step_folder), "script_folder": str(script_folder),
            "widget_img": str(widget_path), "require_input": False
        }
        return scroll_step_dict

    @timeit
    def record_long_press(
            self,
            db: Session,
            script_id: str,
            x: int,
            y: int,
            script_folder: str,
            screen_path: str,
            ui_dump_path: str,
            package: str,
            activity: str,
            op_prev: Optional[str],
            op_next: Optional[str],
            intent: str = ""
    ):
        step_id = gen_step_id(op_prev, op_next)
        script_folder = self.script_path / script_folder
        step_folder = script_folder / step_id
        step_folder.mkdir(exist_ok=True)
        shutil.move(screen_path, str(step_folder / "screen.jpeg"))
        shutil.move(ui_dump_path, str(step_folder / "ui_layout.json"))
        widget_path = step_folder / "widget.jpeg"
        screen_path = step_folder / "screen.jpeg"
        ui_dump_path = step_folder / "ui_layout.json"
        _, widget_desc, widget_bbox = self.extractor.extract(
            x, y, str(ui_dump_path), str(screen_path),
            str(widget_path), ["longClickable"])

        long_press_step = OperationModel(
            script_id=script_id,
            op_id=step_id,
            op_type="long_press",
            op_params=json.dumps([x, y]),
            widget_bbox=str(widget_bbox),
            widget_desc=json.dumps(widget_desc),
            op_folder=step_id,
            timestamp=datetime.now(),
            package=package,
            activity=activity,
            intent=intent,
            mutate_type="NONE",
            mutate_reason="",
        )
        create_operation(db, long_press_step)
        long_press_step_dict = {
            "op_id": step_id, "op_params": [x, y],
            "op_type": "long_press", "widget_desc": widget_desc,
            "package": package, "activity": activity,
            "op_folder": str(step_folder), "script_folder": str(script_folder),
            "widget_img": str(widget_path), "require_input": False
        }
        return long_press_step_dict

    @timeit
    def record_tap_input(
            self,
            db: Session,
            script_id: str,
            x: int,
            y: int,
            text: str,
            script_folder: str,
            screen_path: str,
            ui_dump_path: str,
            package: str,
            activity: str,
            op_prev: Optional[str],
            op_next: Optional[str],
            intent: str = ""
    ):
        step_id = gen_step_id(op_prev, op_next)
        script_folder = self.script_path / script_folder
        step_folder = script_folder / step_id
        step_folder.mkdir(exist_ok=True)
        shutil.move(screen_path, str(step_folder / "screen.jpeg"))
        shutil.move(ui_dump_path, str(step_folder / "ui_layout.json"))

        tap_input_step = OperationModel(
            script_id=script_id,
            op_id=step_id,
            op_type="tap_input",
            op_params=json.dumps([x, y, text]),
            widget_bbox=str((-1, -1, -1, -1)),
            widget_desc="",
            op_folder=step_id,
            timestamp=datetime.now(),
            package=package,
            activity=activity,
            intent=intent,
            mutate_type="NONE",
            mutate_reason="",
        )
        create_operation(db, tap_input_step)
        tap_input_step_dict = {
            "op_id": step_id, "op_params": [x, y, text],
            "op_type": "tap_input", "widget_desc": "",
            "package": package, "activity": activity,
            "op_folder": str(step_folder), "script_folder": str(script_folder),
            "widget_img": "", "require_input": False
        }
        return tap_input_step_dict

    @timeit
    def record_oracle(
            self,
            db: Session,
            script_id: str,
            script_folder: str,
            screen_path: str,
            assertion_info: Dict[str, Any],
            op_prev: Optional[str],
            op_next: Optional[str],
            intent: str = ""
    ):
        step_id = gen_step_id(op_prev, op_next)
        script_folder = self.script_path / script_folder
        step_folder = script_folder / step_id
        step_folder.mkdir(exist_ok=True)
        shutil.move(screen_path, str(step_folder / "screen.jpeg"))
        assert_param = {}
        if "text" in assertion_info.keys():
            assert_param["text"] = assertion_info["text"]
        else:
            raise Exception("Unknown assertion type")

        assert_step = OperationModel(
            script_id=script_id,
            op_id=step_id,
            op_type="assert",
            op_params=json.dumps(assert_param),
            widget_bbox=str((-1, -1, -1, -1)),
            widget_desc="",
            op_folder=step_id,
            timestamp=datetime.now(),
            package="",
            activity="",
            intent=intent,
            mutate_type="NONE",
            mutate_reason="",
        )
        create_operation(db, assert_step)
        # assert_step_dict = {
        #     "op_id": step_id, "op_params": assert_param,
        #     "op_type": "assert", "widget_desc": "",
        #     "package": "", "activity": "",
        #     "op_folder": str(step_folder), "script_folder": str(script_folder),
        #     "widget_img": str(widget_path) if "image" in assert_param.keys() else "",
        #     "require_input": False
        # }
        assert_step_dict = {
            "op_id": step_id, "op_params": assert_param,
            "op_type": "assert", "widget_desc": "",
            "package": "", "activity": "",
            "op_folder": str(step_folder), "script_folder": str(script_folder),
            "widget_img": "", "require_input": False
        }
        return assert_step_dict

    @timeit
    def remove_op_from_db(self, db: Session, op_id: str, script_id: str):
        script_folder = get_script_folder_from_op_id(db, op_id)
        op_folder = get_step_folder_from_id(db, op_id)
        op_folder = self.script_path / script_folder / op_folder
        if op_folder.exists() and op_folder.is_dir():
            shutil.rmtree(op_folder)
        delete_operation(db, op_id)

    @timeit
    def get_script(self, db: Session, script_id: str) -> Dict[str, Any]:
        script_dict = {}
        script, operations = get_script_with_operations(db, script_id)
        if script is not None:
            script_dict["script_id"] = script_id
            script_dict["script_name"] = script.script_name
            script_dict["description"] = script.description
            script_dict["device_id"] = script.device_id
            script_dict["app_id"] = script.app_id
            script_dict["timestamp"] = script.timestamp
            script_dict["script_folder"] = script.script_folder
            script_dict["mutating"] = script.mutating
            script_dict["mutate_master"] = script.mutate_master
            script_dict["operations"] = []

            for op in operations:
                op: Operation = op
                op_dict = {
                    "op_id": op.op_id,
                    "op_type": op.op_type,
                    "op_params": json.loads(op.op_params),
                    "widget_bbox": op.widget_bbox,
                    "widget_desc": op.widget_desc,
                    "package": op.package,
                    "activity": op.activity,
                    "op_folder": op.op_folder,
                    "intent": op.intent,
                    "timestamp": op.timestamp,
                    "mutate_type": op.mutate_type,
                    "mutate_reason": op.mutate_reason,
                }
                script_dict["operations"].append(op_dict)
        return script_dict

    @timeit
    def get_script_path(self):
        return self.script_path

    @timeit
    def get_scripts(self, db: Session):
        scripts = get_all_scripts(db)
        script_list = [{"id": script.script_id, "name": script.script_name} for script in scripts]
        return script_list

    @timeit
    def delete_script(self, db: Session, script_id: str):
        script_folder = get_script_folder_from_id(db, script_id)
        script_folder = self.script_path / script_folder
        if script_folder.exists() and script_folder.is_dir():
            shutil.rmtree(script_folder)
        delete_script(db, script_id)

    @timeit
    def copy_script_from_id(self, db: Session, script_id_old: str):
        device_id, app_id = get_device_app_from_id(db, script_id_old)
        new_script = self.init_script(db, "new_script", device_id, app_id)
        script_id_new = new_script["script_id"]
        script_folder_old = get_script_folder_from_id(db, script_id_old)
        script_folder_new = get_script_folder_from_id(db, script_id_new)
        _, operations = get_script_with_operations(db, script_id_old)

        for op in operations:
            op: Operation = op
            op_id_new = gen_step_id(None, None)
            op_folder_old = self.script_path / script_folder_old / op.op_folder
            op_folder_new = self.script_path / script_folder_new / op_id_new
            op_folder_new.mkdir(parents=True)
            shutil.copytree(op_folder_old, op_folder_new, dirs_exist_ok=True)

            op_new = OperationModel(
                script_id=script_id_new,
                op_id=op_id_new,
                op_type=op.op_type,
                op_params=op.op_params,
                widget_bbox=op.widget_bbox,
                widget_desc=op.widget_desc,
                op_folder=op.op_folder,
                timestamp=datetime.now(),
                package=op.package,
                activity=op.activity,
                intent=op.intent,
                mutate_type="NONE",
                mutate_reason="",
            )
            create_operation(db, op_new)
        return script_id_new

    @timeit
    def update_op_params(self, db: Session, op_id: str, params: List[Union[int, str]]):
        update_operation_params(db, op_id, json.dumps(params))

    def abstract_operation(self, op_dict: Dict[str, Any], script_folder: str, prev_ops: List[Dict[str, Any]]) -> str:
        if op_dict["op_type"] != "assert":
            op_folder = op_dict["op_folder"]
            screenshot_path = self.script_path / script_folder / op_folder / "screen.jpeg"
            widget_img_path = self.script_path / script_folder / op_folder / "widget.jpeg"
            prompt = operation_intent_generate_prompt.replace(
                "{PREVIOUS-OPERATIONS}",
                "None" if len(prev_ops) == 0 else "->".join(item["op_intent"] for item in prev_ops)
            ).replace(
                "{OPERATION-TYPE}",
                "input" if op_dict["op_type"] == "tap_input" else op_dict["op_type"]
            ).replace(
                "{INPUT-TEXT}",
                op_dict["op_params"][2] if op_dict["op_type"] == "tap_input" else ""
            )
            usr_msg_img = str(screenshot_path) if not widget_img_path.exists() \
                else [str(screenshot_path), str(widget_img_path)]
            result, _, _, _, _ = query(user_msg_txt=prompt, user_msg_img=usr_msg_img)
            return result["result"]
        else:
            assertion_params = op_dict["op_params"]
            return assertion_params["text"]

    def describe_script_in_natural_language(self, db: Session, script_id: str):
        script_dict = self.get_script(db, script_id)
        script_folder = script_dict["script_folder"]
        abstracted_ops = []
        for op_dict in script_dict["operations"]:
            op_id, op_folder = op_dict["op_id"], op_dict["op_folder"]
            op_intent = self.abstract_operation(op_dict, script_folder, abstracted_ops)
            print(op_intent)
            update_operation_intent(db, op_id, op_intent)
            abstracted_ops.append({
                "op_id": op_id, "op_folder": op_folder, "op_type": op_dict["op_type"],
                "op_intent": op_intent, "op_params": op_dict["op_params"],
            })
        prompt = script_intent_generate_prompt.replace(
            "{OPERATION-INTENTS}",
            "\n".join(f"{i + 1}. " + item["op_intent"] for i, item in enumerate(abstracted_ops))
        )
        result, _, _, _, _ = query(user_msg_txt=prompt)
        update_script_description(db, script_id, result["result"])

    def abstract_operation_scenario(self, op_dict: Dict[str, Any], script_folder: str, prev_ops: List[Dict[str, Any]]) -> str:
        op_folder = op_dict["op_folder"]
        screenshot_path = self.script_path / script_folder / op_folder / "screen.jpeg"
        widget_img_path = self.script_path / script_folder / op_folder / "widget.jpeg"
        prev_ops_str = "None" if len(prev_ops) == 0 else "->".join(item["op_intent"] for item in prev_ops)
        sys_msg = """
            You will be provided with the following materials:
            - a JSON object containing basic information of a GUI test operation
            - a list of all the prerequisite operations before the operation
            - a picture of screenshot captured just before the operation is executed
            - a picture of the target widget of the operation (optional)
            Your task is to abstract the GUI test operation in brief language, describing the action and intent based on the provided materials.
            General style guidelines:
            - Use short, user-centric phrasing (avoid technical ids/coordinates unless required).
            - Combine action + target + intent.
            - Return ONLY a JSON response of the form: {"result": "..."} (no extra fields).
            Special rules by operation type:
            - If the operation type is "tap":
              - If the target is one item among similar items (e.g., an article, a news, a song, a book), abstract the object by generalizing it, and don't keep specific names or labels.
                Example: "tap the book named 'Jane Eyre'" → "tap a book in the bookshelf page".
              - If the target is a functional widget (e.g., submit button, favorite icon, settings tab), don't abstract. Keep the functional meaning explicit.
                Example: "tap the submit button to submit your personal configration".
            - If the operation type is "scroll", the result MUST include the scroll direction and distance. 
              eg.: "scroll down to load more items (distance: 600)".
            - For other types (e.g., input), keep their essential parameters (e.g., the input text).

            Examples:
            - tap the heart button to favorite the article
            - tap an email in the inbox to open its details
            - input "pizza" to search for food information
            - scroll down in the product list to load more results (distance: 500)
            - press the enter key  
            - tap the play bar at the bottom to check the detail of the song 

            Return a JSON response: { "result": "..." }

        """
        op_prompt_dict = {"id": op_dict["op_id"], "type": op_dict["op_type"]}
        if op_dict["op_type"] == "tap_input":
            op_prompt_dict["type"] = "input"
            op_prompt_dict["value"] = op_dict["op_params"][2]
        elif op_dict["op_type"] == "scroll":
            x1, y1, x2, y2, _ = op_dict["op_params"]
            direction, distance = scroll_direction(x1, y1, x2, y2)
            value = f"direction:{direction};distance: {distance}"
            op_prompt_dict["value"] = value
        elif op_dict["op_type"] == "assert":
            op_prompt_dict["value"] = op_dict["op_params"]["text"]

        if op_dict["widget_desc"] is not None and op_dict["widget_desc"] != "":
            op_prompt_dict["widget"] = op_dict["widget_desc"]
        usr_msg_txt = (
            f"a GUI test operation in JSON format: ```{json.dumps(op_prompt_dict)}```\n\n"
            f"a list of all the prerequisite operations: ```{prev_ops_str}```"
        )
        usr_msg_img = str(screenshot_path) if not widget_img_path.exists() \
            else [str(screenshot_path), str(widget_img_path)]
        result, _, _, _, _ = query(user_msg_txt=usr_msg_txt, user_msg_img=usr_msg_img, system_msg=sys_msg)
        return result["result"]

    def show_script(self, db: Session, script_id: str):
        script_dict = self.get_script(db=db, script_id=script_id)
        script_str = "\n".join(f"[{i}] {op['intent']}" for i, op in enumerate(script_dict["operations"], start=1))
        print(script_str)
        return script_str
