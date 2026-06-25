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
    def get_semantic_view(self, db: Session, script_id: str, refresh: bool = False):
        ...

    @abstractmethod
    def generate_mutation_goal(
            self,
            db: Session,
            script_id: str,
            mutation_point_id: str,
            app_type: str = "",
            semantic_view=None,
    ):
        ...

    @abstractmethod
    def formulate_input_adaptation_goal(
            self,
            semantic_view,
            mutated_value: str,
            original_suffix,
            executed_trace,
            screenshot: str,
    ):
        ...

    @abstractmethod
    def generate_mutated_input_data(self, db: Session, script_id: str, op_id: str):
        ...

    @abstractmethod
    def set_mutation_point(self, db: Session, op_id: str, mutate_type: str, mutate_reason: str):
        ...

    @abstractmethod
    def next_operation(
            self,
            db: Session,
            master_script_id: str,
            screen: str,
            screen_bbox: str,
            bboxes: List,
            executed_op: List[Dict[str, Any]],
            goal: str,
            image_service: ImageService,
            source_op_id: str = "",
    ):
        ...

    @abstractmethod
    def inject_assertion(
            self,
            db: Session,
            script_id: str,
            device_service: DeviceService,
            device_id: str,
            goal: str = "",
            generated_ops=None,
    ):
        ...

    @abstractmethod
    def initialize_augmentation_context(
            self,
            script_id: str,
            module: str,
            master_script_id: str,
            source_op_id: str,
            **metadata,
    ):
        ...

    @abstractmethod
    def get_augmentation_context(self, script_id: str):
        ...

    @abstractmethod
    def update_augmentation_context(self, script_id: str, **updates):
        ...
