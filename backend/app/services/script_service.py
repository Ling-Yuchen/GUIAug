from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union

from sqlalchemy.orm import Session


class ScriptService(ABC):

    @abstractmethod
    def init_script(self, db: Session, script_name: str, device_id: str, app_id: str, mutate_master: Optional[str] = None, mutating: bool = False) -> Dict[str, Any]:
        ...

    @abstractmethod
    def record_tap(self, db: Session, script_id: str, x: int, y: int, script_folder: str, screen_path: str, ui_dump_path: str, package: str, activity: str, op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def record_tap_input(self, db: Session, script_id: str, x: int, y: int, text: str, script_folder: str, screen_path: str, ui_dump_path: str, package: str, activity: str, op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def record_scroll(self, db: Session, script_id: str, x1: int, y1: int, x2: int, y2: int, duration: int, script_folder: str, screen_path: str, ui_dump_path: str, package: str, activity: str, op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def record_long_press(self, db: Session, script_id: str, x: int, y: int, script_folder: str, screen_path: str, ui_dump_path: str, package: str, activity: str, op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def record_back(self, db: Session, script_id: str, script_folder: str, screen_path: str, ui_dump_path: str, package: str, activity: str, op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def record_oracle(self, db: Session, script_id: str, script_folder: str, screen_path: str, assertion_info: Dict[str, Any], op_prev: Optional[str], op_next: Optional[str], intent: str = ""):
        ...

    @abstractmethod
    def remove_op_from_db(self, db: Session, op_id: str, script_id: str):
        ...

    @abstractmethod
    def get_script(self, db: Session, script_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_script_path(self):
        ...

    @abstractmethod
    def get_scripts(self, db: Session):
        ...

    @abstractmethod
    def delete_script(self, db: Session, script_id: str):
        ...

    @abstractmethod
    def update_op_params(self, db: Session, op_id: str, params: List[Union[int, str]]):
        ...

    @abstractmethod
    def describe_script_in_natural_language(self, db: Session, script_id: str):
        ...
