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


class HarmonyWidgetExtractor(BaseWidgetExtractor):

    @timeit
    def extract2(self, ui_dump_file: str, required_attr: List[str]):
        page = json.load(open(ui_dump_file))
        dq = deque()
        dq.append(page)
        targets = []
        while len(dq) > 0:
            element = dq.popleft()
            if self.confirm_attrs(element, required_attr):
                bounds = self.get_bounds(element)
                targets.append(bounds)
            if not self.is_leaf(element):
                for child in element.get("children"):
                    dq.append(child)
        return targets

    @timeit
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
        with open(ui_dump_file, 'r', encoding='utf-8') as f:
            page = json.load(f)
        dq = deque()
        dq.append(page)
        target = None
        while len(dq) > 0:
            element = dq.popleft()
            bounds = self.get_bounds(element)
            if self.is_within_bounds(x, y, bounds):
                if target is None:
                    if self.confirm_attrs(element, required_attr):
                        target = element
                    elif self.is_leaf(element):
                        target = element
                else:
                    target = self.get_smaller_element(element, target)
            if not self.is_leaf(element):
                for child in element.get("children"):
                    dq.append(child)

        if target is not None:
            x1, y1, x2, y2 = self.get_bounds(target, reference_bounds)
            screenshot = Image.open(screenshot_file)
            widget_img = screenshot.crop((x1, y1, x2, y2))
            widget_img.save(widget_img_path)
        else:
            x1, y1, x2, y2 = -1, -1, -1, -1

        target_type, target_desc = self.gen_desc_v2(target)
        target_desc = target_desc[:250] + "..." if len(target_desc) > 250 else target_desc
        return target_type, target_desc, (x1, y1, x2, y2)

    @staticmethod
    def get_bounds(element: Dict[str, Any], reference: Optional[Tuple] = None) -> Optional[Tuple[int, int, int, int]]:
        try:
            bounds_str: str = element["attributes"]["bounds"]
            bounds = bounds_str.strip("[]").replace("][", ",").split(",")
            x1, y1, x2, y2 = map(int, bounds)
            if reference is not None:
                ...
            return x1, y1, x2, y2
        except Exception as e:
            print("Error in get_bounds", e)
            return None

    @staticmethod
    def is_within_bounds(
            x: Union[int, Tuple[int, int]],
            y: Union[int, Tuple[int, int]],
            bounds: Optional[Tuple],
    ) -> bool:
        if bounds is not None:
            x1, y1, x2, y2 = bounds
            if isinstance(x, int) and isinstance(y, int):
                return x1 <= x <= x2 and y1 <= y <= y2
            elif isinstance(x, tuple) and isinstance(y, tuple):
                x_t1, x_t2 = x
                y_t1, y_t2 = y
                x_l, x_r = min(x_t1, x_t2), max(x_t1, x_t2)
                y_l, y_r = min(y_t1, y_t2), max(y_t1, y_t2)
                return x_l >= x1 and x_r <= x2 and y_l >= y1 and y_r <= y2
        return False

    @staticmethod
    def is_leaf(element: Dict[str, Any]) -> bool:
        children = element.get("children")
        return children is None or len(children) == 0

    def gen_desc(self, element: Dict[str, Any]):
        if element is None:
            return ""
        w_type = element["attributes"].get("type")
        w_text = element["attributes"].get("text")
        w_hint = element["attributes"].get("hint")
        w_desc = element["attributes"].get("description")
        desc = f"#[{w_type}]"
        desc += f" with hint [{w_hint}]" if w_hint is not None and len(w_hint) > 0 else ""
        desc += f" with text [{w_text}]" if w_text is not None and len(w_text) > 0 else ""
        desc += f" with desc [{w_desc}]" if w_desc is not None and len(w_desc) > 0 else ""
        if not self.is_leaf(element):
            desc += " CONTAINS {"
            for child in element.get("children"):
                desc += f"{self.gen_desc(child)}, "
            desc = desc.strip().strip(",") + "}"
        return desc

    def gen_desc_v2(self, element: Dict[str, Any]):

        def get_labels(e: Dict[str, Any]) -> List[str]:
            labels = []
            element_queue = deque()
            element_queue.append(e)
            while len(element_queue) > 0:
                curr_e = element_queue.popleft()
                w_text = curr_e["attributes"].get("text")
                w_hint = curr_e["attributes"].get("hint")
                w_desc = curr_e["attributes"].get("description")
                if w_text is not None and len(w_text) > 0:
                    labels.append(w_text)
                if w_hint is not None and len(w_hint) > 0:
                    labels.append(w_hint)
                if w_desc is not None and len(w_desc) > 0:
                    labels.append(w_desc)
                if not self.is_leaf(curr_e):
                    for child in curr_e.get("children"):
                        element_queue.append(child)
            return labels

        if element is None:
            return "", ""
        w_type = element["attributes"].get("type")
        w_labels = get_labels(element)
        desc = f"#{w_type}"
        if len(w_labels) > 0:
            desc += f"[{','.join(w_labels)}]"
        return w_type, desc

    @staticmethod
    def confirm_attrs(element: Dict[str, Any], attrs: List[str]):
        if len(attrs) > 0:
            for attr in attrs:
                attr_val = element["attributes"][attr]
                if attr_val != "true":
                    return False
        return True

    def get_smaller_element(self, element1: Optional[Dict[str, Any]], element2: Optional[Dict[str, Any]]):
        if element1 is None and element2 is not None:
            return element2
        if element1 is not None and element2 is None:
            return element1
        if element1 is None and element2 is None:
            return None
        bounds1 = self.get_bounds(element1)
        bounds2 = self.get_bounds(element2)
        x11, y11, x12, y12 = bounds1
        x21, y21, x22, y22 = bounds2
        # if x21 <= x11 and y21 <= y11 and x22 >= x12 and y22 >= y12:
        #     return element1
        # if x11 <= x21 and y11 <= y21 and x12 >= x22 and y12 >= y22:
        #     return element2
        return element1 if (x12 - x11) * (y12 - y11) \
                < (x22 - x21) * (y22 - y21) else element2


