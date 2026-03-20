from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, cast
from sqlalchemy.orm import Session
from app.models.db_models import Script, Operation
from app.models.schemas import ScriptModel, OperationModel


def create_script(db: Session, script: ScriptModel):
    db_script = Script(**script.model_dump())
    db.add(db_script)
    db.commit()
    db.refresh(db_script)
    return db_script

def create_operation(db: Session, operation: OperationModel):
    db_operation = Operation(**operation.model_dump())
    db.add(db_operation)
    db.commit()
    db.refresh(db_operation)
    return db_operation

def get_operation_by_id(db: Session, step_id: str):
    operation = db.query(Operation).filter(Operation.op_id == step_id).first()
    return operation

def get_step_folder_from_id(db: Session, step_id: str):
    operation = db.query(Operation).filter(Operation.op_id == step_id).first()
    return operation.op_folder if operation else None

def get_script_folder_from_op_id(db: Session, step_id: str):
    operation = db.query(Operation).filter(Operation.op_id == step_id).first()
    if operation:
        script_id = operation.script_id
        script = db.query(Script).filter(Script.script_id == script_id).first()
        return script.script_folder if script else None
    return None

def get_script_folder_from_id(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    return script.script_folder if script else None

def get_device_app_from_id(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    return script.device_id, script.app_id if script else None, None

def get_script(db: Session, script_id: str):
    return db.query(Script).filter(Script.script_id == script_id).first()

def get_all_scripts(db: Session, skip: int = 0, limit: int = 1000):
    return db.query(Script).offset(skip).limit(limit).all()

def get_script_with_operations(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if not script:
        return None, []
    operations = db.query(Operation) \
        .filter(Operation.script_id == script_id) \
        .order_by(cast(Operation.op_id, Integer)).all()
    return script, operations

def get_master_script_with_operations(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if not script:
        return None, []
    master_script_id = str(script.mutate_master)
    if master_script_id == "":
        return None, []
    return get_script_with_operations(db, master_script_id)


def delete_script(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        db.query(Operation).filter(Operation.script_id == script_id).delete()
        db.delete(script)
        db.commit()

def delete_operation(db: Session, op_id: str):
    operation = db.query(Operation).filter(Operation.op_id == op_id).first()
    if operation:
        db.delete(operation)
        db.commit()

def update_operation_params(db: Session, op_id: str, new_params: str):
    operation = db.query(Operation).filter(Operation.op_id == op_id).first()
    if operation:
        operation.op_params = new_params
        db.commit()
        db.refresh(operation)

def update_script_name(db: Session, script_id: str, new_name: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        script.script_name = new_name
        db.commit()
        db.refresh(script)

def update_script_desc(db: Session, script_id: str, new_desc: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        script.description = new_desc
        db.commit()
        db.refresh(script)

def update_script_mutate(db: Session, script_id: str, val: bool):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        script.mutated_ready = val
        db.commit()
        db.refresh(script)

def update_script_mutating(db: Session, script_id: str, val: bool):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        script.mutating = val
        db.commit()
        db.refresh(script)

def update_script_description(db: Session, script_id: str, desc: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    if script:
        script.description = desc
        db.commit()
        db.refresh(script)

def update_operation_intent(db: Session, op_id: str, intent: str):
    operation = db.query(Operation).filter(Operation.op_id == op_id).first()
    if operation:
        operation.intent = intent
        db.commit()
        db.refresh(operation)

def update_operation_mutate(db: Session, op_id: str, mtype: str, reason: Optional[str] = None):
    operation = db.query(Operation).filter(Operation.op_id == op_id).first()
    if operation:
        operation.mutate_type = mtype
        if reason is not None:
            operation.mutate_reason = reason
        db.commit()

def get_script_mutate(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    return script.mutate_ready if script else None

def get_script_description(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    return script.description if script else None

def copy_operation(db: Session, op_id: str, new_script_id: str, new_op_id: str):
    operation = db.query(Operation).filter(Operation.op_id == op_id).first()
    if operation:
        new_operation_data = {
            "script_id": new_script_id,
            "op_id": new_op_id,
            "op_type": operation.op_type,
            "op_params": operation.op_params,
            "widget_bbox": operation.widget_bbox,
            "widget_desc": operation.widget_desc,
            "op_folder": new_op_id,
            "timestamp": datetime.now(),
            "package": operation.package,
            "activity": operation.activity,
            "intent": operation.intent,
            "mutate_type": "NONE",
            "mutate_reason": "",
        }
        new_operation = OperationModel(**new_operation_data)
        return create_operation(db, new_operation)

def get_scenario_by_script_id(db: Session, script_id: str):
    script = db.query(Script).filter(Script.script_id == script_id).first()
    operations = db.query(Operation).filter(Operation.script_id == script_id).all()
    intentions = [op.intent for op in operations if op.intent is not None]
    return script.description, intentions

def update_intention_by_step_id(db: Session, step_id: str, new_intention: str):
    operation = db.query(Operation).filter(Operation.op_id == step_id).first()
    if operation:
        operation.intent = new_intention
        db.commit()
        db.refresh(operation)

