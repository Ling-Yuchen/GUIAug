import json
import time
from typing import Any, Dict, List, Optional


def gen_timestamp() -> str:
    """Generate timestamp"""
    timestamp = int(time.time())
    return str(timestamp)


def remove_punctuation(s: str, more_punc: Optional[List[str]] = None) -> str:
    """Remove punctuation marks from string"""
    punctuation = [',', '.', ':', ';', '_']
    if more_punc is not None:
        punctuation.extend(more_punc)
    for char in punctuation:
        s = s.replace(char, ' ')
    return s.strip()
