import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

from app.models.device import Device
from app.services.device_service import DeviceService
from app.utils.main import gen_timestamp


class ADBDeviceServiceImpl(DeviceService):

    screenshot_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "screenshots"
    ui_xml_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "ui_xml"
    device_pool: Dict[str, Device] = {}

    def get_ui_structure(self, serial_no: str, save: bool = True) -> str:
        if save:
            ui_xml_file_src = "/sdcard/ui-dump.xml"
            ui_xml_file_dest = self.ui_xml_path / f"ui-dump-{gen_timestamp()}.xml"
            cmd1 = f"adb -s {serial_no} shell /system/bin/uiautomator dump --compressed {ui_xml_file_src}"
            cmd2 = f"adb pull {ui_xml_file_src} {ui_xml_file_dest}"
            subprocess.run(cmd1, shell=True)
            subprocess.run(cmd2, shell=True)
            return str(ui_xml_file_dest)
        else:
            cmd = f"adb -s {serial_no} exec-out /system/bin/uiautomator dump --compressed /dev/tty"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
            match = re.search(r"<\s*hierarchy\b.*?</\s*hierarchy\s*>", raw, flags=re.S | re.I)
            xml_str = match.group(0).strip() if match else ""
            return xml_str

    def uninstall_app(self, serial_no: str, package: str) -> None:
        cmd = f"adb -s {serial_no} uninstall {package}"
        subprocess.run(cmd, shell=True)

    def install_app(self, serial_no: str, file_path: str) -> None:
        cmd = f"adb -s {serial_no} install {file_path}"
        subprocess.run(cmd, shell=True)

    def launch_app(self, serial_no: str, package: str, main_activity: str) -> None:
        cmd = f"adb -s {serial_no} shell am start {package}/{main_activity}"
        subprocess.run(cmd, shell=True)

    def stop_app(self, serial_no: str, package: str) -> None:
        cmd = f"adb -s {serial_no} shell am force-stop {package}"
        subprocess.run(cmd, shell=True)

    def perform_click(self, serial_no: str, x: int, y: int):
        cmd = f"adb -s {serial_no} shell input tap {x} {y}"
        subprocess.run(cmd, shell=True)
        return cmd

    def perform_input(self, serial_no: str, text: str, x: int, y: int):
        cmd = ""
        if len(text) > 0:
            # self.perform_click(serial_no, x, y)

            cmd1 = f"adb -s {serial_no} shell ime set com.android.adbkeyboard/.AdbIME"
            subprocess.run(cmd1, shell=True)
            time.sleep(1)

            # text = text.replace(" ", "%s")
            # text = text.replace('"', "'")
            # for char in ["'", "?", "&", "#", "<", ">"]:
            #     text = text.replace(f"{char}", f"\\{char}")
            # cmd = f"adb -s {serial_no} shell input text \"{text}\""
            text = text.replace('"', "'")
            for char in ["'", "?", "&", "#", "<", ">", " ", "|", "\\", ";", "`", "*", "(", ")", "~"]:
                if char in text:
                    text = text.replace(char, f"\\{char}")
            cmd = f"adb -s {serial_no} shell am broadcast -a ADB_INPUT_TEXT --es msg \"{text}\""
            subprocess.run(cmd, shell=True)
            time.sleep(1)

            cmd2 = f"adb -s {serial_no} shell ime set io.appium.settings/.UnicodeIME"
            subprocess.run(cmd2, shell=True)
            time.sleep(.5)
        return cmd

    def perform_long_press(self, serial_no: str, x: int, y: int):
        cmd = f"adb -s {serial_no} shell input swipe {x} {y} {x} {y} 2000"
        subprocess.run(cmd, shell=True)
        return cmd

    def perform_scroll(self, serial_no: str, x_from: int, y_from: int, x_to: int, y_to: int, v: int):
        cmd = f"adb -s {serial_no} shell input swipe {x_from} {y_from} {x_to} {y_to} {int(v)}"
        print(cmd)
        subprocess.run(cmd, shell=True)
        return cmd

    def perform_back(self, serial_no: str):
        cmd = f"adb -s {serial_no} shell input keyevent 4"
        subprocess.run(cmd, shell=True)
        return cmd

    def get_screenshot(self, serial_no: str):
        # screenshot_src = "/sdcard/screenshot.png"
        # screenshot_dest = self.screenshot_path / f"screenshot-{gen_timestamp()}.png"
        # cmd1 = f"adb -s {serial_no} shell screencap -p {screenshot_src}"
        # cmd2 = f"adb pull {screenshot_src} {screenshot_dest}"
        # subprocess.run(cmd1, shell=True)
        # subprocess.run(cmd2, shell=True)
        # return str(screenshot_dest)
        h, w = self.get_device_hw(serial_no)
        screenshot_dest = self.screenshot_path / f"screenshot-{gen_timestamp()}.jpeg"
        cmd = (
            f"adb -s {serial_no} shell"
            " LD_LIBRARY_PATH=/data/local/tmp"
            " /data/local/tmp/minicap"
            f" -P {w}x{h}@{w}x{h}/0 -s"
            f" > {screenshot_dest}"
        )
        subprocess.run(cmd, shell=True)
        return str(screenshot_dest)

    def get_device_list(self) -> List[Device]:
        output = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
        serial_no_list = [line.split("\t")[0] for line in output.stdout.strip().split("\n")[1:]]
        dev_list = []
        for serial_no in serial_no_list:
            if serial_no not in self.device_pool.keys():
                height, width = self.get_device_hw(serial_no)
                dev = Device(
                    platform="android",
                    serial_no=serial_no,
                    height=height,
                    width=width,
                )
                self.device_pool[serial_no] = dev
            dev_list.append(self.device_pool[serial_no])
        return dev_list

    def get_current_app_message(self, serial_no: str) -> Tuple[str, str]:
        """Show current app message."""
        system_name = platform.system().lower()
        filter_cmd = "findstr" if system_name == "windows" else "grep"
        cmd = f"adb -s {serial_no} shell dumpsys window windows | {filter_cmd} mFocusedApp"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
        result = result[result.find("u0") + 2:].strip().split(" ")[0]
        package, activity = result.split("/", maxsplit=1)
        return package, activity

    def get_device_hw(self, serial_no: str) -> Tuple[int, int]:
        if serial_no in self.device_pool.keys():
            height = self.device_pool[serial_no].height
            width = self.device_pool[serial_no].width
            return height, width

        cmd = f"adb -s {serial_no} shell wm size"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
        result = result.lower()
        idx = result.find("override size:")
        if idx != -1:
            result = result[idx + len("override size:"):].strip()
            result = result.split("\n")[0]
        else:
            idx = result.find("physical size:")
            result = result[idx + len("physical size:"):].strip()
            result = result.split("\n")[0]
        width, height = result.split("x")
        return int(height), int(width)

    def get_device(self, serial_no: str):
        return self.device_pool.get(serial_no)
