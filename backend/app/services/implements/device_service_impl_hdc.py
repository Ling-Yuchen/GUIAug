import json
import re
import copy
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from jpype import JBoolean

from app.models.device import Device
from app.services.device_service import DeviceService
from app.utils.main import gen_timestamp, timeit
from app.utils.java_conn import HosRemoteDevice


class HarmonyDeviceServiceImpl(DeviceService):

    screenshot_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "screenshots"
    ui_json_path: Path = Path(__file__).parent.parent.parent.parent.resolve() / "data" / "ui_json"
    device_pool: Dict[str, Device] = {}

    @timeit
    def get_device_list(self) -> List[Device]:
        cmd = "hdc list targets"
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        serial_no_list = [line.strip() for line in output.stdout.strip().splitlines()]
        dev_list = []
        for serial_no in serial_no_list:
            if serial_no not in self.device_pool.keys():
                hos_dev = HosRemoteDevice(serial_no)
                screen_size = hos_dev.getScreenSize(JBoolean(True))
                width = screen_size.width
                height = screen_size.height
                dev = Device(
                    platform="harmony",
                    serial_no=serial_no,
                    height=height,
                    width=width,
                    java_instance=hos_dev,
                )
                self.device_pool[serial_no] = dev
            r_dev = copy.copy(self.device_pool[serial_no])
            r_dev.java_instance = None
            dev_list.append(r_dev)
        return dev_list

    def install_app(self, serial_no: str, file_path: str) -> None:
        cmd = f"hdc -t {serial_no} app install {file_path}"
        subprocess.run(cmd, shell=True)

    def uninstall_app(self, serial_no: str, package: str) -> None:
        cmd = f"hdc -t {serial_no} app uninstall {package}"
        subprocess.run(cmd, shell=True)

    def launch_app(self, serial_no: str, package: str, main_activity: str) -> None:
        cmd = f"hdc -t {serial_no} shell aa start -a {main_activity} -b {package}"
        subprocess.run(cmd, shell=True)

    def stop_app(self, serial_no: str, package: str) -> None:
        cmd = f"hdc -t {serial_no} shell aa force-stop {package}"
        subprocess.run(cmd, shell=True)

    @timeit
    def perform_click(self, serial_no: str, x: int, y: int):
        cmd = f"hdc -t {serial_no} shell uitest uiInput click {x} {y}"
        if serial_no in self.device_pool.keys():
            dev_java = self.device_pool[serial_no].java_instance
            if dev_java is not None:
                dev_java.onTouchDown(x, y)
                time.sleep(.2)
                dev_java.onTouchUp(x, y)
                return cmd
        subprocess.run(cmd, shell=True)
        return cmd

    @timeit
    def perform_input(self, serial_no: str, text: str, x: int, y: int):
        cmd = f"hdc shell uitest uiInput inputText {x} {y} \"{text}\""
        subprocess.run(cmd, shell=True)
        # re_cmd = cmd + '; '
        time.sleep(1)
        # cmd = f"hdc -t {serial_no} shell uitest uiInput click 1450 1780"
        # re_cmd = re_cmd + cmd
        # subprocess.run(cmd, shell=True)
        return cmd
        # time.sleep(.1)
        # subprocess.run(cmd, shell=True)

    @timeit
    def perform_enter(self, serial_no: str):
        cmd = f"hdc shell uitest uiInput keyEvent 2054"
        subprocess.run(cmd, shell=True)
        time.sleep(1)
        return cmd
        # time.sleep(.1)
        # subprocess.run(cmd, shell=True)

    @timeit
    def perform_long_press(self, serial_no: str, x: int, y: int):
        cmd = f"hdc -t {serial_no} shell uitest uiInput longClick {x} {y}"
        if serial_no in self.device_pool.keys():
            dev_java = self.device_pool[serial_no].java_instance
            if dev_java is not None:
                dev_java.onTouchDown(x, y)
                time.sleep(.7)
                dev_java.onTouchUp(x, y)
                return cmd
        subprocess.run(cmd, shell=True)
        return cmd

    @timeit
    def perform_scroll(self, serial_no: str, x_from: int, y_from: int, x_to: int, y_to: int, v: int):
        cmd = f"hdc -t {serial_no} shell uitest uiInput swipe {x_from} {y_from} {x_to} {y_to} {v}"
        print(f'debug-swipe cmd: {cmd}')
        subprocess.run(cmd, shell=True)
        return cmd

    def perform_back(self, serial_no: str) -> None:
        cmd = f"hdc -t {serial_no} shell uitest uiInput keyEvent 2"
        subprocess.run(cmd, shell=True)

    @timeit
    def get_screenshot(self, serial_no: str) -> str:
        screenshot_src = "/data/local/tmp/screenshot.jpeg"
        screenshot_dest = self.screenshot_path / f"screenshot-{gen_timestamp()}.jpeg"
        cmd1 = f"hdc -t {serial_no} shell snapshot_display -f {screenshot_src}"
        cmd2 = f"hdc -t {serial_no} file recv {screenshot_src} {screenshot_dest}"
        subprocess.run(cmd1, shell=True)
        subprocess.run(cmd2, shell=True)
        return str(screenshot_dest)

    @timeit
    def get_ui_structure(self, serial_no: str, save: bool = True) -> str:
        ui_json_file_dest = self.ui_json_path / f"ui-dump-{gen_timestamp()}.json"
        if serial_no in self.device_pool.keys():
            dev_java = self.device_pool[serial_no].java_instance
            if dev_java is not None:
                layout = dev_java.getLayout()
                if layout is not None:
                    if save:
                        layout_dict = json.loads(str(layout))
                        with open(str(ui_json_file_dest), mode="w", encoding="utf-8") as f:
                            f.write(json.dumps(layout_dict))
                        return str(ui_json_file_dest)
                    else:
                        return layout
        else:
            ui_json_file_src = "/data/local/tmp/layout.json"
            ui_json_file_dest = self.ui_json_path / f"ui-dump-{gen_timestamp()}.json"
            cmd1 = f"hdc -t {serial_no} shell uitest dumpLayout -p {ui_json_file_src}"
            cmd2 = f"hdc -t {serial_no} file recv {ui_json_file_src} {ui_json_file_dest}"
            subprocess.run(cmd1, shell=True)
            subprocess.run(cmd2, shell=True)
            return str(ui_json_file_dest)

    @timeit
    def get_current_app_message(self, serial_no: str) -> Tuple[str, str]:
        cmd = f"hdc -t {serial_no} shell aa dump -l"
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pattern = (
            r"AbilityRecord ID #\d+[\s\S]*?app name \[(.*?)\][\s\S]*?main name"
            r" \[(.*?)\][\s\S]*?state #FOREGROUND[\s\S]*?app state #FOREGROUND"
        )
        matches = re.findall(pattern, output.stdout)
        if len(matches) > 0:
            app_name, main_name = matches[0][0], matches[0][1]
            return app_name, main_name
        return "home", "home"

    @timeit
    def get_device_hw(self, serial_no: str) -> Tuple[Optional[int], Optional[int]]:
        if serial_no in self.device_pool.keys():
            height = self.device_pool[serial_no].height
            width = self.device_pool[serial_no].width
            return height, width

        hos_dev = HosRemoteDevice(serial_no)
        screen_size = hos_dev.getScreenSize(JBoolean(True))
        width = screen_size.width
        height = screen_size.height
        return height, width

    @timeit
    def get_device(self, serial_no: str):
        if serial_no not in self.device_pool.keys():
            hos_dev = HosRemoteDevice(serial_no)
            screen_size = hos_dev.getScreenSize(JBoolean(True))
            width = screen_size.width
            height = screen_size.height
            dev = Device(
                platform="harmony",
                serial_no=serial_no,
                height=height,
                width=width,
                java_instance=hos_dev,
            )
            self.device_pool[serial_no] = dev
        return self.device_pool.get(serial_no)
