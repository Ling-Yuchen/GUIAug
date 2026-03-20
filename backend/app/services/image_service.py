from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple, List, Dict


class ImageService(ABC):

    @abstractmethod
    def get_image_base64(self, image_path: str, max_height: Optional[int] = None, max_width: Optional[int] = None) -> str:
        ...

    @abstractmethod
    def widget_image_match(self, screenshot_path: str, widget_image_path: str):
        ...

    @abstractmethod
    def widget_layout_match(self, screenshot_path_src: str, screenshot_path_dst: str, x: int, y: int):
        ...

    @abstractmethod
    def widget_semantic_match(self, screenshot_path_src: str, screenshot_path_dst: str, widget_image_path: str):
        ...

    @abstractmethod
    def widget_template_match(self, screenshot_path: str, widget_image_path: str, threshold: float = 0.8):
        ...

    @abstractmethod
    def detect_page_change(self, image_path1: str, image_path2: str, threshold: float):
        ...

    @abstractmethod
    def oracle_text_match(self, screenshot_path: str, target_text: str, supplement: Any):
        ...

    @abstractmethod
    def get_screenshot_with_bbox(self, screenshot_path: str):
        ...

    @abstractmethod
    def check_match_validity(self, kernel: Tuple[int, int], match_result: Tuple[int, int], screenshot_path_src: str, screenshot_path_dst: str, threshold: float = 0.15, mode: str = "square"):
        ...

    @abstractmethod
    def draw_bounding_boxes(self, screenshot_path: str, bboxes: Dict[str, Tuple], candidate_idx: Optional[List]):
        ...

    @abstractmethod
    def do_semantic_assertion(self, screenshot_path: str, assertion_text: str):
        ...
