"""
config 파일과 tracking_all 파일을 비교하여 누락된 필드 확인
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, Set, List

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.google_sheets_sync import flatten_json

# 이벤트 타입 매핑
EVENT_TYPE_MAP = {
    'Module Exposure': 'module_exposure',
    'Product Exposure': 'product_exposure',
    'Product Click': 'product_click',
    'Product ATC Click': 'product_atc_click',
    'PDP PV': 'pdp_pv',
    'PV': 'pv',
}


def get_all_paths(data: Dict[str, Any], prefix: str = '') -> Set[str]:
    """중첩된 딕셔너리에서 모든 경로 추출"""
    paths = set()
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, (dict, list)):
                paths.update(get_all_paths(value, current_path))
            else:
                paths.add(current_path)
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            if isinstance(item, (dict, list)):
                paths.update(get_all_paths(item, f"{prefix}[{idx}]"))
    
    return paths


def normalize_path(path: str, remove_payload_prefix: bool = False, remove_decoded_gokey: bool = False) -> str:
    """경로 정규화 (배열 인덱스 제거 등)"""
    import re
    # payload. prefix 제거 (필요한 경우)
    if remove_payload_prefix and path.startswith('payload.'):
        path = path[8:]  # 'payload.' 길이만큼 제거
    
    # decoded_gokey.params. prefix 제거 (Product Exposure, Product Click의 경우)
    if remove_decoded_gokey:
        if path.startswith('decoded_gokey.params.'):
            path = path[22:]  # 'decoded_gokey.params.' 길이만큼 제거
        elif path.startswith('payload.decoded_gokey.params.'):
            path = path[30:]  # 'payload.decoded_gokey.params.' 길이만큼 제거
    
    # [0] 같은 배열 인덱스 제거
    path = re.sub(r'\[\d+\]', '[0]', path)
    return path


def compare_event(
    event_type: str,
    tracking_data: Dict[str, Any],
    config_data: Dict[str, Any],
) -> Dict[str, Any]:
    """단일 이벤트 타입 비교 (모듈 config 섹션만 기준)"""
    config_key = EVENT_TYPE_MAP.get(event_type)
    if not config_key:
        return {}
    
    # tracking_all에서 필드 추출
    # tracking_all의 모든 이벤트는 payload 안에 있음
    tracking_flat = flatten_json(tracking_data, exclude_keys=['timestamp', 'method', 'url'])
    
    # payload prefix를 제거해야 하는 이벤트 타입 확인
    remove_payload = config_key in ['product_exposure', 'product_click']
    
    # decoded_gokey.params prefix를 제거해야 하는 이벤트 타입 확인
    # Product Exposure와 Product Click은 decoded_gokey.params. prefix를 제거해야 함
    remove_decoded_gokey = config_key in ['product_exposure', 'product_click']
    
    tracking_paths = set()
    for item in tracking_flat:
        path = item['path']
        # payload. prefix 제거 (필요한 경우)
        if remove_payload and path.startswith('payload.'):
            path = path[8:]  # 'payload.' 길이만큼 제거
        tracking_paths.add(normalize_path(path, remove_payload_prefix=False, remove_decoded_gokey=remove_decoded_gokey))
    
    config_event_config = config_data.get(config_key, {})
    if config_event_config:
        module_flat = flatten_json(config_event_config, exclude_keys=['timestamp', 'method', 'url'])
    else:
        module_flat = []

    module_paths = {normalize_path(item['path']) for item in module_flat}
    all_config_paths = module_paths

    missing_in_config = tracking_paths - all_config_paths

    result = {
        'event_type': event_type,
        'config_key': config_key,
        'tracking_fields_count': len(tracking_paths),
        'config_fields_count': len(all_config_paths),
        'module_fields_count': len(module_paths),
        'missing_fields': sorted(list(missing_in_config)),
        'missing_count': len(missing_in_config),
        'only_in_tracking': sorted(list(missing_in_config)),
    }
    
    return result


def main():
    # 파일 경로
    project_root = Path(__file__).parent.parent
    tracking_file = project_root / 'json' / 'tracking_all_4.5_이상.json'
    config_file = project_root / 'tracking_schemas' / 'SRP' / '4.5 이상.json'

    # 파일 읽기
    print("파일 로드 중...")
    with open(tracking_file, 'r', encoding='utf-8') as f:
        tracking_all = json.load(f)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # 비교할 이벤트 타입 (pv, pdp_pv 제외)
    exclude_types = ['PV', 'PDP PV']
    
    results = []
    
    for event in tracking_all:
        event_type = event.get('type')
        if event_type in exclude_types:
            continue
        
        if event_type not in EVENT_TYPE_MAP:
            print(f"[SKIP] 알 수 없는 이벤트 타입: {event_type}")
            continue
        
        payload = event.get('payload', {})
        result = compare_event(event_type, payload, config_data)
        results.append(result)
    
    # 결과 출력
    print("=" * 80)
    print("비교 결과")
    print("=" * 80)
    
    for result in results:
        print(f"\n[{result['event_type']}]")
        print(f"  Config Key: {result['config_key']}")
        print(f"  Tracking 필드 수: {result['tracking_fields_count']}")
        print(f"  Config 필드 수: {result['config_fields_count']} (모듈: {result['module_fields_count']})")
        print(f"  누락된 필드 수: {result['missing_count']}")
        
        if result['missing_count'] > 0:
            print(f"\n  [WARNING] 누락된 필드 목록:")
            for field in result['missing_fields'][:20]:  # 최대 20개만 표시
                print(f"    - {field} [config에 없음]")
            
            if len(result['missing_fields']) > 20:
                print(f"    ... 외 {len(result['missing_fields']) - 20}개")
        else:
            print("  [OK] 누락된 필드 없음")
    
    # 요약
    print("\n" + "=" * 80)
    print("요약")
    print("=" * 80)
    total_missing = sum(r['missing_count'] for r in results)
    print(f"총 누락된 필드 수: {total_missing}")
    
    for result in results:
        if result['missing_count'] > 0:
            print(f"  - {result['event_type']}: {result['missing_count']}개")


if __name__ == '__main__':
    main()
