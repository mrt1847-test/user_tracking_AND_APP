from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple


class TrackerBackend(Protocol):
    """검증 스텝이 요구하는 최소 트래커 백엔드 인터페이스."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def clear_logs(self) -> None: ...
    def get_logs(self, request_type: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def get_h_ut_pipeline(self) -> List[Dict[str, Any]]: ...
    def validate_payload(
        self,
        log: Dict[str, Any],
        expected_data: Dict[str, Any],
        goodscode: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]: ...
