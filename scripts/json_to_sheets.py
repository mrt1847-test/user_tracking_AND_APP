"""
JSON → 구글 시트 변환 스크립트
tracking_all JSON 파일을 구글 시트로 변환하여 기본 틀 생성
"""
import json
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.google_sheets_sync import (
    GoogleSheetsSync,
    group_by_event_type,
    TRACKING_TYPE_TO_CONFIG_KEY,
)
from utils.schema_template_merge import default_schema_template_path
from utils.template_tracking_extract import (
    build_merged_source,
    iter_template_sheet_rows,
)


# 시트에서 제외할 필드명 목록
EXCLUDE_FIELDS = [
    # 여기에 제외할 필드명을 추가하세요
    # 예: 'timestamp', 'method', 'url' 등
]

# SPM 필드별 점(.) 개수 설정 (해당 개수까지만 유지)
SPM_DOT_COUNT = {
    'spm-cnt': 3,  # spm-cnt는 점 2개까지 유지 (예: gmktpc.searchlist)
    'spm-url': 3,  # spm-url은 점 3개까지 유지 (예: gmktpc.home.searchtop)
    'spm-pre': 3,  # spm-pre는 점 3개까지 유지 (예: gmktpc.home)
}

def truncate_spm_value(value: str, max_dots: int) -> str:
    """
    SPM 값을 점(.)으로 구분하여 지정된 개수까지만 유지
    
    Args:
        value: 원본 SPM 값 (예: 'gmktpc.home.searchtop.dsearchbox.1fbf486aNeD7nd')
        max_dots: 유지할 점(.)의 최대 개수 (예: 3이면 'gmktpc.home.searchtop' 반환)
    
    Returns:
        잘린 SPM 값
    """
    if not isinstance(value, str):
        return value
    
    parts = value.split('.')
    # max_dots 개의 점을 유지하려면 max_dots + 1 개의 부분을 가져와야 함
    # 예: max_dots=3이면 4개 부분 (gmktpc, home, searchtop, dsearchbox) -> 점 3개
    truncated_parts = parts[:max_dots + 1]
    return '.'.join(truncated_parts)

def replace_value_with_placeholder(field_name: str, value: Any) -> Any:
    """
    필드명에 따라 실제 값을 placeholder / mandatory / skip 으로 치환.

    ``tracking_schemas/schema_template.json`` 에 정의된 필드만 처리한다.
    그 외(gokey, ts, device 등 공통 payload)는 치환하지 않고 원본(또는 JSON 직렬화)을 쓴다.
    (시트 행은 ``schema_template.json`` path 기준으로만 생성된다.)
    """
    if field_name in SPM_DOT_COUNT:
        max_dots = SPM_DOT_COUNT[field_name]
        return truncate_spm_value(value, max_dots)

    # schema_template.json 과 동일한 키만 (공통 필드 일괄 치환 제거)
    field_placeholder_map = {
        "query": "<검색어>",
        "origin_price": "<원가>",
        "promotion_price": "<할인가>",
        "coupon_price": "<쿠폰적용가>",
        "_p_prod": "<상품번호>",
        "x_object_id": "<상품번호>",
        "is_ad": "<is_ad>",
        "trafficType": "<trafficType>",
        "pguid": "skip",
        "sguid": "skip",
        "_p_catalog": "skip",
        "_p_group": "skip",
        "ab_buckets": "skip",
        "pvid": "skip",
        "search_session_id": "skip",
        "match_type": "skip",
        "cate_leaf_id": "skip",
        "module_index": "mandatory"
    }

    if field_name in field_placeholder_map:
        return field_placeholder_map[field_name]

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)

    return value


def _known_schema_root_keys() -> set:
    """tracking_schemas/*.json 최상위 섹션 키 (google_sheets_sync 매핑 기준)."""
    return set(TRACKING_TYPE_TO_CONFIG_KEY.values())


def is_tracking_schema_document(data: Any) -> bool:
    """
    tracking_all 배열이 아니라, module_exposure 등 섹션 객체 하나인 JSON인지 판별.
    """
    if not isinstance(data, dict) or not data:
        return False
    known = _known_schema_root_keys()
    return bool(known.intersection(data.keys()))


def resolve_input_json_path(raw: str, project_root: Path) -> Path:
    """
    --input 경로를 실제 JSON 파일로 해석한다.

    PowerShell에서 ``...newlowest(1).json`` 처럼 따옴표 없이 주면 ``(1)`` 가 잘려
    ``...newlowest`` 만 전달되는 경우가 있어, 해당 접두어로 ``*.json`` glob 을 시도한다.
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("--input 값이 비어 있습니다.")

    p = Path(raw)
    search_bases: List[Path] = []
    if p.is_absolute():
        search_bases.append(p)
    else:
        search_bases.append(project_root / p)
        search_bases.append(Path.cwd() / p)

    def first_existing_file(paths: List[Path]) -> Optional[Path]:
        for cand in paths:
            try:
                if cand.is_file():
                    return cand.resolve()
            except OSError:
                continue
        return None

    hit = first_existing_file(search_bases)
    if hit:
        return hit

    for base in search_bases:
        if base.suffix.lower() != ".json":
            alt = base.with_suffix(".json")
            try:
                if alt.is_file():
                    return alt.resolve()
            except OSError:
                pass

    for base in search_bases:
        name = base.name
        if not name:
            continue
        parent = base.parent
        try:
            if not parent.is_dir():
                continue
        except OSError:
            continue
        matches = sorted(parent.glob(name + "*.json"))
        if len(matches) == 1:
            print(
                f"입력 경로 보정: {raw!r} → {matches[0]} "
                "(파일명에 괄호가 있으면 PowerShell에서는 "
                "--input 'json/…(1).json' 처럼 작은따옴표로 감싸는 것을 권장합니다.)"
            )
            return matches[0].resolve()
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise FileNotFoundError(
                f"입력 파일을 찾을 수 없습니다: {raw!r}. "
                f"접두어 {name!r}에 해당하는 JSON이 여러 개입니다: {names}. "
                "전체 파일명을 따옴표와 함께 지정하세요."
            )

    raise FileNotFoundError(
        f"입력 JSON을 찾을 수 없습니다: {raw!r}. "
        "프로젝트 루트 또는 현재 디렉터리 기준 경로를 확인하세요. "
        "PowerShell: --input 'json/tracking_all_모듈(1).json'"
    )


def infer_module_from_input_path(input_path: str) -> str:
    """
    입력 경로의 파일명에서 모듈 ID를 추출한다.

    기대 패턴: ``tracking_all_<module>`` 또는 ``tracking_all_<module>(숫자)`` (+ 선택적 ``.json``).
    예: ``json/tracking_all_today_branddeal(1).json`` → ``today_branddeal``

    Args:
        input_path: ``--input`` 과 동일한 경로 문자열

    Returns:
        모듈명 (스키마/시트의 모듈 키와 동일하게 쓰임)

    Raises:
        ValueError: 파일명이 ``tracking_all_`` 로 시작하지 않거나, 모듈 부분이 비어 있는 경우
    """
    p = Path(input_path)
    stem = p.stem
    if not stem.startswith("tracking_all_"):
        raise ValueError(
            f"모듈 자동 추출: 파일명(확장자 제외)이 'tracking_all_' 으로 시작해야 합니다. "
            f"현재 stem={stem!r}. --module 로 명시하세요."
        )
    rest = stem[len("tracking_all_") :].strip()
    if not rest:
        raise ValueError(
            f"모듈 자동 추출: 'tracking_all_' 뒤에 모듈 식별자가 없습니다. stem={stem!r}"
        )
    # 복사본 표기 tracking_all_foo(1) → foo
    module_id = re.sub(r"\(\d+\)$", "", rest).strip()
    if not module_id:
        raise ValueError(
            f"모듈 자동 추출: '(숫자)' 제거 후 모듈명이 비었습니다. rest={rest!r}"
        )
    return module_id


def load_tracking_json(file_path: str) -> List[Dict[str, Any]]:
    """
    tracking_all JSON 파일 로드
    
    Args:
        file_path: JSON 파일 경로
        
    Returns:
        트래킹 데이터 배열
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        raise ValueError(f"JSON 파일은 배열 형태여야 합니다: {file_path}")
    
    return data


def _format_sheet_cell(field: str, raw: Any) -> str:
    """템플릿 리프에 대응하는 시트 값 문자열."""
    out = replace_value_with_placeholder(field, raw if raw is not None else "")
    if isinstance(out, str):
        return out
    return str(out)


def _flatten_module_fields_for_sheet(
    merged_source: Any,
    template_section: Any = None,
) -> List[Dict[str, str]]:
    """
    schema_template 섹션의 path 순서대로, merged tracking 소스에서 값을 채워 시트 행을 만든다.
    """
    if not isinstance(template_section, dict):
        print("경고: 기준 템플릿 섹션이 없어 해당 이벤트 행을 건너뜁니다.")
        return []
    exclude_keys = ["timestamp", "method", "url"] + [k for k in EXCLUDE_FIELDS if k not in ("timestamp", "method", "url")]
    return iter_template_sheet_rows(
        template_section,
        merged_source,
        format_leaf=_format_sheet_cell,
        exclude_keys=exclude_keys,
    )


def _build_event_type_rows_from_schema(
    schema_obj: Dict[str, Any],
    event_type_order: List[str],
    excluded_event_types: List[str],
    template_obj: Any = None,
) -> List[Tuple[str, List[Dict[str, str]]]]:
    """
    tracking_schemas 형 JSON(상품평 많은순.json 등) → (이벤트 타입, 평면 필드) 목록.
    섹션은 이미 최종 형태이므로 build_merged_source 를 거치지 않는다.
    """
    rows_out: List[Tuple[str, List[Dict[str, str]]]] = []
    for event_type in event_type_order:
        if event_type in excluded_event_types:
            print(f"[{event_type}] 등록에서 제외됨 (스키마 모드)")
            continue
        config_key = TRACKING_TYPE_TO_CONFIG_KEY.get(event_type)
        if not config_key or config_key not in schema_obj:
            continue
        section = schema_obj[config_key]
        if not isinstance(section, dict):
            continue
        tmpl_sec = None
        if isinstance(template_obj, dict):
            tmpl_sec = template_obj.get(config_key)
        flattened = _flatten_module_fields_for_sheet(section, tmpl_sec)
        if not flattened:
            continue
        rows_out.append((event_type, flattened))
        print(f"[{event_type}] {len(flattened)}개 고유 필드 평면화 완료 (스키마 JSON)")
    return rows_out


def main():
    parser = argparse.ArgumentParser(
        description=(
            "JSON을 구글 시트로 반영. "
            "tracking_all 배열 또는 tracking_schemas 형 단일 객체 지원. "
            "시트 경로는 schema_template.json 과 동일하며, 값은 tracking 에서만 채운다."
        ),
        epilog=(
            "PowerShell: 파일명에 괄호가 있으면 반드시 작은따옴표로 경로를 감싸세요. "
            "예: --input 'json/tracking_all_today_newlowest(1).json'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='입력 JSON (tracking_all 배열 또는 module_exposure 등이 있는 스키마 객체)',
    )
    parser.add_argument(
        '--module',
        type=str,
        default=None,
        help=(
            '모듈명 (시트 A열 모듈 키, 예: today_branddeal). '
            '생략 시 --input 파일명에서 추출: tracking_all_<모듈>(선택적 (숫자)).json'
        ),
    )
    parser.add_argument(
        '--area',
        type=str,
        required=True,
        help='영역명 (SRP, PDP, HOME, CART 등)'
    )
    parser.add_argument(
        '--template',
        type=str,
        default=None,
        help='기준 스키마 JSON (기본: tracking_schemas/schema_template.json). path·리프 집합의 유일한 기준.',
    )
    args = parser.parse_args()

    args.input = str(resolve_input_json_path(args.input, project_root))

    module_name: Optional[str] = (args.module or "").strip() or None
    if not module_name:
        module_name = infer_module_from_input_path(args.input)
        print(f"모듈명 자동 추출: {module_name!r} (--input 파일명 기준)")
    args.module = module_name

    # config.json에서 설정 로드
    config_path = project_root / 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    SPREADSHEET_ID = config.get('spreadsheet_id')
    if not SPREADSHEET_ID:
        raise RuntimeError("config.json에 'spreadsheet_id'가 설정되어 있지 않습니다.")
    CREDENTIALS_PATH = str(project_root / 'python-link-test-380006-2868d392d217.json')
    
    tmpl_path = Path(args.template) if args.template else default_schema_template_path(project_root)
    if not tmpl_path.is_file():
        raise RuntimeError(f"기준 템플릿 파일이 필요합니다. 없음: {tmpl_path}")
    with open(tmpl_path, encoding="utf-8") as f:
        template_obj = json.load(f)
    print(f"기준 템플릿 로드 (path 기준): {tmpl_path}")

    # JSON 파일 로드 (스키마 객체 vs tracking_all 배열 자동 판별)
    print(f"JSON 파일 로드 중: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    use_schema = is_tracking_schema_document(raw_data)
    if use_schema:
        schema_obj = raw_data
        print("입력 형식: tracking_schemas 스타일 객체 (섹션 키 고정, 값만 시트로)")
        grouped = None
    else:
        if not isinstance(raw_data, list):
            raise ValueError(
                "JSON이 배열도 스키마 객체도 아닙니다. "
                "tracking_all 배열 또는 module_exposure 등이 있는 스키마 파일을 사용하세요."
            )
        tracking_data = raw_data
        print(f"총 {len(tracking_data)}개의 이벤트 로드됨 (tracking_all)")
        grouped = group_by_event_type(tracking_data)
        print(f"이벤트 타입: {list(grouped.keys())}")
    
    # 구글 시트 연동 객체 생성
    print(f"구글 시트 연결 중... (Spreadsheet ID: {SPREADSHEET_ID})")
    sync = GoogleSheetsSync(SPREADSHEET_ID, CREDENTIALS_PATH)
    
    # 영역 시트 가져오기 또는 생성 (시트명: 영역만, 예: SRP)
    worksheet_name = args.area
    print(f"워크시트 '{worksheet_name}' 준비 중...")
    worksheet = sync.get_or_create_worksheet(worksheet_name)
    
    # 표 생성 전에 기존 데이터 읽기 (addTable 시 범위 변경 가능성 대비)
    all_values = worksheet.get_all_values()
    data_rows = all_values[1:] if len(all_values) > 1 else []
    kept = [r for r in data_rows if len(r) >= 1 and (r[0].strip() != args.module)]
    
    table_created = sync.ensure_area_table(worksheet, args.area)
    if not table_created:
        print("⚠️ 표(Native Table) 생성 실패/건너뜀. 1행 헤더만 쓰고 데이터는 A2:E에 기록합니다. (위 traceback 확인)")
        sync.ensure_area_header(worksheet)
    
    # 이벤트 타입 순서 (config JSON 구조에 맞춤)
    event_type_order = [
        'Module Exposure',
        'Product Exposure',
        'Product Click',
        'General Exposure',
        'General Click',
        'Product ATC Click',
        'Product Minidetail',
        'PDP PV',
        'PDP Buynow Click',
        'PDP ATC Click',
        'PDP Gift Click',
        'PDP Join Click',
        'PDP Rental Click',
        'PV',
    ]
    
    # 등록에서 제외할 이벤트 타입 (관련 로직은 유지)
    EXCLUDED_EVENT_TYPES = ['PDP PV', 'PV']
    
    if use_schema:
        event_type_rows = _build_event_type_rows_from_schema(
            schema_obj,
            event_type_order,
            EXCLUDED_EVENT_TYPES,
            template_obj,
        )
    else:
        event_type_rows = []
        for event_type in event_type_order:
            if grouped is None or event_type not in grouped:
                continue
            if event_type in EXCLUDED_EVENT_TYPES:
                print(f"[{event_type}] 등록에서 제외됨 (관련 로직은 유지)")
                continue
            events = grouped[event_type]
            if not events:
                continue
            event_data = events[0]
            merged = build_merged_source(event_data, event_type)
            config_key = TRACKING_TYPE_TO_CONFIG_KEY[event_type]
            tmpl_sec = template_obj.get(config_key) if isinstance(template_obj, dict) else None
            flattened = _flatten_module_fields_for_sheet(merged, tmpl_sec)
            if not flattened:
                continue
            event_type_rows.append((event_type, flattened))
            print(f"[{event_type}] {len(flattened)}개 고유 필드 평면화 완료")
    
    # 데이터만 A2:E에 기록 (1행은 표 헤더, 건드리지 않음)
    ncols = sync.AREA_NCOLS
    # 컬럼 수를 정확히 ncols로 맞춤 (부족하면 채우고, 초과하면 자름)
    trim = lambda r: (r + [''] * (ncols - len(r)))[:ncols]
    new_rows = sync.build_area_module_rows(args.module, event_type_rows)
    to_write = [trim(r) for r in kept] + [trim(r) for r in new_rows]
    
    sync.clear_area_data_range(worksheet)
    if to_write:
        worksheet.update(to_write, range_name='A2', value_input_option='RAW')
    
    last_row = 1 + len(to_write)
    sync.format_area_data_as_text(worksheet, last_row)
    
    print(f"\n✅ 완료! 시트 '{worksheet_name}'에 모듈 '{args.module}' Upsert 완료")
    print(f"구글 시트 URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")


if __name__ == '__main__':
    main()
