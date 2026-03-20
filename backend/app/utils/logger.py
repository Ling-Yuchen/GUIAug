import datetime
import threading
from pathlib import Path

class SimpleLogger:
    def __init__(self, log_to_file=False):
        self.log_to_file = log_to_file
        self.log_file_path = str(Path(__file__).parent.parent.parent.resolve() / "data" / "log" / f"log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.log")
        self._lock = threading.Lock()
        self.cost = 0

    def log(self, tag: str, message: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] | [{tag}] : {message}"

        with self._lock:
            print(log_line)
            if self.log_to_file:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")

    def success(self, message: str):
        self.log("SUCCESS", message)

    def debug(self, message: str):
        self.log("DEBUG", message)

logger = SimpleLogger(log_to_file=True)
