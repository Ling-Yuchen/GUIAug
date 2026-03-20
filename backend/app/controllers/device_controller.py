import asyncio
import subprocess
import json
import time
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
# from jpype import JBoolean

from app.models.device import Device
from app.services.device_service import DeviceService
from app.services.dependence import get_device_service
from app.utils.main import read_frame_data
# from app.utils.java_conn import PyScreenCapCallback, capture_error_event


class DeviceController:

    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/device/list", self.get_device_list, methods=["GET"], response_model=List[Device])
        self.router.add_api_route("/device/tap/{serial_no}/{x}/{y}", self.tap_on_device, methods=["GET"])
        self.router.add_api_route("/device/tap_input/{serial_no}/{x}/{y}/{text}", self.tap_input_to_device, methods=["GET"])
        self.router.add_api_route("/device/scroll/{serial_no}/{x1}/{y1}/{x2}/{y2}", self.scroll_screen, methods=["GET"])
        self.router.add_api_route("/device/long_press/{serial_no}/{x}/{y}", self.long_press_on_device, methods=["GET"])
        self.router.add_websocket_route("/ws", self.build_screen_websocket_android)
        # self.router.add_websocket_route("/ws2", self.build_screen_websocket_harmony)

    # async def build_screen_websocket_harmony(self, websocket: WebSocket):
    #     device_service = get_device_service()
    #     await websocket.accept()
    #     data = await websocket.receive_text()
    #     print(f"Received code: {data}")
    #     serial_no = data.strip("device://").strip()
    #
    #     screen_cap_callback = PyScreenCapCallback()
    #     screen_cap_callback.set_websocket(websocket)
    #     device = device_service.get_device(serial_no)
    #     hos_device = device.java_instance
    #     hos_device.stopCaptureScreen()
    #     hos_device.startCaptureScreen(screen_cap_callback, JBoolean(False))
    #     try:
    #         while not capture_error_event.is_set():
    #             dev_ctrl = await websocket.receive_text()
    #             dev_ctrl = json.loads(dev_ctrl)
    #             ctrl_event, x, y = dev_ctrl["event"], dev_ctrl["x"], dev_ctrl["y"]
    #             if ctrl_event == "down":
    #                 hos_device.onTouchDown(x, y)
    #             elif ctrl_event == "up":
    #                 hos_device.onTouchUp(x, y)
    #             else:
    #                 hos_device.onTouchMove(x, y)
    #     except WebSocketDisconnect:
    #         print("Websocket closed")
    #     except Exception as e:
    #         print(f"Error: {e}")
    #     finally:
    #         print("stop screen stream capture")
    #         hos_device.stopCaptureScreen()
    #         try:
    #             await websocket.close()
    #         except RuntimeError as e:
    #             if 'Cannot call "send" once a close message has been sent.' in str(e):
    #                 pass

    async def connect_device(self, serial_no: str, device_service: DeviceService = Depends(get_device_service)):
        # height, width = device_service.get_device_hw(serial_no)
        width, height, v_width, v_height, rotate = 1080, 1920, 360, 640, 0
        # v_height, v_width, rotate = height // 3, width // 3, 0
        cmd = "adb shell ps | grep minicap"
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if len(output.stdout.strip()) == 0:
            cmd = (
                f"adb -s {serial_no} shell"
                f" LD_LIBRARY_PATH=/data/local/tmp"
                f" /data/local/tmp/minicap"
                f" -P {width}x{height}@{v_width}x{v_height}/{rotate} &"
            )
            subprocess.run(cmd, shell=True)
            time.sleep(3)
        subprocess.run("adb forward tcp:1717 localabstract:minicap", shell=True)

    async def build_screen_websocket_android(self, websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_text()
        print(f"Received code: {data}")
        serial_no = data.strip("device://").strip()

        await self.connect_device(serial_no)
        reader, _ = await asyncio.open_connection("localhost", 1717)
        banner = await reader.read(24)  # skip banner
        try:
            while True:
                frame = await read_frame_data(reader)
                if not frame:
                    print("no frame")
                    break
                await websocket.send_bytes(frame)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            try:
                await websocket.close()
            except RuntimeError as e:
                if 'Cannot call "send" once a close message has been sent.' in str(e):
                    pass

    async def get_device_list(self, device_service: DeviceService = Depends(get_device_service)):
        devices = device_service.get_device_list()
        print(devices)
        return devices

    async def tap_on_device(self, serial_no: str, x: int, y: int, device_service: DeviceService = Depends(get_device_service)):
        device_service.perform_click(serial_no, x, y)
        time.sleep(.1)

    async def scroll_screen(self, serial_no: str, x1: int, y1: int, x2: int, y2: int, device_service: DeviceService = Depends(get_device_service)):
        device_service.perform_scroll(serial_no, x1, y1, x2, y2, v=1500)
        time.sleep(.1)

    async def long_press_on_device(self, serial_no: str, x: int, y: int, device_service: DeviceService = Depends(get_device_service)):
        device_service.perform_long_press(serial_no, x, y)
        time.sleep(.1)

    async def tap_input_to_device(self, serial_no: str, x: int, y: int, text: str, device_service: DeviceService = Depends(get_device_service)):
        device_service.perform_input(serial_no, text, x, y)
        time.sleep(.1)

device_controller = DeviceController()
