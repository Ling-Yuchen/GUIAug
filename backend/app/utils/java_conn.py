import asyncio
from pathlib import Path

import jpype
import jpype.imports
from jpype import *
from fastapi import WebSocket
from jpype import JImplements, JOverride


def start_jvm(classpath: str):
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[classpath])


def shutdown_jvm():
    if jpype.isJVMStarted():
        jpype.shutdownJVM()


jar_file_path = Path(__file__).parent.parent.resolve() / "hosscrcpy-1.0.4-beta.jar"
start_jvm(str(jar_file_path))

HosRemoteDevice = JClass("com.huawei.hosscrcpy.api.HosRemoteDevice")
ScreenCapCallback = JClass("com.huawei.hosscrcpy.api.ScreenCapCallback")

capture_error_event = asyncio.Event()

@JImplements(ScreenCapCallback)
class PyScreenCapCallback:

    def __init__(self):
        self.count = 0
        self.websocket = None
        self.loop = asyncio.get_event_loop()

    def set_websocket(self, websocket: WebSocket):
        self.websocket = websocket

    @JOverride
    def onData(self, byteBuffer):
        if not self.loop.is_running():
            self.loop.run_forever()
        self.count += 1
        # print(f"triggered: {self.count}")
        screen_bytes = bytes(byteBuffer.array())
        self.loop.create_task(self.send_data(screen_bytes))

    async def send_data(self, screen_bytes):
        if self.websocket is not None:
            await self.websocket.send_bytes(screen_bytes)

    @JOverride
    def onException(self, throwable):
        throwable.printStackTrace()
        print(f"Error occurred: {throwable}")
        capture_error_event.set()

    @JOverride
    def onReady(self):
        print("Screen capture ready.")
