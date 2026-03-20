from typing import Any, Optional

from pydantic import BaseModel


class Device(BaseModel):
    platform: Optional[str] = None
    serial_no: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    busy: bool = False
    java_instance: Optional[Any] = None
