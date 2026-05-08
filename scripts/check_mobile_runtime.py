import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.appium_runtime import AppiumRuntime


def main() -> None:
    project_root = PROJECT_ROOT
    config_path = project_root / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    runtime = AppiumRuntime(project_root, config)
    info = runtime.verify_local_environment()
    print("Mobile runtime verification")
    for key, value in info.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
