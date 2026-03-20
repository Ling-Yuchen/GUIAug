import os
from pathlib import Path
from os.path import join as p_join
from typing import Optional, List, Dict

import cv2
import numpy as np

from app.utils.llm import query
from app.utils.ui.detect_compo import ip_region_proposal as ip
from app.utils.ui.detect_text import text_detection as text
from app.utils.ui.detect_merge import merge as merge


class WidgetDetector:
    def __init__(self):
        self.img: Optional[np.ndarray] = None
        self.img_path: Optional[str] = None
        self.resize_length: int = 800
        self.output_root = str(Path(__file__).parent.parent.parent.parent.resolve() / "data" / "temp")

        """
            ele:min-grad: gradient threshold to produce binary map         
            ele:ffl-block: fill-flood threshold
            ele:min-ele-area: minimum area for selected elements 
            ele:merge-contained-ele: if True, merge elements contained in others
            text:max-word-inline-gap: words with smaller distance than the gap are counted as a line
            text:max-line-gap: lines with smaller distance than the gap are counted as a paragraph

            Tips:
            1. Larger *min-grad* produces fine-grained binary-map while prone to over-segment element to small pieces
            2. Smaller *min-ele-area* leaves tiny elements while prone to produce noises
            3. If not *merge-contained-ele*, the elements inside others will be recognized, while prone to produce noises
            4. The *max-word-inline-gap* and *max-line-gap* should be dependent on the input image size and resolution

            mobile: {'min-grad':4, 'ffl-block':5, 'min-ele-area':50, 'max-word-inline-gap':6, 'max-line-gap':1}
            web   : {'min-grad':3, 'ffl-block':5, 'min-ele-area':25, 'max-word-inline-gap':4, 'max-line-gap':4}
        """
        self.key_params = {
            "min-grad": 10,
            "ffl-block": 5,
            "min-ele-area": 50,
            "merge-contained-ele": True,
            "merge-line-to-paragraph": True,
            "remove-bar": True,
        }

    def detect(
            self,
            img_path: Optional[str],
            debug: bool = False,
            ocr_only: bool = False,
    ):
        """
        @return img_res_path: 控件识别结果的可视化展示
        @return resize_ratio: 对原始屏幕截图进行resize的比例
        @return elements["compos"]: 控件识别结果列表
        """
        if img_path is not None:
            self.img_path = img_path

        if img_path is None or \
                not os.path.exists(img_path):
            raise Exception("No Image for Detection.")

        self.img = cv2.imread(self.img_path)

        if not ocr_only:
            texts_json = self.detect_ocr()
            compos_json = self.detect_compo()
            img_res_path, resize_ratio, elements = self.detect_merge(compos_json, texts_json, debug)
            # img_res_path, widgets = self.detect_optimize(img_path, img_res_path, elements["compos"])
            return img_res_path, resize_ratio, elements["compos"]
            # return img_res_path, resize_ratio, widgets
        else:
            texts_json = self.detect_ocr()
            texts_list = texts_json["texts"]
            return [item["content"] for item in texts_list]

    def detect_ocr(self):
        return text.text_detection(
            self.img_path,
            self.output_root,
            show=False,
        )

    def detect_compo(self):
        return ip.compo_detection(
            self.img_path,
            self.output_root,
            self.key_params,
            resize_by_height=self.resize_length,
            show=False,
        )

    def detect_merge(self, compos_json, texts_json, debug: bool = False):
        screen_with_bbox_path, elements, resize_ratio = merge.merge(
            self.img_path,
            compos_json,
            texts_json,
            p_join(self.output_root, "merge"),
            is_remove_bar=self.key_params['remove-bar'],
            is_paragraph=self.key_params['merge-line-to-paragraph'],
            show=debug,
        )
        return screen_with_bbox_path, resize_ratio, elements

    def detect_optimize(self, screenshot_path, screenshot_bbox_path, widgets):
        """deprecated"""

        def get_widget_by_id(all_widgets: List[Dict], widget_id: int):
            _widget = [w for w in all_widgets if w["id"] == widget_id]
            return _widget[0] if len(_widget) > 0 else None

        widget_filter_prompt = """
You are given a screenshot annotated with bounding boxes and index numbers for each detected widget.

Your task is to **identify all widgets that are likely to be interactable**, i.e., UI elements that users can operate.
You should **generally avoid** including:
- Clearly non-interactable elements, such as large blocks of descriptive text, decorative dividers, etc.
- Broken fragments or visual noise, such as misidentified regions that are not valid widgets
- Widgets blocked by top-level windows, which are visible but not interactable due to being underneath a higher-layer UI element

Return a JSON object in the following format: `{ "result": [<list of indices of interactable widgets>] }`
""".strip()
        result, _, _, _, _ = query(user_msg_txt=widget_filter_prompt, user_msg_img=screenshot_bbox_path)
        indices_reserved, widgets_reserved = result["result"], []
        for i, item in enumerate(indices_reserved):
            widget = get_widget_by_id(widgets, item)
            if widget is not None:
                widget["id"] = i
                widgets_reserved.append(widget)

        screen = cv2.imread(screenshot_path)
        for widget in widgets_reserved:
            x1, y1 = widget["position"]["column_min"], widget["position"]["row_min"]
            x2, y2 = widget["position"]["column_max"], widget["position"]["row_max"]
            x1, y1 = max(0, x1 - 3), max(0, y1 - 3)
            x2 = min(screen.shape[1], x2 + 3)
            y2 = min(screen.shape[0], y2 + 3)
            cv2.rectangle(screen, (x1, y1), (x2, y2), (0, 255, 0), 2)
            x0, y0 = max(x1 - 10, 0), min(y1 + 10, screen.shape[0])
            x0 = max(x1 - 20, 0) if widget["id"] >= 10 else x0
            cv2.putText(screen, f"{widget['id']}", (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 6)
            cv2.putText(screen, f"{widget['id']}", (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)

        name = self.img_path.split('/')[-1][:-5]
        img_res_path = p_join(self.output_root, "post", str(name) + ".jpeg")
        cv2.imwrite(img_res_path, screen)
        return img_res_path, widgets_reserved

    def _resize_height_by_longest_edge(self):
        if self.img is None:
            raise Exception("No Image for Detection.")
        height, width = self.img.shape[:2]
        if height > width:
            return self.resize_length
        else:
            return int(self.resize_length * (height / width))


if __name__ == "__main__":
    w = WidgetDetector()
    w.detect("/home/lyc/Projects/huawei-ui/HM-LIRAT/backend/data/screenshots/screenshot-1759578415.jpeg")