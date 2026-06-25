from app.services.augmentation_artifacts import (
    read_json,
    validate_dependencies,
    validate_generated_action,
    write_json_atomic,
)


def test_dependency_validation_keeps_only_forward_typed_edges():
    operations = [
        {"op_id": "10", "op_type": "tap"},
        {"op_id": "20", "op_type": "tap_input"},
        {"op_id": "30", "op_type": "assert"},
    ]
    edges = [
        {"src": "10", "dst": "20", "type": "state", "rationale": "opens form"},
        {"src": "20", "dst": "30", "type": "data", "rationale": "echoes input"},
        {"src": "20", "dst": "30", "type": "oracle", "rationale": "supports oracle"},
        {"src": "30", "dst": "10", "type": "state", "rationale": "backward"},
        {"src": "10", "dst": "20", "type": "oracle", "rationale": "not assertion"},
        {"src": "missing", "dst": "30", "type": "data", "rationale": "invalid id"},
    ]

    result = validate_dependencies(operations, edges)

    assert [(edge["src"], edge["dst"], edge["type"]) for edge in result] == [
        ("10", "20", "state"),
        ("20", "30", "data"),
        ("20", "30", "oracle"),
    ]


def test_generated_action_requires_available_widget_and_input_text():
    bboxes = {"1": (0, 0, 10, 10)}

    assert validate_generated_action({"type": "tap", "target": 1}, bboxes) == (True, "")
    assert validate_generated_action({"type": "tap", "target": 2}, bboxes)[0] is False
    assert validate_generated_action({"type": "input", "target": 1}, bboxes)[0] is False
    assert validate_generated_action(
        {"type": "input", "target": 1, "text": "query"},
        bboxes,
    ) == (True, "")


def test_json_artifact_round_trip(tmp_path):
    path = tmp_path / "script" / "semantic_view.json"
    payload = {"scenario": {"goal": "search"}, "branch_points": []}

    write_json_atomic(path, payload)

    assert read_json(path) == payload
