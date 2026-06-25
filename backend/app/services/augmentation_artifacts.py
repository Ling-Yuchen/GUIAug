import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_dependencies(
        operations: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    positions = {str(op["op_id"]): index for index, op in enumerate(operations)}
    assertion_ids = {
        str(op["op_id"]) for op in operations if op["op_type"] == "assert"
    }
    valid_edges = []
    seen = set()
    for edge in dependencies:
        src, dst = str(edge.get("src", "")), str(edge.get("dst", ""))
        edge_type = str(edge.get("type", "")).lower()
        if src not in positions or dst not in positions:
            continue
        if edge_type not in {"state", "data", "oracle"}:
            continue
        if positions[src] >= positions[dst]:
            continue
        if edge_type == "oracle" and dst not in assertion_ids:
            continue
        key = (src, dst, edge_type)
        if key in seen:
            continue
        seen.add(key)
        valid_edges.append({
            "src": src,
            "dst": dst,
            "type": edge_type,
            "rationale": str(edge.get("rationale", "")),
        })
    return valid_edges


def validate_generated_action(
        action: Dict[str, Any],
        bboxes: Dict[str, Tuple],
) -> Tuple[bool, str]:
    action_type = action.get("type")
    if action_type not in {"tap", "input", "long_press", "back", "end"}:
        return False, f"unsupported action type: {action_type}"
    if action_type in {"tap", "long_press"}:
        target = str(action.get("target"))
        if target not in bboxes:
            return False, f"widget {target} is not available in the current state"
    if action_type == "input":
        target = action.get("target")
        if target is not None and str(target) not in bboxes:
            return False, f"widget {target} is not available in the current state"
        if action.get("text") is None:
            return False, "input action has no text"
    return True, ""


def summarize_seed_profile(
        operations: List[Dict[str, Any]],
        dependency_edges: List[Dict[str, Any]],
        branch_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    positions = {str(op["op_id"]): index for index, op in enumerate(operations)}
    state_depth = {str(op["op_id"]): 1 for op in operations}
    state_edges = sorted(
        (
            edge for edge in dependency_edges
            if edge.get("type") == "state"
            and str(edge.get("src")) in positions
            and str(edge.get("dst")) in positions
        ),
        key=lambda edge: positions[str(edge["dst"])],
    )
    for edge in state_edges:
        src, dst = str(edge["src"]), str(edge["dst"])
        state_depth[dst] = max(state_depth[dst], state_depth[src] + 1)

    input_count = sum(
        op.get("op_type") in {"tap_input", "input"} for op in operations
    )
    scores = [int(point.get("score", 0)) for point in branch_points]
    operation_count = len(operations)
    return {
        "operation_count": operation_count,
        "assertion_count": sum(
            op.get("op_type") == "assert" for op in operations
        ),
        "structural_depth": max(state_depth.values(), default=0),
        "input_richness": {
            "input_count": input_count,
            "input_ratio": input_count / operation_count if operation_count else 0.0,
        },
        "branchability": {
            "candidate_count": len(branch_points),
            "maximum_score": max(scores, default=0),
            "mean_score": sum(scores) / len(scores) if scores else 0.0,
        },
    }
