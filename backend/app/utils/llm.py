import json
import base64
from typing import Dict, Optional, Tuple, Any, List, Union

from openai import OpenAI


api_price = {
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006},
    "gpt-4o": {"input": 0.0000025, "output": 0.00001},
    "qwen-turbo": {"input": 0.000000042, "output": 0.000000084},
    "qwen-vl-plus": {"input": 0.00000021, "output": 0.00000063},
    "qwen-vl-max": {"input": 0.00000042, "output": 0.00000126},
    "qwen-plus": {"input": 0.000000112, "output": 0.00000112},
    "gpt-4.1": {"input": 0.000002, "output": 0.000008},
}

gpt_client = OpenAI(
    base_url="",
    api_key=""
)

custom_client = OpenAI(
    base_url="",
    api_key="",
)

qwen_client = OpenAI(
    base_url="",
    api_key=""
)


def query(
        user_msg_txt: str,
        user_msg_img: Optional[Union[str, List[str]]] = None,
        system_msg: Optional[str] = None,
        model: str = "gpt-4.1",
        temperature: float = 0.5,
) -> Tuple[Dict[str, Any], int, int, float, float]:
    client = qwen_client if model.startswith("q") else gpt_client
    messages = [{"role": "system", "content": system_msg}] if system_msg else []
    if user_msg_img is None:
        user_content = user_msg_txt
    else:
        user_content = [{"type": "text", "text": user_msg_txt}]
        if isinstance(user_msg_img, str):
            user_msg_img = encode_image(user_msg_img)
            user_msg_img = f"data:image/jpeg;base64,{user_msg_img}"
            user_content.append({"type": "image_url", "image_url": {"url": user_msg_img}})
        else:
            for img in user_msg_img:
                img = encode_image(img)
                img = f"data:image/jpeg;base64,{img}"
                user_content.append({"type": "image_url", "image_url": {"url": img}})

    messages.append({"role": "user", "content": user_content})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"}
    )
    response_content = response.choices[0].message.content
    response_dict = json.loads(response_content)
    output_usage = response.usage.completion_tokens
    output_cost = output_usage * api_price[model]["output"]
    input_usage = response.usage.prompt_tokens
    input_cost = input_usage * api_price[model]["input"]
    return response_dict, input_usage, output_usage, input_cost, output_cost


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def query_v2(
        user_msg_txt: str,
        user_msg_img: Optional[Union[str, List[str]]] = None,
        system_msg: Optional[str] = None,
        model: str = "gpt-4o",
        temperature: float = 0.0,
) -> Tuple[Dict[str, Any], int, int, float, float]:
    messages = [{"role": "system", "content": system_msg}] if system_msg else []
    if user_msg_img is None:
        user_content = user_msg_txt
    else:
        user_content = [{"type": "text", "text": user_msg_txt}]
        if isinstance(user_msg_img, str):
            user_msg_img = encode_image(user_msg_img)
            user_msg_img = f"data:image/jpeg;base64,{user_msg_img}"
            user_content.append({"type": "image_url", "image_url": {"url": user_msg_img}})
        else:
            for img in user_msg_img:
                img = encode_image(img)
                img = f"data:image/jpeg;base64,{img}"
                user_content.append({"type": "image_url", "image_url": {"url": img}})

    messages.append({"role": "user", "content": user_content})
    response = custom_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    response_content = response.choices[0].message.content
    response_dict = extract_json_from_string(response_content)
    output_usage = response.usage.completion_tokens
    # output_cost = output_usage * api_price[model]["output"]
    output_cost = 0
    input_usage = response.usage.prompt_tokens
    # input_cost = input_usage * api_price[model]["input"]
    input_cost = 0
    return response_dict, input_usage, output_usage, input_cost, output_cost


def extract_json_from_string(s: str) -> Dict[str, Any]:
    brace_stack = []
    start = end = None
    for i, char in enumerate(s):
        if char == "{":
            if not brace_stack:
                start = i
            brace_stack.append("{")
        elif char == "}":
            if brace_stack:
                brace_stack.pop()
                if not brace_stack:
                    end = i + 1
                    break
    if start is not None and end is not None:
        json_str = s[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON object in response: {e}")
    else:
        raise ValueError("No JSON object found in response")
