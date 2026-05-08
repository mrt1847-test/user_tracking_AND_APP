"""
구글 시트 → JSON 변환 스크립트
구글 시트 데이터를 읽어서 config JSON 파일 생성/업데이트
"""
import json
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.google_sheets_sync import (
    GoogleSheetsSync,
    unflatten_json,
)
from utils.schema_template_merge import (
    default_schema_template_path,
    merge_template_with_sheet_data,
    normalize_sheet_config_for_template_merge,
)

logger = logging.getLogger(__name__)


def _resolve_template_path(
    merge_structure: bool,
    explicit_template: Optional[str],
    fallback_existing_output: Optional[Path] = None,
) -> Optional[Path]:
    """
    구조 병합용 템플릿 경로: --template > schema_template.json > 기존 출력 JSON(단일 모듈 폴백).
    """
    if not merge_structure:
        return None
    if explicit_template:
        p = Path(explicit_template)
        if p.is_file():
            return p
        print(f"경고: --template 파일 없음 ({p}), schema_template.json 또는 출력 파일 폴백을 시도합니다.")
    default_tp = default_schema_template_path(project_root)
    if default_tp.is_file():
        return default_tp
    if fallback_existing_output is not None and fallback_existing_output.is_file():
        return fallback_existing_output
    return None


def create_config_json(
    event_data_dict: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    이벤트 타입별 데이터를 config JSON 구조로 변환
    
    Args:
        event_data_dict: {config_key: [{"path":..., "value":...}, ...]} 형태
        
    Returns:
        config JSON 구조
    """
    config = {}
    
    # payload 구조를 유지해야 하는 이벤트 타입들
    # module_exposure, product_atc_click, product_minidetail, pdp_pv, pdp_buynow_click 등은 payload 전체를 사용
    payload_preserving_types = [
        'module_exposure', 'product_atc_click', 'product_minidetail', 'pdp_pv',
        'pdp_buynow_click', 'pdp_atc_click', 'pdp_gift_click', 'pdp_join_click', 'pdp_rental_click',
    ]

    # schema_template 기준으로 payload 래핑 없이 평탄 키를 유지해야 하는 타입들
    # (General 이벤트는 schema_template에서 flat 구조이므로 sheets_to_json에서도 동일하게 유지)
    flat_schema_types = ['general_exposure', 'general_click']
    
    for config_key, flat_data in event_data_dict.items():
        if not flat_data:
            continue
        
        # 평면 데이터를 중첩 구조로 변환
        nested_data = unflatten_json(flat_data)
        
        # payload 구조를 유지해야 하는 이벤트 타입 처리
        if config_key in payload_preserving_types:
            # payload가 이미 최상위에 있으면 그대로 사용
            if 'payload' in nested_data:
                config[config_key] = nested_data
            else:
                # payload가 없으면 payload 객체로 감싸기
                # 이는 시트에 저장된 모듈 필드의 경로가 payload. prefix 없이 저장된 경우를 처리
                config[config_key] = {'payload': nested_data}
        else:
            # 다른 이벤트 타입은 그대로 사용
            config[config_key] = nested_data

        # General 이벤트는 payload 래핑이 들어오더라도 스키마(flat) 형태로 정규화
        if config_key in flat_schema_types and isinstance(config.get(config_key), dict):
            cur = config[config_key]
            if 'payload' in cur and isinstance(cur['payload'], dict):
                payload_inner = cur['payload']
                rest = {k: v for k, v in cur.items() if k != 'payload'}
                config[config_key] = {**payload_inner, **rest}
    
    return config


def _apply_structure_template(
    config_json: Dict[str, Any],
    template_path: Optional[Path],
    merge_structure: bool,
) -> Dict[str, Any]:
    """tracking_schemas 형태 템플릿이 있으면 키·구조 유지하고 시트 값만 리프에 반영."""
    if not merge_structure or not template_path or not template_path.is_file():
        return config_json
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("템플릿 로드 실패, 병합 생략: %s (%s)", template_path, e)
        return config_json
    if not isinstance(template, dict):
        return config_json
    normalized = normalize_sheet_config_for_template_merge(template, config_json)
    return merge_template_with_sheet_data(template, normalized)


def convert_module_to_json(
    sync: GoogleSheetsSync,
    worksheet: Any,
    area: str,
    module: str,
    output_path: Path,
    overwrite: bool,
    verbose: bool = True,
    template_path: Optional[Path] = None,
    merge_structure: bool = True,
) -> bool:
    """
    시트에서 한 모듈 데이터를 읽어 config JSON 파일로 저장.
    Returns:
        성공 시 True, 실패 시 False
    """
    if output_path.exists() and not overwrite:
        if verbose:
            print(f"  [건너뜀] 이미 존재: {output_path} (--overwrite 사용 시 덮어쓰기)")
        return False

    event_data_dict = sync.read_area_module_data(worksheet, module)
    if not event_data_dict:
        if verbose:
            print(f"  [건너뜀] 모듈 '{module}' 데이터 없음")
        return False

    config_json = create_config_json(event_data_dict)
    config_json = _apply_structure_template(config_json, template_path, merge_structure)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config_json, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  [OK] {output_path} (섹션: {list(config_json.keys())})")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='구글 시트 데이터를 읽어서 config JSON 파일 생성/업데이트'
    )
    parser.add_argument(
        '--sheet',
        action='store_true',
        help='시트 단위 변환: 해당 영역 시트 전체를 읽어 모듈별로 JSON 파일 생성 (--area만 필요)'
    )
    parser.add_argument(
        '--module',
        type=str,
        default=None,
        help='모듈명 (예: "먼저 둘러보세요"). --sheet 사용 시 무시됨'
    )
    parser.add_argument(
        '--area',
        type=str,
        required=True,
        help='영역명 (SRP, PDP, HOME, CART 등)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='출력 JSON 파일 경로 (단일 모듈 모드에서만 사용, 기본값: tracking_schemas/{area}/{module}.json)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='기존 파일이 있으면 덮어쓰기 (기본값: False)'
    )
    parser.add_argument(
        '--template',
        type=str,
        default=None,
        help=(
            '구조 고정용 JSON 경로 (기본: tracking_schemas/schema_template.json, 없으면 단일 모드에서 기존 출력 파일). '
            '해당 키·중첩을 유지하고 시트에서 읽은 값만 리프에 반영.'
        ),
    )
    parser.add_argument(
        '--no-structure-merge',
        action='store_true',
        help='템플릿 병합 없이 시트 데이터만으로 JSON 생성 (기존 동작에 가깝게)',
    )

    args = parser.parse_args()

    # 시트 단위 변환 모드: --area만 필요
    if args.sheet:
        if args.output:
            print("경고: --sheet 모드에서는 --output이 무시됩니다. 각 모듈은 tracking_schemas/{area}/{모듈명}.json에 저장됩니다.")
        _run_sheet_mode(args)
        return

    # 단일 모듈 모드: --module 필수
    if not args.module:
        print("오류: 단일 모듈 변환 시 --module이 필요합니다. 시트 전체 변환은 --sheet 를 사용하세요.")
        sys.exit(1)

    _run_single_module_mode(args)


def _load_sheet_config() -> tuple:
    """config.json에서 구글 시트 관련 설정 로드."""
    config_path = project_root / 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    spreadsheet_id = config.get('spreadsheet_id')
    if not spreadsheet_id:
        raise RuntimeError("config.json에 'spreadsheet_id'가 설정되어 있지 않습니다.")
    credentials_path = str(project_root / 'python-link-test-380006-2868d392d217.json')
    return spreadsheet_id, credentials_path


def _run_sheet_mode(args: Any) -> None:
    """시트 전체를 읽어 모듈별로 config JSON 파일 생성."""
    SPREADSHEET_ID, CREDENTIALS_PATH = _load_sheet_config()

    print(f"구글 시트 연결 중... (Spreadsheet ID: {SPREADSHEET_ID})")
    sync = GoogleSheetsSync(SPREADSHEET_ID, CREDENTIALS_PATH)

    worksheet_name = args.area
    print(f"\n시트 '{worksheet_name}' 전체 변환 (모듈별 JSON 생성)...")
    try:
        worksheet = sync.get_or_create_worksheet(worksheet_name)
        modules = sync.list_area_modules(worksheet)
    except Exception as e:
        print(f"오류: 시트 접근 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not modules:
        print("해당 시트에 모듈 데이터가 없습니다.")
        sys.exit(0)

    print(f"모듈 {len(modules)}개 발견: {modules}")
    out_dir = project_root / 'tracking_schemas' / args.area
    out_dir.mkdir(parents=True, exist_ok=True)
    merge_structure = not args.no_structure_merge
    explicit = args.template
    success = 0
    for module in modules:
        output_path = out_dir / f"{module}.json"
        tp = _resolve_template_path(merge_structure, explicit, output_path)
        if convert_module_to_json(
            sync, worksheet, args.area, module,
            output_path, args.overwrite,
            verbose=True,
            template_path=tp,
            merge_structure=merge_structure,
        ):
            success += 1
    print(f"\n완료: {success}/{len(modules)}개 모듈 JSON 생성 -> {out_dir}")


def _run_single_module_mode(args: Any) -> None:
    """기존처럼 단일 모듈만 변환."""
    SPREADSHEET_ID, CREDENTIALS_PATH = _load_sheet_config()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = project_root / 'tracking_schemas' / args.area / f"{args.module}.json"

    if output_path.exists() and not args.overwrite:
        print(f"오류: 파일이 이미 존재합니다: {output_path}")
        print("덮어쓰려면 --overwrite 플래그를 사용하세요.")
        sys.exit(1)

    print(f"구글 시트 연결 중... (Spreadsheet ID: {SPREADSHEET_ID})")
    sync = GoogleSheetsSync(SPREADSHEET_ID, CREDENTIALS_PATH)

    worksheet_name = args.area
    print(f"\n시트 '{worksheet_name}'에서 모듈 '{args.module}' 데이터 읽는 중...")
    try:
        worksheet = sync.get_or_create_worksheet(worksheet_name)
        event_data_dict = sync.read_area_module_data(worksheet, args.module)
        for ck, rows in event_data_dict.items():
            print(f"  [{ck}]: {len(rows)}개 고유 필드 읽음")
    except Exception as e:
        print(f"오류: 시트에서 데이터 읽기 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not event_data_dict:
        print("오류: 시트에서 데이터를 읽을 수 없습니다.")
        print("  시트 이름: '%s', 모듈: '%s'" % (worksheet_name, args.module))
        sys.exit(1)

    print("\nconfig JSON 구조 생성 중...")
    config_json = create_config_json(event_data_dict)
    merge_structure = not args.no_structure_merge
    tp = _resolve_template_path(merge_structure, args.template, output_path)
    config_json = _apply_structure_template(config_json, tp, merge_structure)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nJSON 파일 저장 중: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config_json, f, ensure_ascii=False, indent=2)
    print("완료: config JSON 생성 -> %s" % output_path)
    print("생성된 섹션: %s" % list(config_json.keys()))


if __name__ == '__main__':
    main()
