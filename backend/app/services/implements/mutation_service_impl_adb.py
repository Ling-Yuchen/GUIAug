import json
import random
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.db.crud import get_script_with_operations, update_operation_mutate, update_script_mutate
from app.models.db_models import Operation
from app.services.augmentation_artifacts import (
    read_json,
    summarize_seed_profile,
    validate_dependencies,
    validate_generated_action,
    write_json_atomic,
)
from app.services.device_service import DeviceService
from app.services.image_service import ImageService
from app.services.mutation_service import MutationService
from app.utils.llm import query
from app.utils.logger import logger
from app.utils.main import gen_timestamp
from app.prompt import (
    assertion_injection_generating_prompt,
    assertion_injection_locating_prompt,
    business_input_mutate_query_prompt,
    content_input_mutate_query_prompt,
    input_assert_binding_prompt,
    input_role_analysis_prompt,
    input_suffix_adaptation_goal_prompt,
    input_type_query_prompt,
    mutation_ending_check_prompt,
    mutation_goal_decide_prompt,
    mutation_point_candidate_filter_prompt,
    new_assertion_generate_prompt,
    operation_semantic_descriptor_prompt,
    path_mutate_query_prompt,
    scenario_dependency_recovery_prompt,
    widget_rank_for_mutation_query_prompt,
)


class MutationServiceImpl(MutationService):

    script_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "scripts"
    screenshots_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "screenshots"
    semantic_view_filename = "semantic_view.json"
    augmentation_context_filename = "augmentation_context.json"

    def prepare(self, db: Session, script_id: str):
        semantic_view = self.get_semantic_view(db, script_id, refresh=True)
        self.detect_mutation_point(db, script_id, semantic_view)
        semantic_view = self.get_semantic_view(db, script_id)
        update_script_mutate(db, script_id, True)
        return semantic_view

    def set_mutation_point(self, db: Session, op_id: str, mutate_type: str, mutate_reason: str):
        update_operation_mutate(db, op_id, mutate_type, mutate_reason)

    def _script_artifact_path(self, script_id: str, filename: str) -> Path:
        return self.script_path / str(script_id) / filename

    @staticmethod
    def _write_json(path: Path, payload: Dict[str, Any]):
        write_json_atomic(path, payload)

    def initialize_augmentation_context(
            self,
            script_id: str,
            module: str,
            master_script_id: str,
            source_op_id: str,
            **metadata,
    ):
        context = {
            "schema_version": 1,
            "module": module,
            "master_script_id": str(master_script_id),
            "source_op_id": str(source_op_id),
            "created_at": datetime.now().isoformat(),
            **metadata,
        }
        self._write_json(
            self._script_artifact_path(script_id, self.augmentation_context_filename),
            context,
        )
        return context

    def get_augmentation_context(self, script_id: str):
        return read_json(
            self._script_artifact_path(script_id, self.augmentation_context_filename)
        )

    def update_augmentation_context(self, script_id: str, **updates):
        context = self.get_augmentation_context(script_id)
        context.update(updates)
        context["updated_at"] = datetime.now().isoformat()
        self._write_json(
            self._script_artifact_path(script_id, self.augmentation_context_filename),
            context,
        )
        return context

    def get_semantic_view(self, db: Session, script_id: str, refresh: bool = False):
        path = self._script_artifact_path(script_id, self.semantic_view_filename)
        if path.exists() and not refresh:
            return read_json(path)

        script = self.get_script(db, script_id)
        if not script:
            raise ValueError(f"Script {script_id} does not exist")
        operations = script["operations"]
        descriptors = []
        for op in operations:
            if op["op_type"] == "assert":
                descriptor = {
                    "op_id": op["op_id"],
                    "description": op["intent"],
                    "preconditions": ["the asserted GUI state has been reached"],
                    "expected_effects": ["the visible GUI evidence is evaluated"],
                    "involved_widgets": [],
                    "references": [],
                }
            else:
                op_folder = self.script_path / script["script_folder"] / op["op_folder"]
                images = [str(op_folder / "screen.jpeg")]
                widget_path = op_folder / "widget.jpeg"
                if widget_path.exists():
                    images.append(str(widget_path))
                input_text = ""
                if op["op_type"] in {"tap_input", "input"} and len(op["op_params"]) >= 3:
                    input_text = str(op["op_params"][2])
                prompt = operation_semantic_descriptor_prompt \
                    .replace("{PREVIOUS-DESCRIPTORS}", json.dumps(descriptors, ensure_ascii=False)) \
                    .replace("{OPERATION-ID}", str(op["op_id"])) \
                    .replace("{OPERATION-TYPE}", op["op_type"]) \
                    .replace("{OPERATION-INTENT}", op["intent"] or "") \
                    .replace("{INPUT-TEXT}", input_text)
                result, in_usage, out_usage, in_cost, out_cost = query(
                    user_msg_txt=prompt,
                    user_msg_img=images,
                )
                descriptor = {
                    "op_id": op["op_id"],
                    "description": result.get("description", op["intent"]),
                    "preconditions": result.get("preconditions", []),
                    "expected_effects": result.get("expected_effects", []),
                    "involved_widgets": result.get("involved_widgets", []),
                    "references": result.get("references", []),
                }
                logger.log(
                    "INTERPRET OPERATION",
                    f"{op['op_id']}: {descriptor['description']} | "
                    f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)",
                )
            descriptors.append(descriptor)

        assertions = [
            {"op_id": op["op_id"], "assertion": op["intent"]}
            for op in operations if op["op_type"] == "assert"
        ]
        recovery_prompt = scenario_dependency_recovery_prompt \
            .replace("{SCRIPT-DESCRIPTION}", script["description"] or "") \
            .replace("{OPERATION-DESCRIPTORS}", json.dumps(descriptors, ensure_ascii=False)) \
            .replace("{ASSERTIONS}", json.dumps(assertions, ensure_ascii=False))
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=recovery_prompt)
        dependencies = validate_dependencies(operations, result.get("dependencies", []))
        semantic_view = {
            "schema_version": 1,
            "script_id": str(script_id),
            "descriptors": descriptors,
            "scenario": result.get("scenario", {}),
            "dependency_graph": {
                "nodes": [op["op_id"] for op in operations],
                "edges": dependencies,
            },
            "input_positions": [
                {"index": index, "op_id": op["op_id"]}
                for index, op in enumerate(operations, start=1)
                if op["op_type"] in {"tap_input", "input"}
            ],
            "branch_points": [],
        }
        self._write_json(path, semantic_view)
        logger.log(
            "RECOVER SCRIPT SEMANTICS",
            f"SCRIPT: {script_id} | EDGES: {len(dependencies)} | "
            f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)",
        )
        return semantic_view

    ##################################################################################

    def generate_mutated_input_data(self, db: Session, script_id: str, op_id: str):
        """
        :return: {
            "original": dict,  # op2mutate
            "input_type": str,  # "business-oriented"|"content-oriented"
            "input_rule": str|None,  # input rule for "business-oriented"
            "mutations": [{
                "value": str,  # new input text
                "type": str|None,  # mutation type for "content-oriented"
                "valid": bool|None,  # mutation type for "business-oriented"
                "reason": str,  # mutation reason
                "bindings": [{
                    "assertion_idx": int,  # op index of bound assertion (script level)
                    "assertion_op_id": str,  # op_id of bound assertion (db level)
                    "assertion_text": str,  # new assertion text
                }]
            }]
        }
        """
        script = self.get_script(db, script_id)
        operations = script["operations"]
        candidates = [op for op in operations if op["op_id"] == op_id]
        if len(candidates) == 0:
            print("Can't find op id: ", op_id)
            return None
        op2mutate = candidates[0]
        if op2mutate["mutate_type"] != "INPUT-DATA":
            print("Mutation type not supported")
            return None

        semantic_view = self.get_semantic_view(db, script_id)
        input_semantics = self.analyze_input_role(semantic_view, op2mutate)
        input_type, input_rule = self.detect_input_type(operations, op2mutate)
        mutate_result = self.do_business_input_mutation(op2mutate, input_rule, 1, 1) \
            if input_type == "business-oriented" else self.do_content_input_mutation(op2mutate, 1, 1, 1)
        mutate_result["input_role"] = input_semantics["role"]
        mutate_result["constraint_summary"] = input_semantics["constraints"]
        for mutation in mutate_result["mutations"]:
            mutation["input_role"] = input_semantics["role"]
            mutation["constraint_summary"] = input_semantics["constraints"]
            if input_type == "business-oriented":
                mutation["category"] = "normal" if mutation.get("valid") else "invalid"
                mutation["expected_effect"] = (
                    "the original suffix may remain feasible"
                    if mutation.get("valid")
                    else "validation feedback, an empty result, or suffix divergence may occur"
                )
            else:
                mutation["category"] = {
                    "length": "long",
                    "language": "domain-specific",
                    "character": "boundary",
                }.get(mutation.get("type"), "normal")
                mutation["expected_effect"] = "the input is accepted and reflected in the seed scenario"
        bindings = self.analyze_input_assert_bound(script, mutate_result)
        return self.apply_input_assert_bound(script, mutate_result, bindings)

    @staticmethod
    def analyze_input_role(semantic_view: Dict[str, Any], op2mutate: Dict[str, Any]):
        descriptor = next(
            (
                item for item in semantic_view.get("descriptors", [])
                if str(item.get("op_id")) == str(op2mutate["op_id"])
            ),
            {},
        )
        dependencies = [
            edge for edge in semantic_view.get("dependency_graph", {}).get("edges", [])
            if str(edge.get("src")) == str(op2mutate["op_id"])
        ]
        prompt = input_role_analysis_prompt \
            .replace("{SCENARIO}", json.dumps(semantic_view.get("scenario", {}), ensure_ascii=False)) \
            .replace("{DESCRIPTOR}", json.dumps(descriptor, ensure_ascii=False)) \
            .replace("{INPUT-OPERATION}", json.dumps(op2mutate, ensure_ascii=False, default=str)) \
            .replace("{DEPENDENCIES}", json.dumps(dependencies, ensure_ascii=False))
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        logger.log(
            "ANALYZE INPUT ROLE",
            f"ROLE: {result.get('role', '')} | "
            f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)",
        )
        return {
            "role": result.get("role", ""),
            "constraints": result.get("constraints", {}),
        }

    @staticmethod
    def detect_input_type(operations: List[Any], op2mutate: Dict[str, Any]):
        prompt = input_type_query_prompt.replace("{FULL-TEST-SCRIPT}",
            "\n".join(f"[{i + 1}] {op['intent']}" for i, op, in enumerate(operations))) \
            .replace("{SPECIFIC-INPUT-STEP-DESCRIPTION}", op2mutate["intent"])
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        input_type = result["type"].lower()
        input_type_reason = result["reason"]
        print(f"input_type_reason: {input_type_reason}")
        input_rule = result["requirement"] if input_type == "business-oriented" else None
        print(f"input_rule: {input_rule}")
        logger.log("DETECT INPUT TYPE", f"ORIGIN: {op2mutate['intent']}")
        logger.log("DETECT INPUT TYPE", f"RESULT: {input_type}")
        logger.log("DETECT INPUT TYPE", f"REASON: {input_type_reason}")
        logger.log("DETECT INPUT TYPE", f"RULE: {input_rule}")
        logger.log("DETECT INPUT TYPE", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return input_type, input_rule

    @staticmethod
    def do_content_input_mutation(op2mutate: Dict[str, Any], n1: int, n2: int, n3: int):
        mutations = []
        prompt = content_input_mutate_query_prompt \
            .replace("{INPUT-OPERATION-FOR-MUTATION}", op2mutate["intent"]) \
            .replace("{NUM_LENGTH}", f"{n1}").replace("{NUM_LANGUAGE}", f"{n2}").replace("{NUM_CHAR}", f"{n3}")
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        for i, item in enumerate(result["mutations"]):
            mutations.append({
                "value": item["value"],
                "type": item.get("type", None),
                "valid": item.get("valid", None),
                "reason": item["reason"],
            })
            logger.log("CONTENT INPUT MUTATION", f"ITEM-{i}-VALUE: {item['value']}")
            logger.log("CONTENT INPUT MUTATION", f"ITEM-{i}-TYPE: {item.get('type', None)}")
            logger.log("CONTENT INPUT MUTATION", f"ITEM-{i}-REASON: {item['reason']}")

        logger.log("CONTENT INPUT MUTATION", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return {
            "original": op2mutate,
            "input_type": "content-oriented",
            "input_rule": None,
            "mutations": mutations,
        }

    @staticmethod
    def do_business_input_mutation(op2mutate: Dict[str, Any], input_rule: str, num_valid: int, num_invalid: int):
        mutations = []
        prompt = business_input_mutate_query_prompt \
            .replace("{INPUT-OPERATION-FOR-MUTATION}", op2mutate["intent"]) \
            .replace("{BUSINESS-RULE-DESCRIPTION}", input_rule) \
            .replace("{NUM_VALID}", f"{num_valid}").replace("{NUM_INVALID}", f"{num_invalid}")
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        for i, item in enumerate(result["mutations"]):
            mutations.append({
                "value": item["value"],
                "type": item.get("type", None),
                "valid": item.get("valid", None),
                "reason": item["reason"],
            })
            logger.log("BUSINESS INPUT MUTATION", f"ITEM-{i}-VALUE: {item['value']}")
            logger.log("BUSINESS INPUT MUTATION", f"ITEM-{i}-VALID: {item.get('valid', None)}")
            logger.log("BUSINESS INPUT MUTATION", f"ITEM-{i}-REASON: {item['reason']}")

        logger.log("BUSINESS INPUT MUTATION", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return {
            "original": op2mutate,
            "input_type": "business-oriented",
            "input_rule": input_rule,
            "mutations": mutations,
        }

    @staticmethod
    def analyze_input_assert_bound(script: Dict[str, Any], mutate_result: Dict[str, Any]):
        operations = script["operations"]
        if "assert" not in [op["op_type"] for op in operations]:
            return []

        input_op = mutate_result["original"]
        input_type, input_rule = mutate_result["input_type"], mutate_result["input_rule"]
        input_type_desc = f"{input_type} input with input rule - `{input_rule}`" \
            if input_rule is not None else f"{input_type} input without input rule"
        script_str = "\n".join(f"  [{i}] {op['intent']}" for i, op, in enumerate(operations, start=1))
        prompt = input_assert_binding_prompt \
            .replace("{SCRIPT_OPERATIONS}", script_str) \
            .replace("{INPUT_INTENT}", input_op["intent"]) \
            .replace("{INPUT_TYPE_DESC}", input_type_desc)
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        bindings = result["result"]
        for i, binding in enumerate(bindings):
            assert_op_idx = binding["assertion_index"]
            if isinstance(assert_op_idx, str):
                assert_op_idx = int(assert_op_idx)
            assertion_desc = operations[assert_op_idx - 1]["intent"]
            assert_op_id = operations[assert_op_idx - 1]["op_id"]
            binding["assertion_desc"] = assertion_desc
            binding["assertion_op_id"] = assert_op_id
            logger.log("ANALYZE INPUT-ASSERT BOUND", f"BINDING-{i}-ASSERT: {assertion_desc} ({binding['binding_confidence']})")
            logger.log("ANALYZE INPUT-ASSERT BOUND", f"BINDING-{i}-REASON: {binding['rationale']}")

        logger.log("ANALYZE INPUT-ASSERT BOUND", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return bindings

    @staticmethod
    def apply_input_assert_bound(script: Dict[str, Any], mutate_result: Dict[str, Any], bindings: List[Dict[str, Any]], threshold: float = 0.7):

        def generate_new_assertion(m, b, d):
            operations = script["operations"]
            input_op = mutate_result["original"]
            script_str = "\n".join(f"  [{i}] {op['intent']}" for i, op, in enumerate(operations, start=1))
            prompt = new_assertion_generate_prompt \
                .replace("{SCRIPT_OPERATIONS}", script_str) \
                .replace("{INPUT_INTENT}", input_op["intent"]) \
                .replace("{NEW_INPUT_TEXT}", m["value"]) \
                .replace("{ASSERTION_DESC}", b["assertion_desc"]) \
                .replace("{BINDING_REASON}", b["rationale"]) \
                .replace("{MUTATION_DESCRIPTION}", d)
            result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
            logger.log("GENERATE NEW ASSERT", f"ORIGIN: {b['assertion_desc']}")
            logger.log("GENERATE NEW ASSERT", f"REFERENCE: {b['rationale']}")
            logger.log("GENERATE NEW ASSERT", f"RESULT: {result['new_assertion']}")
            logger.log("GENERATE NEW ASSERT", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
            return result["new_assertion"]

        bindings = [binding for binding in bindings if binding["binding_confidence"] >= threshold]
        if len(bindings) == 0:
            for mutation in mutate_result["mutations"]:
                mutation["bindings"] = []
            return mutate_result

        for mutation in mutate_result["mutations"]:
            mutation_desc = (f"This is a mutation of {'valid' if mutation['valid'] else 'invalid'} type"
                f" for such a business-oriented input operation with specific input rule, since {mutation['reason']}.") \
                if mutate_result["input_type"] == "business-oriented" else \
                "This is a mutation for such a content-oriented input operation with no specific input rule."
            mutation["bindings"] = []
            for binding in bindings:
                new_assertion = generate_new_assertion(mutation, binding, mutation_desc)
                mutation["bindings"].append({
                    "assertion_idx": binding["assertion_index"],
                    "assertion_op_id": binding["assertion_op_id"],
                    "assertion_text": new_assertion
                })
        return mutate_result

    ##################################################################################

    def detect_mutation_point(
            self,
            db: Session,
            script_id: str,
            semantic_view: Dict[str, Any] | None = None,
    ):
        script_dict = self.get_script(db, script_id)
        script_folder = script_dict["script_folder"]
        operations = script_dict["operations"]
        semantic_view = semantic_view or self.get_semantic_view(db, script_id)
        script_str = "\n".join(f"  [{i+1}] {op['intent']}" for i, op, in enumerate(operations))
        candidates = []
        for i, op_dict in enumerate(operations):
            if op_dict["op_type"] == "tap":
                curr_screen = str(self.script_path / script_folder / op_dict["op_folder"] / "screen.jpeg")
                target_widget = str(self.script_path / script_folder / op_dict["op_folder"] / "widget.jpeg")
                prompt = mutation_point_candidate_filter_prompt \
                    .replace("{SCRIPT_OPERATIONS}", script_str) \
                    .replace("{CANDIDATE_OPERATION}", op_dict["intent"]) \
                    .replace(
                        "{DESCRIPTOR-PREFIX}",
                        json.dumps(
                            semantic_view.get("descriptors", [])[:i],
                            ensure_ascii=False,
                        ),
                    ) \
                    .replace(
                        "{CURRENT-DESCRIPTOR}",
                        json.dumps(
                            semantic_view.get("descriptors", [])[i],
                            ensure_ascii=False,
                        ),
                    ) \
                    .replace(
                        "{DESCRIPTOR-SUFFIX}",
                        json.dumps(
                            semantic_view.get("descriptors", [])[i + 1:],
                            ensure_ascii=False,
                        ),
                    )
                result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=[target_widget, curr_screen])
                logger.log("EVALUATE MUTATION POINT", f"STATE: {op_dict['op_id']} - {result['state_inference']}")
                logger.log("EVALUATE MUTATION POINT", f"SCORE & REASON: {result['branching_value_score']} & {result['reason']}")
                logger.log("EVALUATE MUTATION POINT", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
                score = int(result["branching_value_score"])
                if score >= 3:
                    candidates.append((
                        op_dict["op_id"],
                        score,
                        result["reason"],
                        i,
                        result.get("possible_branch_directions", []),
                    ))
            elif op_dict["op_type"] == "tap_input" or op_dict["op_type"] == "input":
                update_operation_mutate(db, op_dict["op_id"], "INPUT-DATA", "")
        # candidates.sort(key=lambda x: (-x[1], x[0]))

        def pick_candidates(_candidates):
            if len(_candidates) == 0:
                return []
            candidates_sorted = sorted(_candidates, key=lambda x: (-x[1], x[0]))
            max_score = candidates_sorted[0][1]
            top_group = [x for x in candidates_sorted if x[1] == max_score]
            picked = []

            def pick_from_group(group, k):
                g = sorted(group, key=lambda x: x[0])
                n = len(g)
                if k <= 0 or n == 0:
                    return []
                if n <= 2:
                    return g[:k]

                smallest = g[0]
                tier_random = g[1:4]
                tier_rest = g[4:]
                res = []
                if k > 0 and tier_random:
                    take = min(k, len(tier_random))
                    res.extend(random.sample(tier_random, take))
                    k -= take
                if k > 0 and tier_rest:
                    take = min(k, len(tier_rest))
                    res.extend(tier_rest[:take])
                    k -= take
                if k > 0:
                    res.append(smallest)
                    k -= 1
                return res

            picked.extend(pick_from_group(top_group, 2))
            if len(picked) < 2:
                next_score = max_score - 1
                next_group = [x for x in candidates_sorted if x[1] == next_score]
                picked.extend(pick_from_group(next_group, 1))
                # remain = [x for x in candidates_sorted if x not in picked]
                # picked.extend(remain[: (2 - len(picked))])
            return picked

        candidates = pick_candidates(candidates)
        branch_points = []
        for op_id, score, reason, index, directions in candidates[:2]:
            update_operation_mutate(db, op_id, "PATH", reason[:250])
            logger.log("SELECT MUTATION POINT", f"SCRIPT-OP-ID: {script_id}-{op_id}")
            goal = self.generate_mutation_goal(
                db,
                script_id,
                op_id,
                semantic_view=semantic_view,
            )
            branch_points.append({
                "index": index + 1,
                "op_id": op_id,
                "score": score,
                "rationale": reason,
                "possible_branch_directions": directions,
                **goal,
            })
        semantic_view["branch_points"] = branch_points
        semantic_view["seed_profile"] = summarize_seed_profile(
            operations,
            semantic_view.get("dependency_graph", {}).get("edges", []),
            branch_points,
        )
        self._write_json(
            self._script_artifact_path(script_id, self.semantic_view_filename),
            semantic_view,
        )
        return branch_points

    def generate_mutation_goal(
            self,
            db: Session,
            script_id: str,
            mutation_point_id: str,
            app_type: str = "",
            semantic_view: Dict[str, Any] | None = None,
    ):
        script_dict = self.get_script(db, script_id)
        script_folder = script_dict["script_folder"]
        operations = script_dict["operations"]
        semantic_view = semantic_view or self.get_semantic_view(db, script_id)
        mutation_point = [op for op in operations if op["op_id"] == mutation_point_id][0]
        mutation_index = next(
            index for index, op in enumerate(operations)
            if str(op["op_id"]) == str(mutation_point_id)
        )
        retained_operations = operations[:mutation_index + 1]
        script_str = "\n".join(f"  [{i}] {op['intent']}" for i, op, in enumerate(operations, start=1))
        retained_script_str = "\n".join(f"  [{i}] {op['intent']}" for i, op, in enumerate(retained_operations, start=1))
        branch_state_op = (
            operations[mutation_index + 1]
            if mutation_index + 1 < len(operations)
            else mutation_point
        )
        curr_screen = str(
            self.script_path
            / script_folder
            / branch_state_op["op_folder"]
            / "screen.jpeg"
        )
        branch_dependencies = [
            edge for edge in semantic_view.get("dependency_graph", {}).get("edges", [])
            if str(edge.get("src")) == str(mutation_point_id)
            or str(edge.get("dst")) == str(mutation_point_id)
        ]
        prompt = mutation_goal_decide_prompt \
            .replace("{APP_TYPE}", app_type) \
            .replace("{SCRIPT_OPERATIONS}", script_str) \
            .replace("{RETAINED_OPERATIONS}", retained_script_str) \
            .replace(
                "{SCENARIO-ABSTRACTION}",
                json.dumps(semantic_view.get("scenario", {}), ensure_ascii=False),
            ) \
            .replace(
                "{BRANCH-DEPENDENCIES}",
                json.dumps(branch_dependencies, ensure_ascii=False),
            )
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=curr_screen)
        logger.log("GENERATE MUTATION GOAL", f"GOAL: {result['goal']}")
        logger.log("GENERATE MUTATION GOAL", f"REASON: {result['reason']}")
        logger.log("GENERATE MUTATION GOAL", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return {
            "goal": result["goal"],
            "goal_reason": result.get("reason", ""),
            "discouraged_actions": result.get("discouraged_actions", []),
            "success_signals": result.get("success_signals", []),
            "terminal_evidence": result.get("terminal_evidence", []),
        }

    @staticmethod
    def formulate_input_adaptation_goal(
            semantic_view: Dict[str, Any],
            mutated_value: str,
            original_suffix: List[Dict[str, Any]],
            executed_trace: List[Dict[str, Any]],
            screenshot: str,
    ):
        prompt = input_suffix_adaptation_goal_prompt \
            .replace(
                "{SCENARIO}",
                json.dumps(semantic_view.get("scenario", {}), ensure_ascii=False),
            ) \
            .replace("{MUTATED-INPUT}", mutated_value) \
            .replace(
                "{ORIGINAL-SUFFIX}",
                json.dumps(original_suffix, ensure_ascii=False, default=str),
            ) \
            .replace(
                "{EXECUTED-TRACE}",
                json.dumps(executed_trace, ensure_ascii=False, default=str),
            )
        result, in_usage, out_usage, in_cost, out_cost = query(
            user_msg_txt=prompt,
            user_msg_img=screenshot,
        )
        logger.log(
            "FORMULATE INPUT ADAPTATION GOAL",
            f"GOAL: {result.get('goal', '')} | "
            f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)",
        )
        return {
            "goal": result.get("goal", ""),
            "expected_outcome": "ALTERNATIVE",
            "success_signals": result.get("success_signals", []),
            "reason": result.get("reason", ""),
        }

    @staticmethod
    def rank_widgets_goal_guided(test_goal: str, screen_bbox: str, k: int = 8):
        prompt = widget_rank_for_mutation_query_prompt.replace("{TEST_GOAL}", test_goal)
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=screen_bbox)
        ranked = []
        for item in result.get("rank_list", []):
            if item["score"] > 0.5:
                ranked.append(item)
        ranked = sorted(ranked, key=lambda x: (-x.get("score", 0.0), x.get("bbox_id", "")))
        for i, item in enumerate(ranked[:k]):
            logger.log("WIDGET RANKING", f"ITEM-{i}: {item}")
        logger.log("WIDGET RANKING", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return ranked[:k]

    def inject_assertion(
            self,
            db: Session,
            script_id: str,
            device_service: DeviceService,
            device_id: str,
            goal: str = "",
            generated_ops: List[Dict[str, Any]] | None = None,
    ):

        def get_screenshot_for_assertion(op_next: Dict[str, Any] | None):
            if op_next is None:
                return device_service.get_screenshot(device_id)
            else:
                script_folder = self.script_path / script_id
                op_folder = script_folder / op_next["op_folder"]
                ori_screen_path = op_folder / "screen.jpeg"
                dst_screen_path = self.screenshots_path / f"screen-{gen_timestamp()}.jpeg"
                shutil.copy(str(ori_screen_path), str(dst_screen_path))
                return str(dst_screen_path)

        script = self.get_script(db, script_id)
        operations = script["operations"]
        script_str = "\n".join(f"  [{i}] {op['intent']}" for i, op, in enumerate(operations, start=1))
        prompt = assertion_injection_locating_prompt.replace("{SCRIPT_OPERATIONS}", script_str)
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt)
        op_prev_idx = result["assertion_insertion_point"]["after_operation"]
        op_next_idx = result["assertion_insertion_point"]["before_operation"]
        if op_next_idx is not None:
            op_prev_id, op_next_id = \
                operations[op_prev_idx - 1]["op_id"], operations[op_next_idx - 1]["op_id"]
        else:
            op_prev_id, op_next_id = operations[op_prev_idx - 1]["op_id"], None
        logger.log("INSERT ASSERTION PREPARE", f"RESULT: after {op_prev_idx} & before {op_next_id}")
        logger.log("INSERT ASSERTION PREPARE", f"REASON: {result['reason']}")
        logger.log("INSERT ASSERTION PREPARE", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")

        op_prev_desc = operations[op_prev_idx - 1]["intent"]
        assertion_screen = get_screenshot_for_assertion(
            operations[op_next_idx - 1] if op_next_idx is not None else None)
        prompt = assertion_injection_generating_prompt \
            .replace("{OPERATION_DESCRIPTION}", op_prev_desc) \
            .replace("{BRANCH-GOAL}", goal or "not specified") \
            .replace(
                "{GENERATED-CONTINUATION}",
                json.dumps(generated_ops or [], ensure_ascii=False),
            )
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=assertion_screen)
        assertion_content = result["assertion_content"]
        assertion_info = {"text": assertion_content}
        assertion_intent = f"verify that \"\"\"{assertion_content}\"\"\""
        logger.log("INSERT ASSERTION EXECUTE", f"RESULT: {assertion_content}")
        logger.log("INSERT ASSERTION EXECUTE", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        return assertion_info, assertion_intent, assertion_screen, op_prev_id, op_next_id

    @staticmethod
    def check_mutation_state(goal: str, executed_ops: List[Dict[str, Any]], screenshot: str):
        if not goal.strip():
            raise ValueError("A non-empty branch goal is required for progress monitoring")
        mutate_operations_str = "\n".join(f"  [{i+1}] {op['intent']}" for i, op in enumerate(executed_ops))
        prompt = mutation_ending_check_prompt.replace("{TEST_GOAL}", goal) \
            .replace("{MUTATED_STEPS}", mutate_operations_str)
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=screenshot)
        logger.log("CHECK MUTATION END", f"RESULT & REASON: {result['judgement']} & {result['reason']}")
        logger.log("CHECK MUTATION END", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        status = str(result.get("judgement", "ONGOING")).upper()
        if status not in {"SATISFIED", "ONGOING"}:
            status = "ONGOING"
        return {
            "status": status,
            "reason": result.get("reason", ""),
        }

    def next_operation(
            self,
            db: Session,
            master_script_id: str,
            screen: str,
            screen_bbox: str,
            bboxes: Dict[str, Tuple],
            executed_op: List[Dict[str, Any]],
            goal: str,
            image_service: ImageService,
            source_op_id: str = "",
    ):
        progress = self.check_mutation_state(goal, executed_op, screen)
        if progress["status"] == "SATISFIED":
            return {"type": "end", "description": "mutation goal has been reached"}
        ranked = self.rank_widgets_goal_guided(goal, screen_bbox, k=8)
        ranked_idx = [item["bbox_id"] for item in ranked]
        screen_bbox = image_service.draw_bounding_boxes(screen, bboxes, ranked_idx)

        master_script = self.get_script(db, master_script_id)
        master_operations = master_script["operations"]
        source_index = next(
            (
                index for index, op in enumerate(master_operations)
                if str(op["op_id"]) == str(source_op_id)
            ),
            -1,
        )
        reference_operations = (
            master_operations[source_index + 1:]
            if source_index >= 0
            else master_operations
        )
        master_operations_str = "\n".join(
            f"[{i+1}] {op['intent']}" for i, op in enumerate(reference_operations)
        )
        mutate_operations_str = "\n".join(f"[{i+1}] {op['intent']}" for i, op in enumerate(executed_op))
        prompt = path_mutate_query_prompt.replace("{TEST_GOAL}", goal) \
            .replace("{ORIGINAL_SCRIPT}", master_operations_str) \
            .replace("{MUTATED_STEPS}", mutate_operations_str)
        result, in_usage, out_usage, in_cost, out_cost = query(user_msg_txt=prompt, user_msg_img=screen_bbox)
        logger.log("GENERATE NEXT ACTION", f"ACTION: {result['next_action']['type']} | {result['next_action']['target']} | {result['next_action']['text']}")
        logger.log("GENERATE NEXT ACTION", f"DESCRIPTION: {result['next_action']['description']}")
        logger.log("GENERATE NEXT ACTION", f"REASON: {result['reasoning']}")
        logger.log("GENERATE NEXT ACTION", f"COST: {in_usage}+{out_usage}(token), {in_cost}+{out_cost}($)")
        action = result["next_action"]
        valid, reason = validate_generated_action(action, bboxes)
        if not valid:
            return {"type": "invalid", "description": reason}
        return action

    ##################################################################################

    @staticmethod
    def get_script(db: Session, script_id: str) -> Dict[str, Any]:
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


if __name__ == "__main__":
    from app.services.implements.image_service_impl import ImageServiceImpl
    _screen = "/home/lyc/Projects/huawei-ui/HM-LIRAT/backend/data/screenshots/screenshot-1758523273.jpeg"
    ws = ImageServiceImpl()
    _screen_bbox, _bboxes = ws.get_screenshot_with_bbox(_screen)
    print(_screen_bbox)
    ms = MutationServiceImpl()
    _ranked = ms.rank_widgets_goal_guided("购买理财产品", _screen_bbox)
    print(_ranked)
    _ranked_idx = [item["bbox_id"] for item in _ranked]
    _screen_bbox = ws.draw_bounding_boxes(_screen, _bboxes, _ranked_idx)
    print(_screen_bbox)
