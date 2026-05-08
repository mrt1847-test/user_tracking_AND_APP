"""
구글 시트 연동 유틸리티
JSON 파일과 구글 시트 간 양방향 동기화 기능 제공
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from gspread.http_client import HTTPClient
import requests
import logging
import traceback
import urllib3

# SSL 경고 비활성화 (회사 프록시/방화벽 환경에서 자체 서명 인증서 사용 시)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# 이벤트 타입 매핑: tracking_all JSON의 type → config JSON의 섹션 키
TRACKING_TYPE_TO_CONFIG_KEY = {
    'PV': 'pv',
    'PDP PV': 'pdp_pv',
    'PDP Buynow Click': 'pdp_buynow_click',
    'PDP ATC Click': 'pdp_atc_click',
    'PDP Gift Click': 'pdp_gift_click',
    'PDP Join Click': 'pdp_join_click',
    'PDP Rental Click': 'pdp_rental_click',
    'Module Exposure': 'module_exposure',
    'Product Exposure': 'product_exposure',
    'Product Click': 'product_click',
    'General Exposure': 'general_exposure',
    'General Click': 'general_click',
    'Product ATC Click': 'product_atc_click',
    'Product Minidetail': 'product_minidetail',
}

# 역매핑: config JSON의 섹션 키 → tracking_all JSON의 type
CONFIG_KEY_TO_TRACKING_TYPE = {v: k for k, v in TRACKING_TYPE_TO_CONFIG_KEY.items()}


class GoogleSheetsSync:
    """구글 시트 연동 클래스"""
    
    def __init__(self, spreadsheet_id: str, credentials_path: Optional[str] = None):
        """
        구글 시트 동기화 클래스 초기화
        
        Args:
            spreadsheet_id: 구글 시트 ID
            credentials_path: 서비스 계정 JSON 파일 경로 (None이면 환경변수에서 찾음)
        """
        self.spreadsheet_id = spreadsheet_id
        self.client = self._authenticate(credentials_path)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
    
    def _authenticate(self, credentials_path: Optional[str] = None) -> gspread.Client:
        """
        구글 시트 API 인증
        
        Args:
            credentials_path: 서비스 계정 JSON 파일 경로
            
        Returns:
            gspread.Client 인스턴스
        """
        if credentials_path:
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
        else:
            # 환경변수에서 경로 찾기
            env_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if env_path and Path(env_path).exists():
                creds = Credentials.from_service_account_file(
                    env_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                raise ValueError(
                    "인증 정보를 찾을 수 없습니다. "
                    "credentials_path를 제공하거나 GOOGLE_APPLICATION_CREDENTIALS 환경변수를 설정하세요."
                )
        
        # gspread 클라이언트 생성
        client = gspread.authorize(creds)
        
        # SSL 검증 비활성화 (회사 프록시/방화벽 환경 대응)
        client.http_client.session.verify = False
        
        return client
    
    def get_or_create_worksheet(self, worksheet_name: str) -> gspread.Worksheet:
        """
        워크시트 가져오기 또는 생성
        
        Args:
            worksheet_name: 워크시트 이름
            
        Returns:
            gspread.Worksheet 인스턴스
        """
        try:
            return self.spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"워크시트 '{worksheet_name}'를 생성합니다.")
            return self.spreadsheet.add_worksheet(title=worksheet_name, rows=3000, cols=10)
    
    def write_event_type_table(self, worksheet: gspread.Worksheet, 
                               event_type: str, data: List[Dict[str, str]], 
                               start_row: int = 1) -> int:
        """
        이벤트 타입별 테이블을 시트에 작성
        
        Args:
            worksheet: 워크시트 객체
            event_type: 이벤트 타입 (예: "Module Exposure")
            data: 평면화된 데이터 리스트 (각 항목은 {"path": "...", "field": "...", "value": "..."})
            start_row: 시작 행 번호 (1-based)
            
        Returns:
            다음 시작 행 번호
        """
        if not data:
            return start_row
        
        # 헤더 작성
        worksheet.update([[f'[{event_type}]', '', '']], range_name=f'A{start_row}', value_input_option='RAW')
        start_row += 1
        
        # 컬럼 헤더
        worksheet.update([['경로', '필드명', '값']], range_name=f'A{start_row}', value_input_option='RAW')
        start_row += 1
        
        # 데이터 행 작성
        rows = [[item.get('path', ''), item.get('field', ''), item.get('value', '')] for item in data]
        if rows:
            worksheet.update(rows, range_name=f'A{start_row}', value_input_option='RAW')
            start_row += len(rows)
        
        # 빈 행 추가
        start_row += 1
        
        return start_row
    
    def read_event_type_table(self, worksheet: gspread.Worksheet, 
                             event_type: str, start_row: int = 1) -> Tuple[List[Dict[str, str]], int]:
        """
        시트에서 이벤트 타입별 테이블 읽기
        
        Args:
            worksheet: 워크시트 객체
            event_type: 이벤트 타입 (예: "Module Exposure")
            start_row: 시작 검색 행 번호 (1-based)
            
        Returns:
            (데이터 리스트, 다음 시작 행 번호)
        """
        data = []
        current_row = start_row
        
        # 이벤트 타입 헤더 찾기
        all_values = worksheet.get_all_values()
        header_found = False
        search_pattern = f'[{event_type}]'
        
        # 디버깅: 검색 범위 확인
        search_range = all_values[start_row - 1:]
        print(f"    [디버깅] 헤더 '{search_pattern}' 검색 중 (시작 행: {start_row}, 검색 범위: {len(search_range)}행)")
        
        for i, row in enumerate(search_range, start=start_row):
            if row and len(row) > 0 and row[0]:
                # 디버깅: 첫 번째 컬럼 값 확인
                first_col = row[0].strip()
                if search_pattern in first_col:
                    header_found = True
                    current_row = i + 1
                    print(f"    [디버깅] 헤더 발견: 행 {i}, 값: '{first_col}'")
                    break
        
        if not header_found:
            # 디버깅: 헤더를 찾지 못한 경우 주변 행 출력
            print(f"    [디버깅] 헤더 '{search_pattern}'를 찾지 못함. 검색 범위의 첫 10개 행:")
            for i, row in enumerate(search_range[:10], start=start_row):
                first_col = row[0].strip() if row and len(row) > 0 else ''
                print(f"      행 {i}: '{first_col}'")
            return [], current_row
        
        # 컬럼 헤더 스킵
        if current_row <= len(all_values):
            current_row += 1
        
        # 데이터 행 읽기
        for i, row in enumerate(all_values[current_row - 1:], start=current_row):
            # 빈 행 확인 (3개 컬럼 모두 비어있거나 경로가 없으면)
            if not row or len(row) == 0 or (len(row) >= 1 and row[0].strip() == ''):
                # 빈 행 발견 시 종료
                return data, i + 1
            
            # 다음 이벤트 타입 헤더인지 확인
            if row[0] and row[0].startswith('[') and row[0].endswith(']'):
                return data, i
            
            # 경로가 있으면 데이터로 추가 (필드명과 값은 선택적)
            if row[0] and row[0].strip():  # 경로가 있는 경우만
                path = row[0].strip()
                field = row[1].strip() if len(row) > 1 else ''
                value = row[2].strip() if len(row) > 2 else ''
                data.append({'path': path, 'field': field, 'value': value})
        
        return data, current_row + len(data) + 1

    # 영역별 통합 시트용 (모듈 | 이벤트 타입 | 경로 | 필드명 | 값 단일 테이블)
    # Native Table(addTable) 사용: 1행은 표 헤더로 고정, 데이터만 A2:E에 기록

    AREA_HEADER = ['모듈', '이벤트 타입', '경로', '필드명', '값']
    AREA_NCOLS = 5
    TABLE_INITIAL_ROWS = 1000

    def ensure_area_table(self, worksheet: gspread.Worksheet, area_name: str) -> bool:
        """
        영역 시트에 Native Table이 없으면 addTable로 생성.
        범위 A1:E{TABLE_INITIAL_ROWS}, 5열 모두 TEXT, 헤더는 표가 관리.
        Returns:
            True if table was created, False if skipped (already exists) or failed.
        """
        sheet_id = int(worksheet.id)
        table = {
            "name": f"AreaTable_{area_name.replace('-', '_').replace(' ', '_')}",
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": self.TABLE_INITIAL_ROWS,
                "startColumnIndex": 0,
                "endColumnIndex": self.AREA_NCOLS,
            },
            "columnProperties": [
                {"columnIndex": i, "columnName": name, "columnType": "TEXT"}
                for i, name in enumerate(self.AREA_HEADER)
            ],
        }
        body = {"requests": [{"addTable": {"table": table}}]}
        try:
            self.spreadsheet.batch_update(body)
            logger.info(f"영역 '{area_name}' 시트에 표 생성 완료 (A1:E{self.TABLE_INITIAL_ROWS})")
            return True
        except Exception as e:
            logger.warning(f"표 생성 실패 (이미 있거나 오류): {e}")
            traceback.print_exc()
            return False

    def ensure_area_header(self, worksheet: gspread.Worksheet) -> None:
        """1행에 헤더(모듈|이벤트 타입|경로|필드명|값) 작성. 표 미사용 시 fallback용."""
        try:
            row1 = worksheet.row_values(1)
            if row1[: self.AREA_NCOLS] != self.AREA_HEADER:
                worksheet.update(
                    [self.AREA_HEADER],
                    range_name="A1",
                    value_input_option="RAW",
                )
        except Exception:
            worksheet.update(
                [self.AREA_HEADER],
                range_name="A1",
                value_input_option="RAW",
            )

    def clear_area_data_range(self, worksheet: gspread.Worksheet) -> None:
        """데이터 구간 A2:E만 비우기. 1행(표 헤더)은 건드리지 않음."""
        last_col = chr(64 + self.AREA_NCOLS)
        try:
            worksheet.batch_clear([f"A2:{last_col}10000"])
        except Exception as e:
            logger.warning(f"데이터 구간 clear 실패 (무시): {e}")

    def build_area_module_rows(
        self,
        module: str,
        event_type_rows: List[Tuple[str, List[Dict[str, str]]]],
    ) -> List[List[str]]:
        """
        (모듈, 이벤트 타입, 경로, 필드명, 값) 행 리스트 생성.
        write_area_module_table과 동일한 행 포맷, append 대신 한 번에 update용.
        """
        rows: List[List[str]] = []
        for event_type, flat_list in event_type_rows:
            for item in flat_list:
                path = item.get("path", "")
                field = item.get("field", "")
                value = item.get("value", "")
                rows.append([module, event_type, path, field, value])
        return rows

    def write_area_module_table(
        self,
        worksheet: gspread.Worksheet,
        module: str,
        event_type_rows: List[Tuple[str, List[Dict[str, str]]]],
    ) -> None:
        """
        영역 시트에 (모듈, 이벤트 타입, 경로, 필드명, 값) 행들을 append.
        event_type_rows: [(event_type, flat_list), ...], flat_list 항목은 path, field, value 사용.
        """
        rows: List[List[str]] = []
        for event_type, flat_list in event_type_rows:
            for item in flat_list:
                path = item.get('path', '')
                field = item.get('field', '')
                value = item.get('value', '')
                rows.append([module, event_type, path, field, value])
        if rows:
            worksheet.append_rows(rows, value_input_option='RAW')

    def list_area_modules(self, worksheet: gspread.Worksheet) -> List[str]:
        """
        영역 시트에서 고유 모듈명 목록을 반환 (1행 헤더 제외, A열 기준).
        Returns:
            비어있지 않은 고유 모듈명 리스트 (정렬됨)
        """
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) < 2:
            return []
        modules = set()
        for row in all_values[1:]:
            if row and len(row) >= 1 and row[0].strip():
                modules.add(row[0].strip())
        return sorted(modules)

    def read_area_module_data(
        self,
        worksheet: gspread.Worksheet,
        module: str,
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        영역 시트에서 모듈에 해당하는 행만 추출 후 이벤트 타입별 그룹.
        반환: {config_key: [{"path":..., "value":...}, ...]}. (필드명은 config 복원에 미사용)
        """
        all_values = worksheet.get_all_values()
        if not all_values:
            return {}
        data_rows = all_values[1:]
        by_event: Dict[str, List[Dict[str, str]]] = {}
        for row in data_rows:
            if len(row) < 4:
                continue
            mod = row[0].strip()
            event_type = row[1].strip()
            path = row[2].strip()
            # 5열(경로|필드명|값): value=row[4] / 4열(경로|값): value=row[3]
            value = row[4].strip() if len(row) >= 5 else row[3].strip()
            if mod != module:
                continue
            config_key = TRACKING_TYPE_TO_CONFIG_KEY.get(event_type)
            if not config_key:
                continue
            if config_key not in by_event:
                by_event[config_key] = []
            by_event[config_key].append({'path': path, 'value': value})
        return by_event

    def format_area_data_as_text(self, worksheet: gspread.Worksheet, last_row: int) -> None:
        """
        데이터 범위(A2 ~ E{last_row})를 텍스트 포맷으로 지정.
        표로 변환 시 '값' 열이 숫자 등으로 추론되어 mandatory/skip/JSON 등 입력이
        막히는 문제를 방지하기 위함.
        """
        if last_row < 2:
            return
        rng = f'A2:{chr(64 + self.AREA_NCOLS)}{last_row}'
        try:
            worksheet.format(rng, {'numberFormat': {'type': 'TEXT', 'pattern': '@'}})
        except Exception as e:
            logger.warning(f"영역 데이터 텍스트 포맷 적용 실패 (무시): {e}")


def flatten_json(obj: Any, parent_path: str = '', exclude_keys: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    중첩된 JSON 객체를 평면화하여 시트 행 데이터로 변환
    
    Args:
        obj: 변환할 JSON 객체
        parent_path: 부모 경로 (재귀 호출 시 사용)
        exclude_keys: 제외할 키 목록
        
    Returns:
        평면화된 데이터 리스트 [{"path": "...", "field": "...", "value": "..."}]
    """
    if exclude_keys is None:
        exclude_keys = []
    
    result = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in exclude_keys:
                continue
            
            current_path = f"{parent_path}.{key}" if parent_path else key
            current_field = key  # 필드명은 경로의 마지막 부분
            
            if isinstance(value, (dict, list)):
                result.extend(flatten_json(value, current_path, exclude_keys))
            else:
                # 리프 노드: 값 저장
                result.append({
                    'path': current_path,
                    'field': current_field,
                    'value': _serialize_value(value)
                })
    
    elif isinstance(obj, list):
        # 배열 처리
        if len(obj) == 0:
            field_name = parent_path.split('.')[-1] if parent_path else ''
            result.append({
                'path': parent_path,
                'field': field_name,
                'value': '[]'
            })
        elif len(obj) == 1 and not isinstance(obj[0], (dict, list)):
            # 단일 요소 배열: 배열 제거하고 값만 저장
            field_name = parent_path.split('.')[-1] if parent_path else ''
            result.append({
                'path': parent_path,
                'field': field_name,
                'value': _serialize_value(obj[0])
            })
        else:
            # 다중 요소 배열 또는 중첩 배열: 각 항목을 개별적으로 평면화
            # expdata.parsed 같은 특수한 경우를 위해 배열의 각 항목을 재귀적으로 처리
            for idx, item in enumerate(obj):
                item_path = f"{parent_path}[{idx}]" if parent_path else f"[{idx}]"
                result.extend(flatten_json(item, item_path, exclude_keys))
    
    else:
        # 기본 타입
        field_name = parent_path.split('.')[-1] if parent_path else ''
        result.append({
            'path': parent_path,
            'field': field_name,
            'value': _serialize_value(obj)
        })
    
    return result


def _serialize_value(value: Any) -> str:
    """값을 문자열로 직렬화"""
    if value is None:
        return ''
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        return value
    else:
        return json.dumps(value, ensure_ascii=False)


def unflatten_json(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    평면화된 행 데이터를 중첩된 JSON 객체로 재구성
    
    Args:
        rows: 평면화된 데이터 리스트 [{"path": "...", "field": "...", "value": "..."}]
        
    Returns:
        중첩된 JSON 딕셔너리
    """
    result = {}
    
    for row in rows:
        path = row.get('path', '')
        value = row.get('value', '')
        
        if not path:
            continue
        
        # 경로를 키 리스트로 분할
        keys = path.split('.')
        
        # 중첩 구조 생성
        current = result
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # 이미 다른 타입의 값이 있으면 무시
                break
            current = current[key]
        
        # 마지막 키에 값 할당
        final_key = keys[-1]
        current[final_key] = _deserialize_value(value)
    
    return result


def _deserialize_value(value: str) -> Any:
    """문자열 값을 적절한 타입으로 역직렬화 (리스트는 제외하고 나머지는 문자열)"""
    # 공란은 빈 문자열로 반환
    if value == '':
        return ''
    
    # JSON 배열 형태는 파싱해서 리스트로 반환
    if value.startswith('[') and value.endswith(']'):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    
    # 나머지는 모두 문자열로 반환 (타입 변환 없음)
    return value


def group_by_event_type(tracking_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    tracking_all JSON 데이터를 이벤트 타입별로 그룹화
    
    Args:
        tracking_data: tracking_all JSON 파일의 배열 데이터
        
    Returns:
        이벤트 타입별로 그룹화된 딕셔너리
    """
    grouped = {}
    
    for item in tracking_data:
        event_type = item.get('type', 'Unknown')
        if event_type not in grouped:
            grouped[event_type] = []
        grouped[event_type].append(item)
    
    return grouped


def extract_payload_for_config(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    tracking_all JSON의 이벤트 데이터에서 config JSON에 사용할 payload 추출
    
    Args:
        event_data: tracking_all JSON의 단일 이벤트 항목
        
    Returns:
        config JSON 형식의 payload 구조
    """
    payload = event_data.get('payload', {})
    
    # decoded_gokey가 있으면 params 구조 추출
    if 'decoded_gokey' in payload and isinstance(payload['decoded_gokey'], dict):
        decoded = payload['decoded_gokey']
        if 'params' in decoded:
            # params를 최상위로 병합하는 방식이 아니라 구조 유지
            pass
    
    return payload
