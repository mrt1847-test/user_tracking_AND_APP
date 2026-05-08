import json
import signal
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.appium_runtime import AppiumRuntime


def main() -> None:
    project_root = PROJECT_ROOT
    config = json.loads((project_root / "config.json").read_text(encoding="utf-8"))
    runtime = AppiumRuntime(project_root, config)
    runtime.start_proxy()
    print(f"mitmproxy capture started: {runtime.proxy_host}:{runtime.proxy_port}")
    print(f"capture file: {runtime.capture_file}")

    def _shutdown(*_args):
        runtime.stop_proxy()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
