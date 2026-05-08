"""
tracking_schemas/*.json 형태(고정 키·중첩)를 유지한 채 시트 등에서 읽은 값만 리프에 덮어쓸 때 사용.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.google_sheets_sync import flatten_json

DEFAULT_SCHEMA_TEMPLATE_REL = Path("tracking_schemas") / "schema_template.json"


def default_schema_template_path(project_root: Path) -> Path:
    return project_root / DEFAULT_SCHEMA_TEMPLATE_REL


def template_leaf_paths(
    template_section: dict,
    exclude_keys: Optional[List[str]] = None,
) -> set[str]:
    """기준 템플릿 섹션을 시트와 동일 규칙으로 평면화한 path 집합."""
    if exclude_keys is None:
        exclude_keys = ["timestamp", "method", "url"]
    if not isinstance(template_section, dict):
        return set()
    return {item["path"] for item in flatten_json(template_section, exclude_keys=exclude_keys)}


def filter_flat_rows_to_template(
    flat_list: List[Dict[str, Any]],
    template_section: Optional[dict],
    exclude_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    tracking_all 등에서 나온 평면 행을 기준 템플릿에 정의된 path만 남긴다.

    템플릿 섹션에 ``payload`` 키가 없고 원본 path가 ``payload.`` 로 시작하면
    접두사를 제거한 뒤 템플릿 path와 매칭한다 (시트→JSON 병합과 동일).
    """
    if not template_section or not isinstance(template_section, dict):
        return flat_list
    allowed = template_leaf_paths(template_section, exclude_keys=exclude_keys)
    if not allowed:
        return flat_list
    use_payload_strip = "payload" not in template_section
    out: List[Dict[str, Any]] = []
    for item in flat_list:
        p = item.get("path", "")
        if p in allowed:
            out.append(dict(item))
            continue
        if use_payload_strip and p.startswith("payload."):
            stripped = p[len("payload.") :]
            if stripped in allowed:
                new_item = dict(item)
                new_item["path"] = stripped
                new_item["field"] = stripped.split(".")[-1] if stripped else ""
                out.append(new_item)
                continue
    return out


def normalize_sheet_config_for_template_merge(template: dict, sheet_cfg: dict) -> dict:
    """
    시트→JSON 파이프라인이 섹션에 `payload` 래퍼를 붙인 경우(예: module_exposure),
    템플릿에 `payload` 없이 리프가 있는 형태와 맞추기 위해 한 단계 펼친다.
    """
    out = copy.deepcopy(sheet_cfg)
    for ck, tmpl_sec in template.items():
        if ck not in out:
            continue
        sec = out[ck]
        if not isinstance(tmpl_sec, dict) or not isinstance(sec, dict):
            continue
        if "payload" in sec and "payload" not in tmpl_sec:
            inner = sec.get("payload")
            if isinstance(inner, dict):
                rest = {k: v for k, v in sec.items() if k != "payload"}
                out[ck] = {**inner, **rest}
    return out


def merge_template_with_sheet_data(template: Any, sheet_nested: Any) -> Any:
    """
    템플릿 JSON의 키·구조를 그대로 두고, sheet_nested에 존재하는 동일 경로의 리프 값만 갱신한다.

    - template에만 있는 키: 그대로 유지 (deepcopy).
    - 둘 다 dict: 재귀 병합.
    - 리프(한쪽이 비-dict): sheet_nested 값을 사용(시트에 반영된 값).
    - sheet_nested에만 있는 키: 무시(템플릿에 없으면 추가하지 않음).

    Args:
        template: 기준 스키마(예: GEMINI/상품평 많은순.json).
        sheet_nested: 시트 → unflatten → create_config_json 결과.

    Returns:
        병합된 dict (주로 dict 루트).
    """
    if isinstance(template, dict) and isinstance(sheet_nested, dict):
        out: dict[str, Any] = {}
        for key, tmpl_val in template.items():
            if key not in sheet_nested:
                out[key] = copy.deepcopy(tmpl_val)
                continue
            upd_val = sheet_nested[key]
            if isinstance(tmpl_val, dict) and isinstance(upd_val, dict):
                out[key] = merge_template_with_sheet_data(tmpl_val, upd_val)
            else:
                out[key] = copy.deepcopy(upd_val) if upd_val is not None else copy.deepcopy(tmpl_val)
        return out

    if isinstance(template, dict) and not isinstance(sheet_nested, dict):
        return copy.deepcopy(template)

    return copy.deepcopy(sheet_nested) if sheet_nested is not None else copy.deepcopy(template)
