from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MitmproxyCollector:
    """mitmproxy jsonl 캡처 파일을 증분으로 읽는 수집기."""

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path
        self._offset = 0

    def reset_offset(self) -> None:
        self._offset = 0

    def read_new_records(self) -> List[Dict[str, Any]]:
        if not self.source_path.exists():
            return []

        records: List[Dict[str, Any]] = []
        with self.source_path.open("r", encoding="utf-8") as fp:
            fp.seek(self._offset)
            for line in fp:
                payload = line.strip()
                if not payload:
                    continue
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("MitmproxyCollector: invalid json line skipped: %s", payload[:200])
                    continue
                if not isinstance(parsed, dict):
                    continue
                records.append(parsed)
            self._offset = fp.tell()
        return records
