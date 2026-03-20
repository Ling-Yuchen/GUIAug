import io
import base64
from collections import deque
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any

import cv2
import numpy as np
from PIL import Image

from app.services.image_service import ImageService
from app.prompt import widget_semantic_match_prompt, operation_desc_generate_prompt, oracle_text_match_prompt, \
    semantic_assertion_prompt

from app.utils.llm import query
from app.utils.main import timeit, gen_timestamp
from app.utils.ui.detect import WidgetDetector


class ImageServiceImpl(ImageService):

    widget_detector: WidgetDetector = WidgetDetector()
    temp_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "temp"
    screenshot_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "screenshots"
    widget_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "temp"

    def get_image_base64(self, image_path: str, max_height: Optional[int] = None, max_width: Optional[int] = None) -> str:
        try:
            img = Image.open(image_path)
            w, h = img.size
            if max_height is not None and h > max_height:
                img = img.resize((w * max_height // h, max_height))
            w, h = img.size
            if max_width is not None and w > max_width:
                img = img.resize((max_width, h * max_width // w))
            if img.mode == "RGBA":
                img = img.convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            image_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return image_str
        except:
            return ""

    def do_semantic_assertion(self, screenshot_path: str, assertion_text: str):
        prompt = semantic_assertion_prompt.replace("{ASSERTION_TEXT}", assertion_text)
        print(prompt)
        result, *_ = query(user_msg_txt=prompt, user_msg_img=screenshot_path)
        return result["assertion_pass"], result["reason"]

    @timeit
    def oracle_text_match(self, screenshot_path: str, target_text: str, supplement: Dict[str, Any]):
        match_result = self.oracle_text_match_by_supplement(target_text, supplement)
        if not match_result:
            match_result = self.oracle_text_match_by_screenshot(target_text, screenshot_path)
        return match_result

    def oracle_text_match_by_screenshot(self, target_text: str, screenshot_path: str):
        screen_texts = self.widget_detector.detect(screenshot_path, ocr_only=True)
        prompt = oracle_text_match_prompt.replace("{TARGET_TEXT}", target_text) \
                    .replace("{EXTRACTED_TEXT}", "; ".join(screen_texts))
        result, *_ = query(
            user_msg_txt=prompt,
            user_msg_img=screenshot_path,
            model="gpt-4.1",
            # model="qwen-vl-max"
        )
        return result["result"]

    @staticmethod
    def oracle_text_match_by_supplement(target_text: str, supplement: Dict[str, Any]):
        page = supplement
        dq = deque()
        dq.append(page)
        while len(dq) > 0:
            element = dq.popleft()
            t1 = element["attributes"].get("text")
            t2 = element["attributes"].get("hint")
            t3 = element["attributes"].get("description")
            t1 = "" if t1 is None else t1
            t2 = "" if t2 is None else t2
            t3 = "" if t3 is None else t3
            if target_text in t3 or target_text in t2 or target_text in t1:
                return True
            for child in element.get("children"):
                dq.append(child)
        return False

    @timeit
    def detect_page_change(self, image_path1: str, image_path2: str, threshold: float = 0.3) -> bool:

        def detect_edges_and_mask(img):
            v = np.median(img)
            canny_sigma = 0.33
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(img, int(max(0, (1 - canny_sigma) * v)), int(min(255, (1 + canny_sigma) * v)))  # Canny 边缘检测
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            mask = np.zeros_like(img, dtype=np.uint8)
            cv2.drawContours(mask, contours, -1, (255), thickness=cv2.FILLED)  # 用轮廓填充掩膜
            return edges, mask

        target_size = (1080, 1920)
        img1 = cv2.imread(image_path1)
        img1 = cv2.resize(img1, target_size, interpolation=cv2.INTER_AREA)
        img2 = cv2.imread(image_path2)
        img2 = cv2.resize(img2, target_size, interpolation=cv2.INTER_AREA)
        _, mask1 = detect_edges_and_mask(img1)
        _, mask2 = detect_edges_and_mask(img2)
        union_mask = cv2.bitwise_or(mask1, mask2)
        # 应用并集掩膜
        img1_masked = cv2.bitwise_and(img1, img1, mask=union_mask)
        img2_masked = cv2.bitwise_and(img2, img2, mask=union_mask)
        # 计算像素差异
        diff = cv2.absdiff(img1_masked, img2_masked)
        total_diff = np.sum(diff)  # 差异的总和
        # 计算掩膜覆盖的像素数
        non_zero_pixels = np.count_nonzero(union_mask)
        # 最大可能差异值（255 * 3 是每个像素的最大可能差异值）
        max_possible_diff = non_zero_pixels * 255 * 3
        # 计算相对差异
        relative_diff = total_diff / max_possible_diff if max_possible_diff > 0 else 0
        print(f"相对像素差异值: {relative_diff:.4f}")
        return relative_diff > threshold

    @timeit
    def get_screenshot_with_bbox(self, screenshot_path: str):
        screen_bbox, _, components = self.widget_detector.detect(screenshot_path)
        bboxes = {}
        for compo in components:
            box_id = str(compo["id"])
            x1 = compo["position"]["column_min"]
            x2 = compo["position"]["column_max"]
            y1 = compo["position"]["row_min"]
            y2 = compo["position"]["row_max"]
            bboxes[box_id] = (x1, y1, x2, y2)
        return screen_bbox, bboxes

    @timeit
    def widget_image_match(
            self,
            screenshot_path: str,
            widget_image_path: str,
    ) -> Tuple[Optional[int], Optional[int], Optional[Tuple]]:
        widget = cv2.imread(widget_image_path)
        screen = cv2.imread(screenshot_path)
        screen_height, screen_width, _ = screen.shape
        if widget is None or screen is None:
            return None, None, None

        # 将图像转换为灰度图
        widget_grey = cv2.cvtColor(widget, cv2.COLOR_BGR2GRAY)
        screen_grey = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        widget_grey = cv2.GaussianBlur(widget_grey, (3, 3), 0)
        screen_grey = cv2.GaussianBlur(screen_grey, (3, 3), 0)

        # 创建sift引用，并计算各自特征点
        sift = cv2.SIFT_create()
        widget_kp, widget_desc = sift.detectAndCompute(widget_grey, None)
        screen_kp, screen_desc = sift.detectAndCompute(screen_grey, None)

        # 绘出灰度图及特征点的图像
        # widget = cv2.drawKeypoints(widget_grey, widget_kp, widget)
        # screen = cv2.drawKeypoints(screen_grey, screen_kp, screen)

        # FLANN特征匹配
        FLANN_INDEX_KDTREE = 0
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)

        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(widget_desc, screen_desc, k=2)

        # 计算特征点之间的最小、最大的距离
        max_distance = min_distance = 0.0
        for i, j in matches:
            if i.distance < min_distance:
                min_distance = i.distance
            if i.distance > max_distance:
                max_distance = i.distance

        goodMatch = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                goodMatch.append(m)

        try:
            src_pts = np.float32([widget_kp[m.queryIdx].pt for m in goodMatch]).reshape(-1, 1, 2)
            dst_pts = np.float32([screen_kp[m.trainIdx].pt for m in goodMatch]).reshape(-1, 1, 2)
            if len(src_pts) < 4 or len(dst_pts) < 4:
                print("Not enough matches to compute homography.")
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if M is None:
                print("Homography could not be computed.")
            # matchesMask = mask.ravel().tolist()
            h, w = widget_grey.shape
            pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
            dst = cv2.perspectiveTransform(pts, M)
            x1 = int(min(dst[0][0][0], dst[1][0][0]))
            y1 = int(min(dst[0][0][1], dst[3][0][1]))
            x2 = int(max(dst[2][0][0], dst[3][0][0]))
            y2 = int(max(dst[1][0][1], dst[2][0][1]))
            center_x = center_y = 0.0
            for i in range(len(dst)):
                center_x = center_x + dst[i][0][0]
                center_y = center_y + dst[i][0][1]
            if round(center_x / 4) < 0 or round(center_y / 4) < 0 \
                    or round(center_x / 4) > screen_width or round(center_y / 4) > screen_height:
                print("invalid coordinates")
                return None, None, None
            return round(center_x / 4), round(center_y / 4), (x1, y1, x2, y2)
        except Exception as e:
            print(e)
            return None, None, None

    @timeit
    def widget_template_match(
            self,
            screenshot_path: str,
            widget_image_path: str,
            threshold: float = 0.8,
    ) -> Tuple[Optional[int], Optional[int], Optional[Tuple]]:
        widget = cv2.imread(widget_image_path)
        screen = cv2.imread(screenshot_path)
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        widget_gray = cv2.cvtColor(widget, cv2.COLOR_BGR2GRAY)
        widget_w, widget_h = widget_gray.shape[::-1]

        result = cv2.matchTemplate(screen_gray, widget_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold:
            x1, y1 = max_loc
            x2, y2 = x1 + widget_w, y1 + widget_h
            x_c, y_c = (x1 + x2) // 2, (y1 + y2) // 2
            return x_c, y_c, (x1, y1, x2, y2)
        return None, None, None

    @timeit
    def widget_semantic_match(
            self,
            screenshot_path_src: str,
            screenshot_path_dst: str,
            widget_image_path: str,
    ) -> Tuple[Optional[int], Optional[int], Optional[Tuple]]:
        widget_desc = query(
            user_msg_txt=operation_desc_generate_prompt,
            user_msg_img=[screenshot_path_src, widget_image_path],
            model="gpt-4.1",
            # model="qwen-vl-max",
        )[0]["result"]
        screen_dst_bbox, bboxes = self.get_screenshot_with_bbox(screenshot_path_dst)
        result, _, _, _, _ = query(
            system_msg=widget_semantic_match_prompt,
            user_msg_txt=f"Operation description: {widget_desc}",
            user_msg_img=screen_dst_bbox,
            model="gpt-4.1",
            # model="qwen-vl-max"
        )
        print(result)
        target_idx = result["match_number"]
        if target_idx == -1:
            return None, None, None
        try:
            x1, y1, x2, y2 = bboxes[str(target_idx)]
            x_c, y_c = (x1 + x2) // 2, (y1 + y2) // 2
            return x_c, y_c, (x1, y1, x2, y2)
        except KeyError as e:
            print(f"error: {e}")
            return None, None, None

    @timeit
    def widget_layout_match(
            self,
            screenshot_path_src: str,
            screenshot_path_dst: str,
            x: int,
            y: int,
    ) -> Tuple[Optional[int], Optional[int], Optional[Tuple]]:

        def process_bounding(img, bounding_list):
            non_blanks = []
            for bounding in bounding_list:
                x, y, w, h = bounding
                node = img[y:y + h, x:x + w, :]
                if not np.count_nonzero(node) == 0 and not np.count_nonzero(255 - node) == 0:
                    non_blanks.append(bounding)

            enlarge_width = 5
            img_h, img_w, _ = img.shape
            enlarged_bounding = []
            for x, y, w, h in bounding_list:
                enlarged_x = max(0, x - enlarge_width)
                enlarged_y = max(0, y - enlarge_width)
                enlarged_w = min(w + 2 * enlarge_width, img_w - enlarged_x)
                enlarged_h = min(h + 2 * enlarge_width, img_h - enlarged_y)
                enlarged_bounding.append((enlarged_x, enlarged_y, enlarged_w, enlarged_h))
            return enlarged_bounding

        def flat_bounding(image, canny_sigma=0.33, dilate_count=4):
            """
            Find external bounding of widgets in a screenshot.

            :param image: Input image of type `ndarray`.
            :param canny_sigma: Sigma parameter for canny to control the thresholds.
            :param dilate_count: Number of iterations to perform dilation.
            :return: A list of widget bounding.
                Each bounding is represented as (x, y, w, h) where (x, y) stands for the position
                of the top-left vertex of the bounding, and (w, h) stands for the width and height of the bounding.
            """
            v = np.median(image)
            img_binary = cv2.Canny(image, int(max(0, (1 - canny_sigma) * v)), int(min(255, (1 + canny_sigma) * v)))
            img_dilated = cv2.dilate(img_binary, None, iterations=dilate_count)
            contours, _ = cv2.findContours(img_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            bounding = []
            for c in contours:
                bounding.append(cv2.boundingRect(c))
            return bounding

        def flat_bounding_v2(image_path):
            detector = WidgetDetector()
            _, _, elements = detector.detect(image_path)
            bounding = [(ele["position"]["column_min"], ele["position"]["row_min"],
                 ele["width"], ele["height"]) for ele in elements]
            return bounding

        def basic_row_generation(bounding):
            basic_rows= []
            for bounding in sorted(bounding, key=lambda b: b[1] + b[3] / 2):
                x, y, w, h = bounding
                center_y = y + h / 2
                found = False
                for row in basic_rows:
                    ceiling = row[1]
                    ground = row[2]
                    if ceiling <= center_y <= ground:
                        row[0].append(bounding)
                        row[1] = min(ceiling, y)
                        row[2] = max(ground, y + h)
                        found = True
                        break
                if not found:
                    basic_rows.append([[bounding], y, y + h])
            return basic_rows

        def group_generation(basic_rows, resolution):
            # Initial Group generation.
            groups = [[[row], row[1], row[2]] for row in basic_rows]
            surviving = [True] * len(groups)
            group_count = 0
            while not len(groups) == group_count:
                group_count = len(groups)
                for i, group_i in enumerate(groups):
                    for j, group_j in enumerate(groups):
                        if not i == j and surviving[j] and \
                                group_j[1] <= (group_i[1] + group_i[2]) / 2 <= group_j[2]:
                            group_j[0] += group_i[0]
                            group_j[1] = min(group_j[1], group_i[1])
                            group_j[2] = max(group_j[2], group_i[2])
                            surviving[i] = False
                            break
            groups = [group for i, group in enumerate(groups) if surviving[i]]

            # Group separation.
            for i, group_i in enumerate(groups):
                for group_j in groups[i + 1:]:
                    if group_j[1] < group_i[2] < group_j[2]:
                        group_i[2] = int((group_i[2] + group_j[1]) / 2)
                        group_j[1] = group_i[2]
                    elif group_j[1] < group_i[1] < group_j[2]:
                        group_i[1] = int((group_i[1] + group_j[2]) / 2)
                        group_j[2] = group_i[1]

            # Group simplification.
            if len(groups) > 0:
                groups[0][1] = 0  # The first group should be at the top.
                groups[-1][2] = resolution[1]  # The last group should be at the bottom.
            for prev, cur in zip(groups[:-1], groups[1:]):
                if prev[2] < cur[1]:
                    cur[1] = int((prev[2] + cur[1]) / 2)
                    prev[2] = cur[1]
            g_threshold = 1.5 * resolution[1] / 100
            surviving = [True] * len(groups)
            for i in range(len(groups)):
                if groups[i][2] - groups[i][1] < g_threshold:
                    if i - 1 < 0 and i + 1 < len(groups):
                        groups[i + 1][0] += groups[i][0]
                        groups[i + 1][1] = groups[i][1]
                    elif i + 1 >= len(groups) and i - 1 >= 0:
                        groups[i - 1][0] += groups[i][0]
                        groups[i - 1][2] = groups[i][2]
                    elif i - 1 >= 0 and i + 1 < len(groups):
                        height_a = groups[i - 1][2] - groups[i - 1][1]
                        height_b = groups[i + 1][2] - groups[i + 1][1]
                        if height_a < height_b:
                            groups[i - 1][0] += groups[i][0]
                            groups[i - 1][2] = groups[i][2]
                        else:
                            groups[i + 1][0] += groups[i][0]
                            groups[i + 1][1] = groups[i][1]
                    surviving[i] = False
            return [group for i, group in enumerate(groups) if surviving[i]]

        def merge_close_lines(lines, threshold=5):
            i = 0
            while i + 1 < len(lines):
                if lines[i + 1] - lines[i] < threshold:
                    lines[i] = int((lines[i] + lines[i + 1]) / 2)
                    lines.pop(i + 1)
                else:
                    i += 1

        def layout(bounding, resolution):
            """
                Data Structure Generation
            """
            # Group Generation
            groups = group_generation(basic_row_generation(bounding), resolution)

            # Row & Column Generation.
            line_merge_threshold = 1.5
            column_merge_threshold = 1.5

            for group in groups:
                group[0][0][1] = group[1]
                group[0][-1][2] = group[2]
                # lines = sorted(set([row[1] for row in group[0]] + [row[2] for row in group[0]]))
                nodes = [(y, h) for node_row in group[0] for _, y, _, h in node_row[0]]
                lines = sorted(set([y for y, _ in nodes] + [y + h for y, h in nodes] + [group[1], group[2]]))
                merge_close_lines(lines, line_merge_threshold * resolution[1] / 100)
                lines[0] = group[1]
                lines[-1] = group[2]

                rows = []
                for top, bottom in zip(lines[:-1], lines[1:]):
                    filtered_basic_rows = [row for row in group[0] if not (bottom <= row[1] or top >= row[2])]
                    filtered_nodes = [(x, w) for row in filtered_basic_rows
                                      for x, y, w, h in row[0] if not (y + h <= top or y >= bottom)]
                    cols = sorted(set([x for x, _ in filtered_nodes] + [x + w for x, w in filtered_nodes]))
                    if len(cols) > 0:
                        if not cols[0] == 0:
                            cols = [0] + cols
                        if not cols[-1] == resolution[0]:
                            cols.append(resolution[0])
                        merge_close_lines(cols, column_merge_threshold * resolution[0] / 100)
                        cols[0] = 0
                        cols[-1] = resolution[0]
                        cols = [[left, right] for left, right in zip(cols[:-1], cols[1:])]
                    rows.append([cols, top, bottom])
                group[0] = rows
            return groups

        screen_src = cv2.imread(screenshot_path_src)
        bounding_src = process_bounding(screen_src, flat_bounding(screen_src))
        resolution_src = (screen_src.shape[1], screen_src.shape[0])
        groups_src = layout(bounding_src, resolution_src)

        try:
            group_no, group = next((i, g) for i, g in enumerate(groups_src) if g[1] <= y < g[2])
            row_no, row = next((i, r) for i, r in enumerate(group[0]) if r[1] <= y < r[2])
            col_no = next(i for i, c in enumerate(row[0]) if c[0] <= x < c[1])
        except StopIteration:
            return None, None, None

        screen_dst = cv2.imread(screenshot_path_dst)
        bounding_dst = process_bounding(screen_dst, flat_bounding(screen_dst))
        resolution_dst = (screen_dst.shape[1], screen_dst.shape[0])
        groups_dst = layout(bounding_dst, resolution_dst)

        if group_no < len(groups_dst):
            group = groups_dst[group_no]
            if row_no < len(group[0]):
                row = group[0][row_no]
                if col_no < len(row[0]):
                    col = row[0][col_no]
                    point_x, point_y = (col[0] + col[1]) // 2, (row[1] + row[2]) // 2
                    return point_x, point_y, (col[0], row[1], col[1], row[2])
                else:
                    print(f"Column number out of range: {col_no}.")
            else:
                print(f"Row number out of range: {row_no}.")
        else:
            print(f"Group number out of range: {group_no}.")

        return None, None, None

    def check_match_validity(
            self,
            kernel: Tuple[int, int],
            match_result: Tuple[Optional[int], Optional[int]],
            screenshot_path_src: str,
            screenshot_path_dst: str,
            threshold: float = 0.15,
            mode: str = "square"
    ):
        if match_result[0] is None or match_result[1] is None:
            return False

        screen_src = cv2.imread(screenshot_path_src)
        screen_dst = cv2.imread(screenshot_path_dst)
        src_h, src_w, _ = screen_src.shape
        dst_h, dst_w, _ = screen_dst.shape
        x_ratio_k, y_ratio_k = kernel[0] / src_w, kernel[1] / src_h
        x_ratio_m, y_ratio_m = match_result[0] / dst_w, match_result[1] / dst_h
        if mode == "square":
            x_lower = max(x_ratio_k * (1 - threshold), 0.0)
            x_upper = min(x_ratio_k * (1 + threshold), 1.0)
            y_lower = max(y_ratio_k * (1 - threshold), 0.0)
            y_upper = min(y_ratio_k * (1 + threshold), 1.0)
        elif mode == "rectangle":
            x_lower = max(x_ratio_k * (1 - 3 * threshold), 0.0)
            x_upper = min(x_ratio_k * (1 + 3 * threshold), 1.0)
            y_lower = max(y_ratio_k * (1 - threshold), 0.0)
            y_upper = min(y_ratio_k * (1 + threshold), 1.0)
        else:
            raise ValueError(f"Unknown mode: {mode}.")
        print(f"x-range: ({x_lower}, {x_upper}) <= {x_ratio_m}")
        print(f"y-range: ({y_lower}, {y_upper}) <= {y_ratio_m}")
        return x_lower < x_ratio_m < x_upper and y_lower < y_ratio_m < y_upper

    def draw_bounding_boxes(self, screenshot_path: str, bboxes: Dict[str, Tuple], candidate_idx: Optional[List] = None):
        bboxes_reserved = {}
        if candidate_idx is not None:
            for idx in candidate_idx:
                bboxes_reserved[str(idx)] = bboxes[idx]
        else:
            bboxes_reserved = bboxes
        screen = cv2.imread(screenshot_path)
        for k, v in bboxes_reserved.items():
            x1, y1, x2, y2 = v
            cv2.rectangle(screen, (x1, y1), (x2, y2), (0, 255, 0), 3)
            x0, y0 = max(x1 - 10, 0), min(y1 + 10, screen.shape[0])
            if int(k) >= 10:
                x0 = max(x1 - 20, 0)
            cv2.putText(screen, f"{k}", (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 5)
            cv2.putText(screen, f"{k}", (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        file_path = str(self.temp_path / "draw" / f"draw-{gen_timestamp()}.jpeg")
        cv2.imwrite(file_path, screen)
        return file_path


if __name__ == "__main__":
    assert_screen = "/home/lyc/Projects/GUIScirptAug/backend/data/temp.jpeg"
    assert_text = "The text message “Results for 500” appears in the interface."
    service = ImageServiceImpl()
    res, rationale = service.do_semantic_assertion(assert_screen, assert_text)
    print("=========================================================================")
    print(f"assertion result: {res}")
    print(f"reason: {rationale}")