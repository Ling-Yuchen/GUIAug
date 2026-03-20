from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

from app.models.device import Device


class DeviceService(ABC):

    @abstractmethod
    def get_device_list(self) -> List[Device]:
        """get serial numbers of all the available devices"""
        ...

    @abstractmethod
    def install_app(self, serial_no: str, file_path: str) -> None:
        ...

    @abstractmethod
    def uninstall_app(self, serial_no: str, package: str) -> None:
        ...

    @abstractmethod
    def launch_app(self, serial_no: str, package: str, main_activity: str) -> None:
        ...

    @abstractmethod
    def stop_app(self, serial_no: str, package: str) -> None:
        ...

    @abstractmethod
    def perform_click(self, serial_no: str, x: int, y: int):
        ...

    @abstractmethod
    def perform_input(self, serial_no: str, text: str, x: int, y: int):
        ...

    @abstractmethod
    def perform_long_press(self, serial_no: str, x: int, y: int):
        ...

    @abstractmethod
    def perform_scroll(self, serial_no: str, x_from: int, y_from: int, x_to: int, y_to: int, v: int):
        ...

    @abstractmethod
    def perform_back(self, serial_no: str) -> None:
        ...

    @abstractmethod
    def get_screenshot(self, serial_no: str) -> str:
        ...

    @abstractmethod
    def get_ui_structure(self, serial_no: str, save: bool = True) -> str:
        ...

    @abstractmethod
    def get_current_app_message(self, serial_no: str) -> Tuple[str, str]:
        ...

    @abstractmethod
    def get_device_hw(self, serial_no: str) -> Tuple[Optional[int], Optional[int]]:
        ...

    @abstractmethod
    def get_device(self, serial_no: str):
        ...