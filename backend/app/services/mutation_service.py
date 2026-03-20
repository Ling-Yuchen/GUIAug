from abc import ABC, abstractmethod
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.services.device_service import DeviceService
from app.services.image_service import ImageService


class MutationService(ABC):

    @abstractmethod
    def prepare(self, db: Session, script_id: str):
        ...

    @abstractmethod
    def generate_mutated_input_data(self, db: Session, script_id: str, op_id: str):
        ...

    @abstractmethod
    def set_mutation_point(self, db: Session, op_id: str, mutate_type: str, mutate_reason: str):
        ...

    @abstractmethod
    def next_operation(self, db: Session, master_script_id: str, screen: str, screen_bbox: str, bboxes: List, executed_op: List[Dict[str, Any]], goal: str, image_service: ImageService):
        ...

    @abstractmethod
    def inject_assertion(self, db: Session, script_id: str, device_service: DeviceService, device_id: str):
        ...
