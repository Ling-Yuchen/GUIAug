import json
from collections import deque
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Dict, Any, Union

from PIL import Image
import xml.etree.ElementTree as ET

from app.utils.main import timeit


class BaseWidgetExtractor(ABC):

    @abstractmethod
    def extract(
            self,
            x: Union[int, Tuple[int, int]],
            y: Union[int, Tuple[int, int]],
            ui_dump_file: str,
            screenshot_file: str,
            widget_img_path: str,
            required_attr: List[str],
            reference_bounds: Optional[Tuple] = None,
    ):
        ...

    @abstractmethod
    def extract2(self, ui_dump_file: str, required_attr: List[str]):
        ...

    @staticmethod
    def extract3(x1: int, y1: int, x2: int, y2: int, screenshot_file: str, widget_img_path: str):
        screenshot = Image.open(screenshot_file)
        widget_img = screenshot.crop((x1, y1, x2, y2))
        widget_img.save(widget_img_path)


class AndroidWidgetExtractor(BaseWidgetExtractor):

    def extract2(self, ui_dump_file: str, required_attr: List[str]):
        def get_bounds(n: ET.Element) -> Optional[Tuple[int, int, int, int]]:
            bounds_str = n.attrib.get("bounds", None)
            if bounds_str:
                bounds = bounds_str.strip('[]').split('][')
                (_x1, _y1) = map(int, bounds[0].split(','))
                (_x2, _y2) = map(int, bounds[1].split(','))
                return _x1, _y1, _x2, _y2
            return None

        def is_leaf(n: ET.Element) -> bool:
            return len(list(n)) == 0

        def confirm_attrs(n: ET.Element, attrs: List[str]):
            if len(attrs) > 0:
                for attr in attrs:
                    attr_val = n.attrib.get(attr, None)
                    if attr_val != "true" and attr_val != True:
                        return False
            return True

        tree = ET.parse(ui_dump_file)
        root = tree.getroot()
        targets = []
        stack = [root]
        while stack:
            node = stack.pop()
            if confirm_attrs(node, required_attr):
                bounds = get_bounds(node)
                targets.append(bounds)
            if not is_leaf(node):
                stack.extend(list(node))
        return targets

    def extract(
            self,
            x: Union[int, Tuple[int, int]],
            y: Union[int, Tuple[int, int]],
            ui_dump_file: str,
            screenshot_file: str,
            widget_img_path: str,
            required_attr: List[str],
            reference_bounds: Optional[Tuple] = None
    ):
        def get_bounds(n: ET.Element) -> Optional[Tuple[int, int, int, int]]:
            bounds_str = n.attrib.get("bounds", None)
            if bounds_str:
                bounds = bounds_str.strip('[]').split('][')
                (_x1, _y1) = map(int, bounds[0].split(','))
                (_x2, _y2) = map(int, bounds[1].split(','))
                return _x1, _y1, _x2, _y2
            return None

        def is_within_bounds(_x: Union[int, Tuple[int, int]], _y: Union[int, Tuple[int, int]], bounds: Tuple) -> bool:
            if bounds is not None:
                _x1, _y1, _x2, _y2 = bounds
                if isinstance(_x, int) and isinstance(_y, int):
                    return _x1 <= _x <= _x2 and _y1 <= _y <= _y2
                elif isinstance(_x, tuple) and isinstance(_y, tuple):
                    _x_t1, _x_t2 = _x
                    _y_t1, _y_t2 = _y
                    _x_l, _x_r = min(_x_t1, _x_t2), max(_x_t1, _x_t2)
                    _y_l, _y_r = min(_y_t1, _y_t2), max(_y_t1, _y_t2)
                    return _x_l >= _x1 and _x_r <= _x2 and _y_l >= _y1 and _y_r <= _y2
            return False

        def is_leaf(n: ET.Element) -> bool:
            return len(list(n)) == 0

        def gen_xpath(n: ET.Element) -> str:
            xpath = "//*["
            text = n.attrib.get("text", "")
            clazz = n.attrib.get("class", "")
            resource_id = n.attrib.get("resource-id", "")
            content_desc = n.attrib.get("content-desc", "")

            if len(text) > 0:
                xpath += f"@text='{text}' and "
            if len(clazz) > 0:
                xpath += f"@class={clazz} and "
            if len(resource_id) > 0:
                xpath += f"@resource-id={resource_id} and "
            if len(content_desc) > 0:
                xpath += f"@content-desc={content_desc} and "
            xpath = xpath.strip(" and ")
            xpath += "]"
            return xpath

        def confirm_attrs(n: ET.Element, attrs: List[str]):
            if len(attrs) > 0:
                for attr in attrs:
                    attr_val = n.attrib.get(attr, None)
                    if attr_val != "true" and attr_val != True:
                        return False
            return True

        def get_smaller_element(n1: ET.Element, n2: ET.Element):
            if n1 is None and n2 is not None:
                return n2
            if n1 is not None and n2 is None:
                return n1
            if n1 is None and n2 is None:
                return None
            bounds1 = get_bounds(n1)
            bounds2 = get_bounds(n2)
            x11, y11, x12, y12 = bounds1
            x21, y21, x22, y22 = bounds2
            return n1 if (x12 - x11) * (y12 - y11) < (x22 - x21) * (y22 - y21) else n2

        tree = ET.parse(ui_dump_file)
        root = tree.getroot()
        result_node, result_node_xpath = None, None
        stack = [root]
        while stack:
            node = stack.pop()
            bbox = get_bounds(node)
            if bbox and is_within_bounds(x, y, bbox):
                if result_node is None:
                    if confirm_attrs(node, required_attr):
                        result_node = node
                    elif is_leaf(node):
                        result_node = node
                else:
                    result_node = get_smaller_element(result_node, node)
                # if is_leaf(node):
                #     break
            stack.extend(list(node))

        if result_node is not None:
            result_node_xpath = gen_xpath(result_node)
            x1, y1, x2, y2 = get_bounds(result_node)
            screenshot = Image.open(screenshot_file)
            widget_img = screenshot.crop((x1, y1, x2, y2))
            widget_img.save(widget_img_path)
        else:
            x1, y1, x2, y2 = -1, -1, -1, -1

        result_node_xpath = result_node_xpath if result_node_xpath is None or len(result_node_xpath) <= 250 else result_node_xpath[:250] + "..."
        return "", result_node_xpath, (x1, y1, x2, y2)
