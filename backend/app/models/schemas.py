from pydantic import BaseModel
from datetime import datetime


class ScriptModel(BaseModel):
    script_id: str
    script_name: str
    device_id: str
    app_id: str
    script_folder: str
    timestamp: datetime
    description: str
    mutate_ready: bool
    mutate_master: str
    mutating: bool

    class Config:
        from_attributes = True

class OperationModel(BaseModel):
    script_id: str
    op_id: str
    op_type: str
    op_params: str
    widget_bbox: str
    widget_desc: str
    op_folder: str
    timestamp: datetime
    package: str
    activity: str
    intent: str
    mutate_type: str
    mutate_reason: str

    class Config:
        from_attributes = True
