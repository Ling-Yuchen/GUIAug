import asyncio
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.crud import copy_operation, get_script_with_operations, create_operation, get_operation_by_id, \
    get_script_mutate, get_script_description, update_operation_mutate, get_master_script_with_operations, \
    update_script_mutating
from app.models.db_models import Operation
from app.models.schemas import OperationModel
from app.services.dependence import get_script_service, get_mutation_service, get_image_service, get_device_service
from app.services.device_service import DeviceService
from app.services.image_service import ImageService
from app.services.mutation_service import MutationService
from app.services.script_service import ScriptService
from app.utils.logger import logger
from app.utils.main import get_img_shape, cal_iou, cal_overlap_rate, gen_step_id, gen_timestamp
from app.utils.widget_extract import HarmonyWidgetExtractor, AndroidWidgetExtractor


class MutateController:

    def __init__(self):
        self.script_model = None
        self.router = APIRouter()
        self.extractor = HarmonyWidgetExtractor()
        self.extractor2 = AndroidWidgetExtractor()
        self.script_path: Path = Path(__file__).parent.parent.parent.resolve() / "data" / "scripts"

        self.router.add_api_route("/mutate/prepare/{script_id}", self.prepare_for_mutation, methods=["GET"])
        self.router.add_api_route("/mutate/semantic_view/{script_id}", self.get_semantic_view, methods=["GET"])
        self.router.add_api_route("/mutate/input_data/{script_id}/{op_id}", self.mutate_script_input_data, methods=["GET"])
        self.router.add_api_route("/mutate/input_data_confirm/{script_id}/{op_id}", self.mutate_script_input_data_confirm, methods=["POST"])
        self.router.add_api_route("/mutate/input_complete/{script_id}/{device_id}", self.complete_input_augmentation, methods=["GET"])
        self.router.add_api_route("/mutate/path_confirm/{script_id}/{op_id}", self.mutate_script_path_confirm, methods=["POST"])
        self.router.add_api_route("/mutate/path_complete/{script_id}/{device_id}", self.complete_mutating_script, methods=["GET"])
        self.router.add_api_route("/mutate/update_mutate/{script_id}/{op_id}/{mutate_type}", self.update_mutate_type, methods=["GET"])

    async def update_mutate_type(self, script_id: str, op_id: str, mutate_type: str, db: Session = Depends(get_db)):
        update_operation_mutate(db, op_id, mutate_type)

    async def prepare_for_mutation(self, script_id: str, db: Session = Depends(get_db), mutation_service: MutationService = Depends(get_mutation_service)):
        mutate_ready = get_script_mutate(db, script_id)
        script_desc = get_script_description(db, script_id)
        if not script_desc:
            return f"Script {script_id} has not been described."
        if mutate_ready:
            return f"Script {script_id} has been ready for mutation."
        mutation_service.prepare(db, script_id)
        return f"Script {script_id} is ready for augmentation."

    async def get_semantic_view(
            self,
            script_id: str,
            refresh: bool = Query(False),
            db: Session = Depends(get_db),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        return mutation_service.get_semantic_view(db, script_id, refresh=refresh)

    async def mutate_script_input_data(
            self,
            script_id: str,
            op_id: str,
            detailed: bool = Query(False),
            db: Session = Depends(get_db),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        logger.log("INPUT MUTATE START", f"SCRIPT ID: {script_id}, OP ID: {op_id}")
        mutation_result = mutation_service.generate_mutated_input_data(db, script_id, op_id)
        if mutation_result is None:
            return [["", []]]
        if detailed:
            return mutation_result
        mutations = mutation_result["mutations"]
        return [[m["value"], m["bindings"]] for m in mutations]

    async def mutate_script_input_data_confirm(
            self,
            script_id: str,
            op_id: str,
            new_data: Request,
            db: Session = Depends(get_db),
            script_service: ScriptService = Depends(get_script_service),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        new_data: Dict[str, Any] = await new_data.json()
        new_data: List[Any] = new_data["data"]
        script, operations = get_script_with_operations(db, script_id)
        op2mutate: Operation = get_operation_by_id(db, op_id)
        if op2mutate.mutate_type != "INPUT-DATA":
            return (f"Script mutation fails: mutation type mismatch. "
                    f"Expected: INPUT-DATA, Actual: {op2mutate.mutate_type}")
        for i, new_item in enumerate(new_data):
            if isinstance(new_item, dict):
                text = new_item["value"]
                assertions = new_item.get("bindings", [])
                mutation_metadata = {
                    "input_role": new_item.get("input_role"),
                    "constraint_summary": new_item.get("constraint_summary"),
                    "category": new_item.get("category"),
                    "expected_effect": new_item.get("expected_effect"),
                }
            else:
                text, assertions = new_item[0], new_item[1]
                mutation_metadata = {}
            timestamp = gen_timestamp()
            script_name = script.script_name + f"-INPUT-{timestamp}-{i + 1}"
            script_new = script_service.init_script(
                db, script_name, script.device_id, script.app_id, script.script_id)
            for op in operations:
                op: Operation = op
                op_id_new = gen_step_id(None, None)
                if op.op_id == op_id:
                    input_op_params = json.loads(op2mutate.op_params)
                    input_op_params[2] = text
                    new_operation_data = {
                        "script_id": script_new["script_id"],
                        "op_id": op_id_new,
                        "op_type": op2mutate.op_type,
                        "op_params": json.dumps(input_op_params),
                        "widget_bbox": json.dumps(op2mutate.widget_bbox),
                        "widget_desc": op2mutate.widget_desc,
                        "op_folder": op_id_new,
                        "timestamp": datetime.now(),
                        "package": op2mutate.package,
                        "activity": op2mutate.activity,
                        "intent": (
                            f'enter "{text}" while preserving the semantic role '
                            f"of the seed input"
                        ),
                        "mutate_type": "NONE",
                        "mutate_reason": "",
                    }
                    new_operation = OperationModel(**new_operation_data)
                    create_operation(db, new_operation)
                elif op.op_id in [a["assertion_op_id"] for a in assertions]:
                    assertion_text = [a["assertion_text"] for a in assertions \
                                            if a["assertion_op_id"] == op.op_id][0]
                    new_operation_data = {
                        "script_id": script_new["script_id"],
                        "op_id": op_id_new,
                        "op_type": "assert",
                        "op_params": json.dumps({"text": assertion_text}),
                        "widget_bbox": str((-1, -1, -1, -1)),
                        "widget_desc": "",
                        "op_folder": op_id_new,
                        "timestamp": datetime.now(),
                        "package": "",
                        "activity": "",
                        "intent": f"verify that {assertion_text}",
                        "mutate_type": "NONE",
                        "mutate_reason": "",
                    }
                    new_operation = OperationModel(**new_operation_data)
                    create_operation(db, new_operation)
                else:
                    copy_operation(db, op.op_id, script_new["script_id"], op_id_new)

                op_folder_old = self.script_path / script.script_folder / op.op_folder
                op_folder_new = self.script_path / script_new["script_id"] / op_id_new
                op_folder_new.mkdir(parents=True)
                for src_file in op_folder_old.iterdir():
                    if src_file.is_file():
                        dst_file = op_folder_new / src_file.name
                        shutil.copy(str(src_file), str(dst_file))
            logger.log("INPUT MUTATE RESULT", f"NEW SCRIPT: {script_name}, SCRIPT ID: {script_new['script_id']}")
            mutation_service.initialize_augmentation_context(
                script_new["script_id"],
                module="input-aware",
                master_script_id=script_id,
                source_op_id=op_id,
                mutated_value=text,
                outcome_label="PENDING_RUNTIME_VALIDATION",
                suffix_strategy="DIRECT_SUBSTITUTION",
                assertion_rebinding=assertions,
                max_exploration_steps=10,
                **mutation_metadata,
            )
        return "Script mutation done"

    async def mutate_script_path_confirm(
            self,
            script_id: str,
            op_id: str,
            new_data: Request,
            db: Session = Depends(get_db),
            script_service: ScriptService = Depends(get_script_service),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        new_data: Dict[str, Any] = await new_data.json()
        # bbox_info = new_data["bbox"]
        # new_data: List[str, Any] = new_data["feasible_choices"]
        script, operations = get_script_with_operations(db, script_id)
        op2mutate: Operation = get_operation_by_id(db, op_id)
        if op2mutate.mutate_type != "PATH":
            return (f"Script mutation fails: mutation type mismatch. "
                    f"Expected: PATH, Actual: {op2mutate.mutate_type}")
        script_name = script.script_name + f"-mutate-path"
        script_new = script_service.init_script(
            db, script_name, script.device_id, script.app_id, script.script_id, mutating=True)
        for op in operations:
            op: Operation = op
            op_id_new = gen_step_id(None, None)
            copy_operation(db, op.op_id, script_new["script_id"], op_id_new)
            op_folder_old = self.script_path / script.script_folder / op.op_folder
            op_folder_new = self.script_path / script_new["script_id"] / op_id_new
            op_folder_new.mkdir(parents=True)
            for src_file in op_folder_old.iterdir():
                if src_file.is_file():
                    dst_file = op_folder_new / src_file.name
                    shutil.copy(str(src_file), str(dst_file))
            if op.op_id == op_id:
                break
        semantic_view = mutation_service.get_semantic_view(db, script_id)
        branch_point = next(
            (
                item for item in semantic_view.get("branch_points", [])
                if str(item.get("op_id")) == str(op_id)
            ),
            None,
        )
        if branch_point is None:
            branch_point = mutation_service.generate_mutation_goal(db, script_id, op_id)
        mutation_service.initialize_augmentation_context(
            script_new["script_id"],
            module="intent-aware",
            master_script_id=script_id,
            source_op_id=op_id,
            branch_goal=branch_point,
            max_exploration_steps=10,
        )
        return "Script path mutation inited"

    async def complete_input_augmentation(
            self,
            script_id: str,
            device_id: str,
            db: Session = Depends(get_db),
            script_service: ScriptService = Depends(get_script_service),
            device_service: DeviceService = Depends(get_device_service),
            image_service: ImageService = Depends(get_image_service),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        context = mutation_service.get_augmentation_context(script_id)
        if context.get("module") != "input-aware":
            return "Input-aware augmentation failed: augmentation context is missing."

        script, operations = get_script_with_operations(db, script_id)
        executed_ops = []
        assertion_records = []
        divergence_index = None
        for index, op in enumerate(operations):
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
            replay_result = await self.replay_operation_harmony(
                script_id,
                device_id,
                op_dict,
                script_service,
                image_service,
                device_service,
            )
            if "failed" in replay_result or "invalid operation" in replay_result:
                divergence_index = index
                break
            executed_ops.append({"op_type": op.op_type, "intent": op.intent})
            if op.op_type == "assert":
                assertion_records.append({
                    "expected_property": json.loads(op.op_params).get("text", ""),
                    "supporting_runtime_evidence": device_service.get_screenshot(device_id),
                    "anchor_operation": (
                        operations[index - 1].op_id if index > 0 else None
                    ),
                })

        if divergence_index is None:
            mutation_service.update_augmentation_context(
                script_id,
                status="COMPLETED",
                outcome_label="POSITIVE",
                suffix_strategy="PRESERVED_SUFFIX",
                generated_operations=executed_ops,
                assertions=assertion_records,
            )
            return f"Input-aware augmentation {script_id} preserved the original suffix."

        for op in operations[divergence_index:]:
            script_service.remove_op_from_db(db, op.op_id, script_id)

        master_script_id = context.get("master_script_id", "")
        source_op_id = context.get("source_op_id", "")
        master_script, master_operations = get_script_with_operations(db, master_script_id)
        if master_script is None:
            return "Input-aware augmentation failed: the seed script reference is missing."
        source_index = next(
            (
                index for index, op in enumerate(master_operations)
                if str(op.op_id) == str(source_op_id)
            ),
            -1,
        )
        original_suffix = [
            {
                "op_id": op.op_id,
                "op_type": op.op_type,
                "intent": op.intent,
            }
            for op in master_operations[source_index + 1:]
        ]
        semantic_view = mutation_service.get_semantic_view(db, master_script_id)
        screen = device_service.get_screenshot(device_id)
        adaptation = mutation_service.formulate_input_adaptation_goal(
            semantic_view,
            context.get("mutated_value", ""),
            original_suffix,
            executed_ops,
            screen,
        )
        goal = adaptation["goal"]
        generated_ops = []

        for _ in range(context.get("max_exploration_steps", 10)):
            screen = device_service.get_screenshot(device_id)
            ui_json = device_service.get_ui_structure(device_id)
            package, activity = device_service.get_current_app_message(device_id)
            screen_bbox, bboxes = image_service.get_screenshot_with_bbox(screen)
            result = mutation_service.next_operation(
                db,
                master_script_id,
                screen,
                screen_bbox,
                bboxes,
                executed_ops + generated_ops,
                goal,
                image_service,
                source_op_id,
            )
            if result["type"] == "end":
                break
            if result["type"] == "invalid":
                break

            await self._execute_and_record_generated_action(
                result,
                script_id,
                device_id,
                screen,
                ui_json,
                package,
                activity,
                bboxes,
                db,
                script_service,
                device_service,
            )
            generated_ops.append({
                "op_type": result["type"],
                "intent": result["description"],
            })

        outcome_label = "ALTERNATIVE"
        assertion = mutation_service.inject_assertion(
            db,
            script_id,
            device_service,
            device_id,
            goal=goal,
            generated_ops=generated_ops,
        )
        assertion_info, assertion_intent, assertion_screen, op_prev, op_next = assertion
        script_service.record_oracle(
            db,
            script_id,
            script_id,
            assertion_screen,
            assertion_info,
            op_prev,
            op_next,
            assertion_intent,
        )
        mutation_service.update_augmentation_context(
            script_id,
            status="COMPLETED",
            outcome_label=outcome_label,
            suffix_strategy="ADAPTED_SUFFIX",
            adaptation_goal=adaptation,
            generated_operations=generated_ops,
            assertion={
                "expected_property": assertion_info["text"],
                "supporting_runtime_evidence": assertion_screen,
                "anchor_after_operation": op_prev,
                "anchor_before_operation": op_next,
            },
        )
        return (
            f"Input-aware augmentation {script_id} completed with "
            f"{outcome_label} outcome."
        )

    @staticmethod
    async def _execute_and_record_generated_action(
            result: Dict[str, Any],
            script_id: str,
            device_id: str,
            screen: str,
            ui_json: str,
            package: str,
            activity: str,
            bboxes: Dict[str, Any],
            db: Session,
            script_service: ScriptService,
            device_service: DeviceService,
    ):
        action_type = result["type"]
        description = result["description"]
        if action_type == "back":
            device_service.perform_back(device_id)
            script_service.record_back(
                db,
                script_id,
                script_id,
                screen,
                ui_json,
                package,
                activity,
                None,
                None,
                intent=description,
            )
            await asyncio.sleep(3)
            return

        target = result.get("target")
        x, y = 10, 10
        if target is not None:
            x1, y1, x2, y2 = bboxes[str(target)]
            x, y = (x1 + x2) // 2, (y1 + y2) // 2

        if action_type == "tap":
            device_service.perform_click(device_id, x, y)
            script_service.record_tap(
                db, script_id, x, y, script_id, screen, ui_json,
                package, activity, None, None, intent=description,
            )
            await asyncio.sleep(4)
        elif action_type == "input":
            if target is not None:
                device_service.perform_click(device_id, x, y)
            text = result["text"]
            device_service.perform_input(device_id, text, x, y)
            script_service.record_tap_input(
                db, script_id, x, y, text, script_id, screen, ui_json,
                package, activity, None, None, intent=description,
            )
            await asyncio.sleep(3)
        elif action_type == "long_press":
            device_service.perform_long_press(device_id, x, y)
            script_service.record_long_press(
                db, script_id, x, y, script_id, screen, ui_json,
                package, activity, None, None, intent=description,
            )
            await asyncio.sleep(3)

    async def complete_mutating_script(
            self,
            script_id: str,
            device_id: str,
            # mutate_goal: Optional[str] = None,
            db: Session = Depends(get_db),
            script_service: ScriptService = Depends(get_script_service),
            device_service: DeviceService = Depends(get_device_service),
            image_service: ImageService = Depends(get_image_service),
            mutation_service: MutationService = Depends(get_mutation_service),
    ):
        logger.log("PATH MUTATE START", f"SCRIPT ID: {script_id}")
        # replay current script
        script, operations = get_script_with_operations(db, script_id)
        executed_ops = []
        for op in operations:
            op_dict = {
                "op_id": op.op_id,
                "op_type": op.op_type,
                "op_params": json.loads(op.op_params),
                "widget_bbox": op.widget_bbox,
                "widget_desc": op.widget_desc,
                "package": op.package,
                "activity": op.activity,
                "op_folder": op.op_folder,
                # "perf_type": op.perf,
                "intent": op.intent,
                "timestamp": op.timestamp,
                "mutate_type": op.mutate_type,
                "mutate_reason": op.mutate_reason,
            }
            replay_result = await self.replay_operation_harmony(
                script_id, device_id, op_dict, script_service, image_service, device_service)
            executed_ops.append({"op_type": op.op_type, "intent": op.intent})
            if "failed" in replay_result:
                print("Mutation failed due to replay failure.")
                return "Mutation failed due to replay failure."
        await asyncio.sleep(3)

        # get master script from script.script_master
        master_script, master_operations = get_master_script_with_operations(db, script_id)
        if master_script is None:
            update_script_mutating(db, script_id, False)
            return "Mutation failed: the seed script reference is missing."
        # do mutation
        augmentation_context = mutation_service.get_augmentation_context(script_id)
        branch_goal = augmentation_context.get("branch_goal", {})
        mutate_goal = branch_goal.get("goal", "") if isinstance(branch_goal, dict) else str(branch_goal)
        source_op_id = augmentation_context.get("source_op_id", "")
        if not mutate_goal:
            update_script_mutating(db, script_id, False)
            return "Mutation failed: no branch goal was persisted for this script."
        op_count, op_end = 0, False
        logger.log("PATH MUTATE INFO", f"GOAL: {mutate_goal}")

        while op_count < 10 and not op_end:
            try:
                screen = device_service.get_screenshot(device_id)
                ui_json = device_service.get_ui_structure(device_id)
                package, activity = device_service.get_current_app_message(device_id)
                screen_bbox, bboxes = image_service.get_screenshot_with_bbox(screen)
                result = mutation_service.next_operation(
                    db, master_script.script_id, screen, screen_bbox,
                    bboxes, executed_ops, mutate_goal, image_service, source_op_id,
                )
                if result["type"] == "invalid":
                    logger.log("PATH MUTATE INVALID ACTION", result["description"])
                    break
                executed_ops.append({"op_type": result["type"], "intent": result["description"]})
                op_count += 1
                if result["type"] == "back":
                    device_service.perform_back(device_id)
                    script_service.record_back(
                        db, script_id, script_id, screen, ui_json,
                        package, activity, None, None,
                        intent=result["description"],
                    )
                    await asyncio.sleep(3)
                elif result["type"] == "tap":
                    index = str(result["target"])
                    x1, y1, x2, y2 = bboxes[index]
                    x, y = (x1 + x2) // 2, (y1 + y2) // 2
                    device_service.perform_click(device_id, x, y)
                    script_service.record_tap(db, script_id, x, y, script_id, screen, ui_json, package, activity, None, None, intent=result["description"])
                    await asyncio.sleep(4)
                elif result["type"] == "input":
                    if result.get("target") is not None:
                        index = str(result["target"])
                        x1, y1, x2, y2 = bboxes[index]
                        x, y = (x1 + x2) // 2, (y1 + y2) // 2
                        device_service.perform_click(device_id, x, y)
                        script_service.record_tap(db, script_id, x, y, script_id, screen, ui_json, package, activity,None, None, intent=result["description"])
                        await asyncio.sleep(1)
                    text = result["text"]
                    device_service.perform_input(device_id, text, 10, 10)
                    script_service.record_tap_input(db, script_id, 10, 10, text, script_id, screen, ui_json, package, activity, None, None, intent=result["description"])
                    await asyncio.sleep(3)
                elif result["type"] == "long_press":
                    index = str(result["target"])
                    x1, y1, x2, y2 = bboxes[index]
                    x, y = (x1 + x2) // 2, (y1 + y2) // 2
                    device_service.perform_long_press(device_id, x, y)
                    script_service.record_long_press(db, script_id, x, y, script_id, screen, ui_json, package, activity, None, None, intent=result["description"])
                    await asyncio.sleep(3)
                elif result["type"] == "end":
                    print("end mutate script...")
                    op_end = True
                else:
                    print("Invalid mutate type:", result["type"])
                    continue
            except Exception as e:
                print(e)
                logger.log("PATH MUTATE ERROR", str(e))
                break

        injected_assertion = mutation_service.inject_assertion(
            db,
            script_id,
            device_service,
            device_id,
            goal=mutate_goal,
            generated_ops=executed_ops,
        )
        assertion_info, assertion_intent, assertion_screen, op_prev, op_next = injected_assertion
        script_service.record_oracle(db, script_id, script_id, assertion_screen, assertion_info, op_prev, op_next, assertion_intent)
        mutation_service.update_augmentation_context(
            script_id,
            status="COMPLETED",
            generated_operations=executed_ops,
            assertion={
                "expected_property": assertion_info["text"],
                "supporting_runtime_evidence": assertion_screen,
                "anchor_after_operation": op_prev,
                "anchor_before_operation": op_next,
            },
        )
        update_script_mutating(db, script_id, False)
        logger.log("PATH MUTATE END", f"SCRIPT ID: {script_id}")
        return f"Script {script_id} mutated completed"

    async def replay_operation_harmony(
            self,
            script_id: str,
            device_id: str,
            op: Dict[str, Any],
            script_service: ScriptService,
            image_service: ImageService,
            device_service: DeviceService
    ):
        wait_count = 0
        layout1 = device_service.get_ui_structure(device_id, False)
        await asyncio.sleep(1)
        layout2 = device_service.get_ui_structure(device_id, False)
        while layout1 != layout2 and wait_count < 4:
            wait_count += 1
            await asyncio.sleep(1)
            layout1 = layout2
            layout2 = device_service.get_ui_structure(device_id, False)

        script_folder = script_service.get_script_path() / script_id
        op_folder = script_folder / op["op_folder"]
        widget_path = str(op_folder / f"widget.jpeg")
        screen_path_src = str(op_folder / "screen.jpeg")
        screen_path_dst = device_service.get_screenshot(device_id)

        if op["op_type"] == "tap" or op["op_type"] == "long_press":
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
                        if x1 is not None and x2 is not None:
                            xr, yr, match_strategy = x1, y1, "image"
                        elif x2 is not None and y2 is not None:
                            xr, yr, match_strategy = x2, y2, "layout"

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

        if op["op_type"] == "back":
            device_service.perform_back(device_id)
            return "operation replayed: back"

        if op["op_type"] == "scroll":
            w_src, h_src = get_img_shape(screen_path_src)
            w_dst, h_dst = get_img_shape(screen_path_dst)
            x_from, y_from, x_to, y_to, duration = op["op_params"]
            v = math.dist((x_from, y_from), (x_to, y_to)) * 1000 // duration
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
                                        (x_to_mapped, y_to_mapped), (x1, y1, x2, y2)) > 0.75:
                        device_service.perform_scroll(
                            device_id, x_from_mapped, y_from_mapped, x_to_mapped, y_to_mapped, v)
                        print((f"operation replayed (scrollable): {op['op_type']} "
                               f"({x_from_mapped}, {y_from_mapped}, {x_to_mapped}, {y_to_mapped})"))
                        return (f"operation replayed (scrollable): {op['op_type']} "
                                f"({x_from_mapped}, {y_from_mapped}, {x_to_mapped}, {y_to_mapped})")
            print(f"replay failed (#TODO): {op['op_id']}-{op['op_type']}")
            return f"replay failed (#TODO): {op['op_id']}-{op['op_type']}"

        if op["op_type"] == "assert":
            assertion_text = op["op_params"]["text"]
            result, explanation = image_service.do_semantic_assertion(
                screen_path_dst,
                assertion_text,
            )
            logger.log(
                "REPLAY ASSERTION",
                f"{'PASS' if result else 'FAILED'}: {explanation}",
            )
            return "assertion pass" if result else "assertion failed"

        print(f"invalid operation: {op['op_id']}-{op['op_type']}")
        return f"invalid operation: {op['op_id']}-{op['op_type']}"

mutate_controller = MutateController()
