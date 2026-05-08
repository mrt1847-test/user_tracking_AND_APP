"""
tracking_all 이벤트 → schema_template.json 섹션과 동일한 path만 시트 행으로 추출.

템플릿을 평면화해 path 순서를 정하고, merged 소스 트리에서 값만 역추적한다.
(기존: 소스 전체 flatten 후 템플릿으로 필터)

가정: Product Exposure 의 ``expdata.parsed`` 에서 **첫 슬롯만** 사용한다
(branddeal 처럼 단일 매칭·배치 1건). ``spm`` / ``--module`` 으로 슬롯을 고르지 않는다.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from utils.google_sheets_sync import flatten_json

# 템플릿 상대 path로 merged에서 값을 찾을 때 시도하는 루트 접두어들.
# Module Exposure 등은 payload / decoded_gokey.params / params-exp.parsed 아래에 값이 있다.
_LOOKUP_PREFIX_CHAINS: List[List[str]] = [
    [],
    ["payload"],
    ["payload", "decoded_gokey", "params"],
    ["payload", "decoded_gokey", "params", "params-exp", "parsed"],
    ["payload", "decoded_gokey", "params", "params-clk", "parsed"],
]


def _utlogmap_parsed_from_params_block(block: Any) -> Optional[Dict[str, Any]]:
    """params-clk / params-exp 블록의 parsed.utLogMap.parsed 를 꺼낸다."""
    if not isinstance(block, dict):
        return None
    parsed = block.get("parsed")
    if not isinstance(parsed, dict):
        return None
    ulm = parsed.get("utLogMap")
    if not isinstance(ulm, dict):
        return None
    inner = ulm.get("parsed")
    if isinstance(inner, dict) and inner:
        return inner
    return None


def _utlogmap_from_expdata_slot(slot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    exargs = slot.get("exargs")
    if not isinstance(exargs, dict):
        return None
    pe = exargs.get("params-exp")
    return _utlogmap_parsed_from_params_block(pe)


def _first_expdata_slot(expdata: Any) -> Optional[Dict[str, Any]]:
    """expdata.parsed 의 첫 요소만 사용 (단일 슬롯 가정)."""
    if not isinstance(expdata, dict):
        return None
    plist = expdata.get("parsed")
    if not isinstance(plist, list) or not plist:
        return None
    first = plist[0]
    return first if isinstance(first, dict) else None


def _merge_expdata_slot_spm_scm(merged: Dict[str, Any], event_type: str) -> None:
    """
    Product Exposure: ``spm`` / ``scm`` 은 ``expdata.parsed[i]`` 슬롯 루트에만 있고
    ``decoded_gokey.params`` 최상위에는 없을 수 있다.
    """
    if event_type != "Product Exposure":
        return
    slot = _first_expdata_slot(merged.get("expdata"))
    if not isinstance(slot, dict):
        return
    spm = slot.get("spm")
    if isinstance(spm, str) and spm.strip():
        merged["spm"] = spm
    if "scm" in slot:
        scm = slot.get("scm")
        if isinstance(scm, str):
            merged["scm"] = scm


def _params_exp_parsed_for_product_row(merged: Dict[str, Any], event_type: str) -> Optional[Dict[str, Any]]:
    """
    시트 템플릿이 루트 path로 찾는 ``_p_sku``, ``gmkt_area_code`` 등은
    배치 노출 시 ``params`` 최상위가 아니라 ``params-exp.parsed``(또는 클릭의 ``params-clk.parsed``)에만 있다.
    Product Exposure 는 ``expdata.parsed[0]`` 의 ``params-exp.parsed`` 만 본다.
    """
    if event_type == "Product Click":
        block = merged.get("params-clk")
        if isinstance(block, dict) and isinstance(block.get("parsed"), dict):
            return block["parsed"]
        return None

    if event_type != "Product Exposure":
        return None

    slot = _first_expdata_slot(merged.get("expdata"))
    if slot:
        exargs = slot.get("exargs")
        if isinstance(exargs, dict):
            pe = exargs.get("params-exp")
            if isinstance(pe, dict) and isinstance(pe.get("parsed"), dict):
                return pe["parsed"]

    pe = merged.get("params-exp")
    if isinstance(pe, dict) and isinstance(pe.get("parsed"), dict):
        return pe["parsed"]
    return None


def _merge_scalar_product_fields_from_parsed(merged: Dict[str, Any], parsed: Optional[Dict[str, Any]]) -> None:
    """params-exp / params-clk 의 스칼라 필드를 merged 루트에 올려 템플릿 path lookup이 되게 한다."""
    if not isinstance(parsed, dict):
        return
    for k, v in parsed.items():
        if k == "utLogMap":
            continue
        if isinstance(v, (dict, list)):
            continue
        merged[k] = v


def _normalize_utlogmap_flat(merged: Dict[str, Any]) -> None:
    """
    템플릿 path ``utLogMap.*`` 가 merged 루트에서 resolve 되도록 정규화한다.

    - 배치 Product Exposure: ``expdata.parsed[0].exargs.params-exp`` 안의 utLogMap 만 본다.
    - Product Click: ``params-clk.parsed.utLogMap.parsed`` 에만 있다.
    - 단일 노출: ``utLogMap`` 이 ``{ raw, parsed }`` 래핑일 수 있다.
    """
    ulm = merged.get("utLogMap")
    if isinstance(ulm, dict):
        inner = ulm.get("parsed")
        if isinstance(inner, dict) and inner:
            merged["utLogMap"] = inner
            return
        if isinstance(ulm.get("pagePos"), str):
            return

    for key in ("params-clk", "params-exp"):
        block = merged.get(key)
        inner = _utlogmap_parsed_from_params_block(block)
        if inner:
            merged["utLogMap"] = inner
            return

    slot = _first_expdata_slot(merged.get("expdata"))
    if slot:
        inner = _utlogmap_from_expdata_slot(slot)
        if inner:
            merged["utLogMap"] = inner


def build_merged_source(event_data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """
    tracking_all 단일 이벤트를 템플릿 path lookup용 트리로 만든다.

    계약: ``resolve_value_for_template_path(merged, path)`` 가 schema_template 섹션의
    dot-path(예: ``utLogMap.query``, ``spm-cnt``)에 대해 가능한 한 값을 반환해야 한다.

    Product Exposure 에서 ``expdata`` 가 여러 슬롯이면 **첫 슬롯만** 사용한다.

    Returns:
        탐색용 dict (이벤트 타입별로 ``payload`` 래핑 또는 params 평탄 merge)
    """
    payload = event_data.get("payload") or {}

    if event_type == "Module Exposure":
        return {"payload": payload}

    if event_type in ("Product Exposure", "Product Click"):
        result: Dict[str, Any] = {}
        for key, value in payload.items():
            if key != "decoded_gokey" and not isinstance(value, (dict, list)):
                result[key] = value

        if "decoded_gokey" in payload and isinstance(payload["decoded_gokey"], dict):
            decoded = payload["decoded_gokey"]
            if "params" in decoded and isinstance(decoded["params"], dict):
                result.update(decoded["params"])

        out: Dict[str, Any] = result if result else dict(payload)
        if isinstance(out, dict) and out:
            _normalize_utlogmap_flat(out)
            _merge_expdata_slot_spm_scm(out, event_type)
            row_parsed = _params_exp_parsed_for_product_row(out, event_type)
            _merge_scalar_product_fields_from_parsed(out, row_parsed)
        return out

    if event_type in (
        "Product Minidetail",
        "General Exposure",
        "General Click",
        "Product ATC Click",
        "PDP PV",
        "PDP Buynow Click",
        "PDP ATC Click",
        "PDP Gift Click",
        "PDP Join Click",
        "PDP Rental Click",
    ):
        return {"payload": payload} if payload else {}

    return {"payload": payload} if payload else {}


def _navigate(obj: Any, key_parts: List[str]) -> Any:
    cur: Any = obj
    for k in key_parts:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def resolve_value_for_template_path(merged: Any, path: str) -> Any:
    """
    schema_template 리프 path에 해당하는 스칼라 값을 merged 트리에서 찾는다.

    여러 루트 접두어를 순서대로 시도한다. 첫 스칼라 리프가 나오면 반환.
    dict/list 리프는 건너뛰고 다음 접두어를 시도한다 (템플릿은 리프만 다룸).
    """
    if merged is None or not path:
        return None

    parts = path.split(".")
    for prefix in _LOOKUP_PREFIX_CHAINS:
        base = _navigate(merged, prefix) if prefix else merged
        if base is None:
            continue

        v = _navigate(base, parts)
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            continue
        return v
    return None


def iter_template_sheet_rows(
    template_section: Dict[str, Any],
    merged_source: Any,
    format_leaf: Callable[[str, Any], str],
    exclude_keys: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """
    템플릿 섹션의 path 순서대로 시트 한 행씩 생성한다.

    - path / field: ``flatten_json(template_section)`` 과 동일
    - value: ``merged_source`` 에서 ``resolve_value_for_template_path`` 로 구한 뒤 ``format_leaf`` 적용
    """
    if not isinstance(template_section, dict):
        return []

    ex = exclude_keys if exclude_keys is not None else ["timestamp", "method", "url"]
    rows: List[Dict[str, str]] = []
    for item in flatten_json(template_section, exclude_keys=ex):
        path = item.get("path", "")
        field = item.get("field", "")
        raw = resolve_value_for_template_path(merged_source, path)
        cell = format_leaf(field, raw)
        rows.append({"path": path, "field": field, "value": cell})
    return rows