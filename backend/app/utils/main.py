import asyncio
import functools
import json
import math
import struct
import time
import re
from typing import List, Optional, Tuple
from pathlib import Path
import cv2
from PIL import Image
import os



def timeit(func):
    if asyncio.iscoroutinefunction(func):  # 判断是否为 async 函数
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)  # 执行 async 函数
            end_time = time.time()
            print(f"##TIME-LOG##: Async function '{func.__name__}' executed in {end_time - start_time:.4f} seconds")
            return result
        return async_wrapper
    else:  # 普通函数
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)  # 执行普通函数
            end_time = time.time()
            print(f"##TIME-LOG##: Function '{func.__name__}' executed in {end_time - start_time:.4f} seconds")
            return result
        return sync_wrapper


def cal_overlap_rate(p1: Tuple[int, int], p2: Tuple[int, int], bounds: Tuple[int, int, int, int]):
    """
    计算线段 (p1, p2) 在矩形边界框 bounds 内的覆盖比例。
    
    :param p1: 线段起点 (x1, y1)
    :param p2: 线段终点 (x2, y2)
    :param bounds: 矩形边界框 (x_up_left, y_up_left, x_down_right, y_down_right)
    :return: 覆盖比例 (0 <= overlap_rate <= 1)
    """
    x_up_left, y_up_left, x_down_right, y_down_right = bounds

    # 计算两点间的欧几里得距离
    def calculate_length(x1, y1, x2, y2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # 检查线段和矩形边界是否有交点
    def line_intersection(p1, p2, q1, q2):
        """计算两线段 (p1, p2) 和 (q1, q2) 的交点"""
        def det(a, b, c, d):
            return a * d - b * c

        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = q1
        x4, y4 = q2

        denom = det(x1 - x2, y1 - y2, x3 - x4, y3 - y4)
        if denom == 0:  # 平行或重叠
            return None

        px = det(det(x1, y1, x2, y2), x1 - x2, det(x3, y3, x4, y4), x3 - x4) / denom
        py = det(det(x1, y1, x2, y2), y1 - y2, det(x3, y3, x4, y4), y3 - y4) / denom

        # 检查交点是否在线段范围内
        if (min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2) and
            min(x3, x4) <= px <= max(x3, x4) and min(y3, y4) <= py <= max(y3, y4)):
            return (px, py)
        return None

    # 边界框的四条边
    edges = [
        ((x_up_left, y_up_left), (x_down_right, y_up_left)),  # 上边
        ((x_down_right, y_up_left), (x_down_right, y_down_right)),  # 右边
        ((x_down_right, y_down_right), (x_up_left, y_down_right)),  # 下边
        ((x_up_left, y_down_right), (x_up_left, y_up_left))  # 左边
    ]

    # 找出线段和矩形边界的所有交点
    intersections = []
    for edge in edges:
        intersection = line_intersection(p1, p2, edge[0], edge[1])
        if intersection:
            intersections.append(intersection)

    # 加入起点和终点
    valid_points = [p1, p2]
    valid_points.extend(intersections)

    # 按线段的顺序对点排序
    valid_points = sorted(valid_points, key=lambda p: calculate_length(p1[0], p1[1], p[0], p[1]))

    # 计算有效部分长度
    total_length = calculate_length(p1[0], p1[1], p2[0], p2[1])
    valid_length = 0
    for i in range(len(valid_points) - 1):
        mid_x = (valid_points[i][0] + valid_points[i + 1][0]) / 2
        mid_y = (valid_points[i][1] + valid_points[i + 1][1]) / 2
        if x_up_left <= mid_x <= x_down_right and y_up_left <= mid_y <= y_down_right:
            valid_length += calculate_length(valid_points[i][0], valid_points[i][1], valid_points[i + 1][0], valid_points[i + 1][1])

    # 计算比例
    overlap_rate = valid_length / total_length if total_length > 0 else 0
    return overlap_rate


def cal_iou(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    inter_area = inter_width * inter_height
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = area1 + area2 - inter_area
    if union_area == 0:
        return 0.0

    iou = inter_area / union_area
    return iou


def get_img_shape(img_path: str):
    img = Image.open(img_path)
    w, h = img.size
    return w, h


def gen_step_id(id_prev: Optional[str], id_next: Optional[str]):
    if id_prev is None and id_next is not None:
        return str(int(id_next) - 100)
    if id_prev is not None and id_next is not None:
        return str((int(id_prev) + int(id_next)) // 2)
    return str(int(time.time() * 1000))


def gen_timestamp() -> str:
    """Generate timestamp"""
    timestamp = int(time.time())
    return str(timestamp)


def get_desc_from_xpath(xpath: str, keys: List[str]) -> str:
    try:
        desc = ""
        elements = xpath.strip("//*[").strip("]").split(" and ")
        for element in elements:
            element = element.strip("@")
            tag, value = element.split("=")
            if tag in keys:
                desc += f"{tag}:\"{value}\","
        return desc.strip(",")
    except:
        return ""


async def read_frame_data(reader):
    # 读取帧头部信息，前4个字节表示帧的大小
    frame_size_data = await reader.read(4)
    if len(frame_size_data) < 4:
        return None

    # 解析帧大小（前4字节是 frame size, 使用 struct.unpack 解析为整数）
    frame_size = struct.unpack('<I', frame_size_data)[0]

    # 读取 frame_size 大小的数据，即图像数据
    frame_data = b''
    while len(frame_data) < frame_size:
        packet = await reader.read(frame_size - len(frame_data))
        if not packet:
            break
        frame_data += packet

    return frame_data


def draw_rect(img_path, pt1, pt2):
    img = cv2.imread(img_path)
    cv2.rectangle(img, pt1, pt2, (0, 255, 0), 2)
    cv2.imshow("rect", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def remove_punctuation(s: str, more_punc: Optional[List[str]] = None) -> str:
    """Remove punctuation marks from string"""
    punctuation = [',', '.', ':', ';', '_']
    if more_punc is not None:
        punctuation.extend(more_punc)
    for char in punctuation:
        s = s.replace(char, ' ')
    return s.strip()

def load_target_json(target_path: Path):
    with open(target_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def parse_replay_decision(migration_decision: str):
    clean_result = migration_decision.strip("```json").strip("```").strip()
    json_content = json.loads(clean_result)

    widget_flag = str(json_content["widget"])
    target = str(json_content["target"])
    widget_id = None
    x = y = None
    if widget_flag == 'true':
        widget_id = target
    else:
        x, y = extract_coordinates(target)
    action_type = str(json_content["action_type"])
    value = None
    if action_type is not 'click':
        value = str(json_content["value"])
    abstract = str(json_content["abstract"])

    return widget_flag, widget_id, x, y, action_type, value, abstract


def extract_coordinates(coord_str):
    numbers = re.findall(r'-?\d+', coord_str)
    if len(numbers) >= 2:
        x, y = numbers[0], numbers[1]
        return int(x), int(y)
    else:
        return None, None

def delete_latest_screenshot(path: str):
    try:
        os.remove(path)
    except FileNotFoundError:
        print("The file does not exist. ")
    except PermissionError:
        print("Error in permission. ")

def parse_state_assess(state_check: str):
    clean_result = state_check.strip("```json").strip("```").strip()
    json_content = json.loads(clean_result)

    GUI_state_flag = str(json_content["Answer1"])
    prediction = str(json_content["Answer2"])
    termination_flag = str(json_content["Answer3"])

    return GUI_state_flag, prediction, termination_flag


def parse_widget_sort(sort_result: str):
    clean_result = sort_result.strip("```json").strip("```").strip()
    json_content = json.loads(clean_result)
    list = json_content["widgets"]
    re_list = []
    for item in list:
        re_list.append({
            "id": item["id"],
            "explanation": item["explanation"]
        })

    return re_list


def scroll_direction(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    distance = (dx ** 2 + dy ** 2) ** 0.5
    if abs(dx) > abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"
    return direction, distance



