import json
import asyncio
import math
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.crud import update_script_mutate, update_script_name, update_script_desc
from app.db.database import get_db
from app.services.device_service import DeviceService
from app.services.image_service import ImageService
from app.services.script_service import ScriptService
from app.utils.main import get_img_shape, cal_iou, cal_overlap_rate, timeit
from app.utils.widget_extract import HarmonyWidgetExtractor, AndroidWidgetExtractor
from app.services.dependence import get_device_service, get_image_service, get_script_service


class RecordController:

    def __init__(self):
        self.extractor: HarmonyWidgetExtractor = HarmonyWidgetExtractor()
        self.extractor2: AndroidWidgetExtractor = AndroidWidgetExtractor()
        self.router = APIRouter()
        # script api
        self.router.add_api_route("/record/scripts", self.get_script_list, methods=["GET"])
        self.router.add_api_route("/record/script/{script_name}/{device_id}/{app_id}", self.create_script, methods=["GET"])
        self.router.add_api_route("/record/script_op_list/{script_id}", self.get_script_with_operation_list, methods=["GET"])
        self.router.add_api_route("/record/discard/{script_id}", self.record_discard, methods=["GET"])
        self.router.add_api_route("/record/update_name/{new_name}/{script_id}", self.update_script_name, methods=["GET"])
        self.router.add_api_route("/record/update_desc/{new_desc}/{script_id}", self.update_script_description, methods=["GET"])
        self.router.add_api_route("/record/generate_intent/{script_id}", self.describe_script, methods=["GET"])
        # app dump api
        self.router.add_api_route("/record/dump/{device_id}/{wait}", self.dump_app_state, methods=["GET"])
        # op change api
        self.router.add_api_route("/record/remove_operation/{script_id}/{step_id}", self.record_remove, methods=["GET"])
        self.router.add_api_route("/record/update_params/{script_id}/{step_id}", self.update_op_params, methods=["GET"])
        # op creation api
        self.router.add_api_route("/record/tap/{script_id}/{x}/{y}/{device_id}/{op_prev}/{op_next}", self.record_tap, methods=["GET"])
        self.router.add_api_route("/record/tap_input/{script_id}/{x}/{y}/{text}/{device_id}/{op_prev}/{op_next}", self.record_tap_input, methods=["GET"])
        self.router.add_api_route("/record/long_press/{script_id}/{x}/{y}/{device_id}/{op_prev}/{op_next}", self.record_long_press, methods=["GET"])
        self.router.add_api_route("/record/scroll/{script_id}/{x1}/{y1}/{x2}/{y2}/{device_id}/{duration}/{op_prev}/{op_next}", self.record_scroll, methods=["GET"])
        self.router.add_api_route("/record/oracle/{script_id}/{device_id}/{op_prev}/{op_next}", self.record_oracle, methods=["GET"])
        # replay api
        self.router.add_api_route("/record/replay/{script_id}/{device_id}", self.replay_operation_harmony, methods=["GET"])

        self.app_state = {"screenshot": "", "ui_structure": "", "package": "", "activity": "", "require_input": False}

    async def describe_script(self, script_id: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        script_service.describe_script_in_natural_language(db, script_id)

    async def update_op_params(self, script_id: str, step_id: str, params: str = Query(None), db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        if params is None:
            return "no params for update"
        params_list = json.loads(params)["params"]
        script_service.update_op_params(db, step_id, params_list)
        update_script_mutate(db, script_id, False)

    async def get_script_list(self, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        return script_service.get_scripts(db)

    async def create_script(self, script_name: str, device_id: str, app_id: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        return script_service.init_script(db, script_name, device_id, app_id)

    async def update_script_name(self, new_name: str, script_id: str, db: Session = Depends(get_db)):
        update_script_name(db, script_id, new_name)

    async def update_script_description(self, new_desc: str, script_id: str, db: Session = Depends(get_db)):
        update_script_desc(db, script_id, new_desc)

    @timeit
    async def dump_app_state(self, device_id: str, wait: str, image_service: ImageService = Depends(get_image_service), device_service: DeviceService = Depends(get_device_service)):
        if wait == "true":
            await asyncio.sleep(2)
        ui_dump_path = device_service.get_ui_structure(device_id)
        screen_path = device_service.get_screenshot(device_id)
        package, activity = device_service.get_current_app_message(device_id)
        self.app_state["screenshot"] = screen_path
        self.app_state["ui_structure"] = ui_dump_path
        self.app_state["package"] = package
        self.app_state["activity"] = activity
        return image_service.get_image_base64(screen_path, 450, 250)

    @timeit
    async def record_tap(self, script_id: str, x: int, y: int, device_id: str, op_prev: str, op_next: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        op_next = None if op_next == "None" else op_next
        op_prev = None if op_prev == "None" else op_prev
        print("start recording tap operation ...")
        print(f"params received: {script_id} & ({x}, {y}) & {device_id}")
        ui_dump_path = self.app_state["ui_structure"]
        screen_path = self.app_state["screenshot"]
        package = self.app_state["package"]
        activity = self.app_state["activity"]
        op_desc_dict = script_service.record_tap(db, script_id, x, y, script_id, screen_path, ui_dump_path, package, activity, op_prev, op_next)
        op_desc_dict["widget_img"] = image_service.get_image_base64(op_desc_dict["widget_img"], 50, 150)
        return op_desc_dict

    @timeit
    async def record_tap_input(self, script_id: str, x: int, y: int, text: str, device_id: str, op_prev: str, op_next: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        op_next = None if op_next == "None" else op_next
        op_prev = None if op_prev == "None" else op_prev
        print("start recording tap input operation ...")
        print(f"params received: {script_id} & ({x}, {y}, {text}) & {device_id}")
        ui_dump_path = self.app_state["ui_structure"]
        screen_path = self.app_state["screenshot"]
        package = self.app_state["package"]
        activity = self.app_state["activity"]
        op_desc_dict = script_service.record_tap_input(db, script_id, x, y, text, script_id, screen_path, ui_dump_path, package, activity, op_prev, op_next)
        op_desc_dict["widget_img"] = image_service.get_image_base64(op_desc_dict["widget_img"], 50, 200)
        return op_desc_dict

    @timeit
    async def record_scroll(self, script_id: str, x1: int, y1: int, x2: int, y2: int, device_id: str, duration: int, op_prev: str, op_next: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        op_next = None if op_next == "None" else op_next
        op_prev = None if op_prev == "None" else op_prev
        print("start recording scroll operation ...")
        print(f"params received: {script_id} & ({x1}, {y1}), ({x2}, {y2}) & {device_id} & {duration}ms")
        ui_dump_path = self.app_state["ui_structure"]
        screen_path = self.app_state["screenshot"]
        package = self.app_state["package"]
        activity = self.app_state["activity"]
        op_desc_dict = script_service.record_scroll(db, script_id, x1, y1, x2, y2, duration, script_id, screen_path, ui_dump_path, package, activity, op_prev, op_next)
        op_desc_dict["widget_img"] = image_service.get_image_base64(op_desc_dict["widget_img"], 50, 200)
        self.app_state["require_input"] = False
        return op_desc_dict

    @timeit
    async def record_oracle(self, script_id: str, device_id: str, op_prev: str, op_next: str, params: str = Query(None), db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        if params is None:
            return "no params for oracle record"
        params: dict = json.loads(params)
        if "text" not in params.keys():
            return "no valid params for oracle record"

        op_next = None if op_next == "None" else op_next
        op_prev = None if op_prev == "None" else op_prev
        print("start recording test oracle ...")
        print(f"params received: {script_id} & ({params}) & {device_id}")
        assertion_info = {"text": params["text"]}  # 用自然语言描述当前页面应当满足的条件/状态
        screen_path = self.app_state["screenshot"]
        op_desc_dict = script_service.record_oracle(db, script_id, script_id, screen_path, assertion_info, op_prev, op_next)
        op_desc_dict["widget_img"] = image_service.get_image_base64(op_desc_dict["widget_img"], 50, 200)
        self.app_state["require_input"] = False
        return op_desc_dict

    @timeit
    async def record_long_press(self, script_id: str, x: int, y: int, device_id: str, op_prev: str, op_next: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        op_next = None if op_next == "None" else op_next
        op_prev = None if op_prev == "None" else op_prev
        print("start recording long press operation ...")
        print(f"params received: {script_id} & ({x}, {y}) & {device_id}")
        ui_dump_path = self.app_state["ui_structure"]
        screen_path = self.app_state["screenshot"]
        package = self.app_state["package"]
        activity = self.app_state["activity"]
        op_desc_dict = script_service.record_long_press(db, script_id, x, y, script_id, screen_path, ui_dump_path, package, activity, op_prev, op_next)
        op_desc_dict["widget_img"] = image_service.get_image_base64(op_desc_dict["widget_img"], 50, 200)
        self.app_state["require_input"] = False
        return op_desc_dict

    async def record_remove(self, script_id: str, step_id: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        script_service.remove_op_from_db(db, step_id, script_id)
        update_script_mutate(db, script_id, False)

    async def record_discard(self, script_id: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service)):
        script_service.delete_script(db, script_id)

    async def get_script_with_operation_list(self, script_id: str, db: Session = Depends(get_db), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service)):
        time.sleep(0.2)
        script = script_service.get_script(db, script_id)
        script_folder = script_service.get_script_path() / script["script_folder"]
        for operation in script["operations"]:
            op_folder = script_folder / operation["op_folder"]
            widget_path = str(op_folder / "widget.jpeg")
            widget_base64 = image_service.get_image_base64(widget_path, 50, 200)
            operation["widget_img"] = widget_base64
            operation["script_folder"] = script["script_folder"]
        return script

    @timeit
    async def replay_operation_harmony(self, script_id: str, device_id: str, op_str: str = Query(None), script_service: ScriptService = Depends(get_script_service), image_service: ImageService = Depends(get_image_service), device_service: DeviceService = Depends(get_device_service)):
        if op_str is None:
            return "no operation for replay"

        wait_count = 0
        layout1 = device_service.get_ui_structure(device_id, False)
        await asyncio.sleep(1)
        layout2 = device_service.get_ui_structure(device_id, False)
        while layout1 != layout2 and wait_count < 4:
            wait_count += 1
            await asyncio.sleep(1)
            layout1 = layout2
            layout2 = device_service.get_ui_structure(device_id, False)

        op = json.loads(op_str)
        script_folder = script_service.get_script_path() / op["script_folder"]
        op_folder = script_folder / op["op_folder"]
        widget_path = str(op_folder / "widget.jpeg")
        screen_path_src = str(op_folder / "screen.jpeg")
        screen_path_dst = device_service.get_screenshot(device_id)

        if op["op_type"] == "tap" or op["op_type"] == "long_press":
            print("op_folder: ", op_folder)
            x, y = op["op_params"][0], op["op_params"][1]
            xr, yr, match_strategy = None, None, None
            x1, y1, _ = image_service.widget_image_match(screen_path_dst, widget_path)
            print(f"widget match (image): {x1}, {y1}")
            image_match_valid = image_service.check_match_validity((x, y), (x1, y1), screen_path_src, screen_path_dst)
            if not image_match_valid:
                image_match_valid = image_service.check_match_validity((x, y), (x1, y1), screen_path_src, screen_path_dst, mode="rectangle")
            if image_match_valid:
                xr, yr, match_strategy = x1, y1, "image"
            else:
                x2, y2, _ = image_service.widget_layout_match(screen_path_src, screen_path_dst, x, y)
                print(f"widget match (layout): {x2}, {y2}")
                layout_match_valid = image_service.check_match_validity((x, y), (x2, y2), screen_path_src, screen_path_dst)
                if layout_match_valid:
                    xr, yr, match_strategy = x2, y2, "layout"
                else:
                    x4, y4, _ = image_service.widget_semantic_match(screen_path_src, screen_path_dst, widget_path)
                    print(f"widget match (semantic): {x4}, {y4}")
                    if x4 is not None and y4 is not None:
                        xr, yr, match_strategy = x4, y4, "semantic"
                    else:
                        if x2 is not None and y2 is not None:
                            xr, yr, match_strategy = x2, y2, "layout"
                        elif x1 is not None and y1 is not None:
                            xr, yr, match_strategy = x1, y1, "image"
                        # if x1 is not None and y1 is not None:
                        #     xr, yr, match_strategy = x1, y1, "image"
                        # elif x2 is not None and y2 is not None:
                        #     xr, yr, match_strategy = x2, y2, "layout"

            if xr is None or yr is None:
                print(f"replay failed: {op['op_id']}-{op['op_type']}")
                return f"replay failed: {op['op_id']}-{op['op_type']}"

            if op["op_type"] == "tap":
                device_service.perform_click(device_id, xr, yr)
                print(f"operation replayed ({match_strategy}): {op['op_type']} ({xr}, {yr})")
                return f"operation replayed ({match_strategy}): {op['op_type']} ({xr}, {yr})"
            if op["op_type"] == "long_press":
                device_service.perform_long_press(device_id, xr, yr)
                print(f"operation replayed ({match_strategy}): {op['op_type']} ({xr}, {yr})")
                return f"operation replayed ({match_strategy}): {op['op_type']} ({xr}, {yr})"

        if op["op_type"] == "tap_input":
            text = op["op_params"][2]
            device_service.perform_input(device_id, text, 10, 10)
            print(f"operation replayed: {op['op_type']} (10, 10, {text})")
            return f"operation replayed: {op['op_type']} (10, 10, {text})"

        if op["op_type"] == "scroll":
            w_src, h_src = get_img_shape(screen_path_src)
            w_dst, h_dst = get_img_shape(screen_path_dst)
            x_from, y_from, x_to, y_to, duration = op["op_params"]
            # v = math.dist((x_from, y_from), (x_to, y_to)) * 1000 // duration
            x_from_mapped = x_from * w_dst // w_src
            y_from_mapped = y_from * h_dst // h_src
            x_to_mapped = x_to * w_dst // w_src
            y_to_mapped = y_to * h_dst // h_src

            _, _, bounds = image_service.widget_image_match(screen_path_dst, widget_path)
            if bounds is not None:
                x1, y1, x2, y2 = bounds
                x_from_final = x1 + (x_from_mapped * (x2 - x1) // w_dst)
                y_from_final = y1 + (y_from_mapped * (y2 - y1) // h_dst)
                x_to_final = x1 + (x_to_mapped * (x2 - x1) // w_dst)
                y_to_final = y1 + (y_to_mapped * (y2 - y1) // h_dst)
                v = abs(x_to_final - x_from_final) * duration // abs(x_to - x_from)
                device_service.perform_scroll(
                    device_id, x_from_final, y_from_final, x_to_final, y_to_final, v)
                print((f"operation replayed (image): {op['op_type']} "
                    f"({x_from_final}, {y_from_final}, {x_to_final}, {y_to_final})"))
                return (f"operation replayed (image): {op['op_type']} "
                        f"({x_from_final}, {y_from_final}, {x_to_final}, {y_to_final})")

            _, _, bounds1 = image_service.widget_layout_match(screen_path_src, screen_path_dst, x_from, y_from)
            _, _, bounds2 = image_service.widget_layout_match(screen_path_src, screen_path_dst, x_to, y_to)
            if bounds1 is not None and bounds2 is not None and cal_iou(bounds1, bounds2) > 0.95:
                x1, y1, x2, y2 = bounds1
                x_from_final = x1 + (x_from_mapped * (x2 - x1) // w_dst)
                y_from_final = y1 + (y_from_mapped * (y2 - y1) // h_dst)
                x_to_final = x1 + (x_to_mapped * (x2 - x1) // w_dst)
                y_to_final = y1 + (y_to_mapped * (y2 - y1) // h_dst)
                v = abs(x_to_final - x_from_final) * duration // abs(x_to - x_from)
                device_service.perform_scroll(
                    device_id, x_from_final, y_from_final, x_to_final, y_to_final, v)
                print((f"operation replayed (layout): {op['op_type']} "
                    f"({x_from_final}, {y_from_final}, {x_to_final}, {y_to_final})"))
                return (f"operation replayed (layout): {op['op_type']} "
                        f"({x_from_final}, {y_from_final}, {x_to_final}, {y_to_final})")

            ui_layout_dst = device_service.get_ui_structure(device_id)
            candidates = self.extractor.extract2(ui_layout_dst, ["scrollable"]) \
                if ui_layout_dst.endswith(".json") else self.extractor2.extract2(ui_layout_dst, ["scrollable"])
            if len(candidates) == 0:
                print(f"replay failed: {op['op_id']}-{op['op_type']}")
                return f"replay failed: {op['op_id']}-{op['op_type']}"

            prior_candidates = [
                (x1, y1, x2, y2) for x1, y1, x2, y2 in candidates
                if x1 <= x_from_mapped <= x2 and y1 <= y_from_mapped <= y2]
            if len(prior_candidates) > 0:
                prior_candidates.sort(key=lambda e: (e[2] - e[0]) * (e[3] - e[1]))
                for x1, y1, x2, y2 in prior_candidates:
                    if cal_overlap_rate((x_from_mapped, y_from_mapped),
                            (x_to_mapped, y_to_mapped),(x1, y1, x2, y2)) > 0.75:
                        v = abs(x_to_mapped - x_from_mapped) * duration // abs(x_to - x_from)
                        device_service.perform_scroll(
                            device_id, x_from_mapped, y_from_mapped, x_to_mapped, y_to_mapped, v)
                        print((f"operation replayed (scrollable): {op['op_type']} "
                            f"({x_from_mapped}, {y_from_mapped}, {x_to_mapped}, {y_to_mapped})"))
                        return (f"operation replayed (scrollable): {op['op_type']} "
                                f"({x_from_mapped}, {y_from_mapped}, {x_to_mapped}, {y_to_mapped})")
            print(f"replay failed (#TODO): {op['op_id']}-{op['op_type']}")
            return f"replay failed (#TODO): {op['op_id']}-{op['op_type']}"

        if op["op_type"] == "assert":
            assertion_params = op["op_params"]
            assertion_text = assertion_params["text"]
            result, explanation = image_service.do_semantic_assertion(screen_path_dst, assertion_text)
            assertion_result = "text assert pass" if result else "text assert failed"
            print(assertion_result)
            print(explanation)
            return assertion_result

        print(f"invalid operation: {op['op_id']}-{op['op_type']}")
        return f"invalid operation: {op['op_id']}-{op['op_type']}"

record_controller = RecordController()
