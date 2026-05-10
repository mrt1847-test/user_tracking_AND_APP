import re
import json
import time
import logging
import copy
import os
from urllib.parse import unquote, urlparse, parse_qs
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from utils.mitmproxy_collector import MitmproxyCollector
from utils.tracker_backend import TrackerBackend
from utils.h_ut_log_ingest import build_synthetic_aplus_ingest

# 로거 설정
logger = logging.getLogger(__name__)

# goodscode 추출 시 시도할 파라미터 키 목록 (중복 제거용)
_GOODSCODE_PARAM_KEYS = ('goodscode', 'goodsCode', 'goods_code', 'goodscd', 'goodsCd')
# PDP 클릭 이벤트 타입 (goodscode 없을 때 fallback 포함용)
_PDP_CLICK_TYPES = ('PDP Buynow Click', 'PDP ATC Click', 'PDP Gift Click', 'PDP Join Click', 'PDP Rental Click')


def _is_price_sentinel_one(value: Any) -> bool:
    """원가/할인가가 미노출 등으로 숫자 1만 내려오는 경우."""
    if isinstance(value, bool):
        return False
    if value == 1:
        return True
    if isinstance(value, float) and value == 1.0:
        return True
    if isinstance(value, str) and value.strip() == "1":
        return True
    return False


class TrackingLogStore:
    """
    aplus.gmarket 도메인의 POST·GET 요청을 실시간으로 감지하고 분류하는 클래스
    """
    
    def __init__(
        self,
        page: Any = None,
        source_path: Optional[str] = None,
        logs: Optional[List[Dict[str, Any]]] = None,
    ):
        """Proxy-backed tracking log store."""
        self.page = page
        self.context = getattr(page, "context", None) if page is not None else None
        self.logs: List[Dict[str, Any]] = list(logs or [])
        self.is_tracking = False
        self.source_path = Path(
            source_path
            or os.environ.get("TRACKING_PROXY_OUTPUT", "json/proxy_capture.jsonl")
        )
        self._collector = MitmproxyCollector(self.source_path)
        self._scenario_start = 0
        self._scenario_stop: Optional[int] = None
        self.domain_pattern = re.compile(r'aplus\.gmarket\.co(\.kr|m)')
        self._seen_request_ids: set[str] = set()
        self._h_ut_pipeline: List[Dict[str, Any]] = []

    def clone(self, start: Optional[int] = None, stop: Optional[int] = None) -> "TrackingLogStore":
        sliced = self._active_logs()[slice(start, stop)]
        clone = TrackingLogStore(source_path=str(self.source_path), logs=sliced)
        clone._collector = self._collector
        return clone
    def sync_from_source(self) -> None:
        for raw in self._collector.read_new_records():
            request_id = str(raw.get("request_id") or "").strip()
            if request_id and request_id in self._seen_request_ids:
                continue

            url = str(raw.get("url") or "")
            kind = str(raw.get("capture_kind") or "")
            if kind == "h_ut_upload" or "h-ut.gmarket.co.kr" in url:
                self._ingest_decoded_h_ut_capture_line(raw)
            else:
                self.record_request(
                    url=url,
                    method=str(raw.get("method") or "POST"),
                    post_data=raw.get("post_data"),
                    timestamp=float(raw.get("timestamp") or time.time()),
                )
            if request_id:
                self._seen_request_ids.add(request_id)

    def _ingest_decoded_h_ut_capture_line(self, raw: Dict[str, Any]) -> None:
        """mitm 이벤트 단위 JSONL(h_ut_upload) → aplus 형태로 record_request."""
        pd = raw.get("post_data")
        if not isinstance(pd, str) or not pd.strip():
            return
        try:
            ev = json.loads(pd)
        except json.JSONDecodeError:
            logger.debug("h-ut capture line: post_data is not JSON, skip ingest")
            return
        if not isinstance(ev, dict):
            return
        if ev.get("_capture_subtype") == "h_ut_session_prefix":
            return
        built = build_synthetic_aplus_ingest(ev)
        if not built:
            return
        surl, smethod, payload = built
        try:
            line = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            return
        upload_ts = float(raw.get("timestamp") or time.time())
        h_ut_meta = {
            "source": "mitm_h_ut_upload",
            "h_ut_upload_url": str(raw.get("url") or ""),
            "mitm_line_request_id": str(raw.get("request_id") or ""),
            "parent_request_id": str(raw.get("parent_request_id") or ""),
            "upload_timestamp": upload_ts,
            "event_index": raw.get("event_index"),
            "event_count": raw.get("event_count"),
            "pipe_event_path": ev.get("event_path"),
            "pipe_record_index": ev.get("record_index"),
        }
        self._h_ut_pipeline.append(
            {
                **h_ut_meta,
                "synthetic_aplus_url": surl,
            }
        )
        self.record_request(
            url=surl,
            method=smethod,
            post_data=line,
            timestamp=upload_ts,
            capture_meta=h_ut_meta,
        )

    def record_request(
        self,
        url: str,
        method: str,
        post_data: Optional[str],
        timestamp: Optional[float] = None,
        capture_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not url or not self.domain_pattern.search(url):
            return
        method_u = (method or '').upper()
        if method_u not in ('POST', 'GET'):
            return
        if method_u == 'GET':
            body = (post_data or '').strip()
            if body:
                parsed_payload = self._parse_payload(post_data)
            else:
                query = urlparse(url).query
                parsed_payload = self._parse_query_string(query) if query else None
        else:
            parsed_payload = self._parse_payload(post_data)
        request_type = self._classify_request_type(url, parsed_payload)
        log_entry: Dict[str, Any] = {
            'type': request_type,
            'url': url,
            'payload': parsed_payload,
            'timestamp': timestamp if timestamp is not None else time.time(),
            'method': method,
        }
        if capture_meta:
            log_entry['h_ut_capture'] = capture_meta
        self.logs.append(log_entry)
        logger.info('%s request captured: %s', request_type, url)

    def _active_logs(self) -> List[Dict[str, Any]]:
        stop = self._scenario_stop if self._scenario_stop is not None else len(self.logs)
        return self.logs[self._scenario_start:stop]
    
    def _classify_request_type(self, url: str, payload: Optional[Dict[str, Any]] = None) -> str:
        """
        URL 패턴을 분석하여 이벤트 타입을 분류
        
        Args:
            url: 요청 URL
            payload: 파싱된 payload (goodscode 확인용)
            
        Returns:
            'PV', 'PDP PV', 'Module Exposure', 'Product Exposure', 'Product Click', 'Product ATC Click',
            'General Exposure', 'General Click',
            'PDP Buynow Click', 'PDP ATC Click', 'PDP Gift Click', 'PDP Join Click', 'PDP Rental Click',
            'Product Minidetail', 또는 'Unknown'
        """
        url_lower = url.lower()
        
        # PDP/Click/Exposure 등 경로 기반 분류를 먼저 수행 (PV의 'gif' 검사가 'Gift'에 매칭되는 것 방지)
        # PDP 전용 클릭 이벤트 (Product ATC Click과 별도 이벤트)
        if '/pdp.buynow.click' in url_lower:
            return 'PDP Buynow Click'
        if '/pdp.atc.click' in url_lower:
            return 'PDP ATC Click'
        if '/pdp.gift.click' in url_lower:
            return 'PDP Gift Click'
        if '/pdp.join.click' in url_lower:
            return 'PDP Join Click'
        if '/pdp.rental.click' in url_lower:
            return 'PDP Rental Click'
        
        # Product ATC Click: SRP/LP 등 리스트에서 장바구니 클릭 (/product.atc.click만)
        if '/product.atc.click' in url_lower:
            return 'Product ATC Click'
        
        # Product Click: Product.Click.Event 패턴
        if '/product.click.event' in url_lower:
            return 'Product Click'
        
        # Product Minidetail: Product.Minidetail.Event 패턴
        if '/product.minidetail.event' in url_lower:
            return 'Product Minidetail'

        # General Exposure: General.Exposure.Event 패턴
        if '/general.exposure.event' in url_lower:
            return 'General Exposure'

        # General Click: General.Click.Event 패턴
        if '/general.click.event' in url_lower:
            return 'General Click'
        
        # Module Exposure: Module.Exposure.Event 패턴
        if '/module.exposure.event' in url_lower:
            return 'Module Exposure'
        
        # Product Exposure: Product.Exposure.Event 패턴
        if '/product.exposure.event' in url_lower:
            return 'Product Exposure'
        
        # PV: gif 요청 (경로 기반 분류 이후에 검사하여 'Gift' 등에 'gif'가 포함되어 PV로 오분류되는 것 방지)
        if 'gif' in url_lower:
            # payload에서 PDP PV인지 판단
            if payload and isinstance(payload, dict):
                # 1. _p_ispdp 필드 확인 (1이면 PDP PV)
                if '_p_ispdp' in payload:
                    ispdp = payload.get('_p_ispdp')
                    if str(ispdp) == '1':
                        return 'PDP PV'
                # 2. _p_typ 필드 확인 (pdp이면 PDP PV)
                if '_p_typ' in payload:
                    ptyp = payload.get('_p_typ', '').lower()
                    if ptyp == 'pdp':
                        return 'PDP PV'
                # 3. decoded_gokey 내부에서 _p_prod 직접 확인
                decoded_gokey = payload.get('decoded_gokey', {})
                if decoded_gokey:
                    params = decoded_gokey.get('params', {})
                    if '_p_prod' in params and params['_p_prod']:
                        return 'PDP PV'
                    def find_p_prod_recursive(obj: Any, visited: Optional[set] = None) -> bool:
                        if visited is None:
                            visited = set()
                        if isinstance(obj, (dict, list)):
                            obj_id = id(obj)
                            if obj_id in visited:
                                return False
                            visited.add(obj_id)
                        if isinstance(obj, dict):
                            if '_p_prod' in obj and obj['_p_prod']:
                                return True
                            for value in obj.values():
                                if find_p_prod_recursive(value, visited):
                                    return True
                        elif isinstance(obj, list):
                            for item in obj:
                                if find_p_prod_recursive(item, visited):
                                    return True
                        if isinstance(obj, (dict, list)):
                            visited.discard(id(obj))
                        return False
                    if find_p_prod_recursive(decoded_gokey):
                        return 'PDP PV'
                if '_p_prod' in payload and payload['_p_prod']:
                    return 'PDP PV'
            return 'PV'
        
        # 기본 Exposure (URL에 exposure 포함하지만 위 패턴에 매칭되지 않음)
        if 'exposure' in url_lower:
            return 'Exposure'
        
        # 기본 Click/Tap (URL에 click 또는 tap 포함, 위 패턴에 매칭되지 않음)
        if 'click' in url_lower or 'tap' in url_lower:
            return 'Click'
        
        return 'Unknown'
    
    def _decode_utlogmap(self, utlogmap_str: str) -> Optional[Dict[str, Any]]:
        """
        utLogMap 문자열을 디코딩하고 JSON 파싱
        
        Args:
            utlogmap_str: URL 인코딩된 utLogMap 문자열
        
        Returns:
            파싱된 JSON 객체 또는 None
        """
        try:
            # 여러 번 디코딩 시도 (다중 인코딩 가능)
            decoded = utlogmap_str
            for _ in range(3):  # 최대 3번 디코딩 시도
                try:
                    decoded = unquote(decoded)
                    # JSON 파싱 시도
                    try:
                        return json.loads(decoded)
                    except json.JSONDecodeError:
                        continue
                except:
                    break
            return None
        except Exception as e:
            logger.debug(f'utLogMap 디코딩 실패: {e}')
            return None
    
    def _decode_params_exp_or_clk(self, params_str: str) -> Dict[str, Any]:
        """
        params-exp 또는 params-clk 문자열을 디코딩하고 파싱
        
        Args:
            params_str: URL 인코딩된 params-exp/clk 문자열
        
        Returns:
            디코딩된 파라미터 딕셔너리
        """
        decoded_params = {}
        
        if not params_str:
            return decoded_params
        
        try:
            # URL 디코딩
            decoded = unquote(params_str)
            
            # &로 분리하여 각 파라미터 파싱
            for item in decoded.split('&'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    decoded_key = unquote(key)
                    decoded_value = unquote(value)
                    
                    # utLogMap은 별도로 JSON 파싱
                    if decoded_key == 'utLogMap':
                        parsed_utlogmap = self._decode_utlogmap(decoded_value)
                        decoded_params[decoded_key] = {
                            'raw': decoded_value,
                            'parsed': parsed_utlogmap
                        }
                    else:
                        decoded_params[decoded_key] = decoded_value
                        
        except Exception as e:
            logger.debug(f'params-exp/clk 디코딩 중 오류: {e}')
            decoded_params['_raw'] = params_str
        
        return decoded_params
    
    def _decode_expdata(self, expdata_str: str) -> Optional[List[Dict[str, Any]]]:
        """
        expdata JSON 문자열을 파싱하고 내부 params-exp 디코딩
        
        Args:
            expdata_str: JSON 문자열
        
        Returns:
            디코딩된 expdata 배열 또는 None
        """
        try:
            # JSON 파싱
            expdata = json.loads(expdata_str)
            
            if not isinstance(expdata, list):
                return None
            
            # 각 아이템의 exargs.params-exp 디코딩
            decoded_items = []
            for item in expdata:
                decoded_item = item.copy() if isinstance(item, dict) else {}
                
                if isinstance(item, dict) and 'exargs' in item:
                    exargs = item['exargs']
                    if isinstance(exargs, dict):
                        decoded_exargs = exargs.copy()
                        
                        # params-exp 디코딩
                        if 'params-exp' in exargs:
                            params_exp_raw = exargs['params-exp']
                            decoded_params = self._decode_params_exp_or_clk(str(params_exp_raw))
                            decoded_exargs['params-exp'] = {
                                'raw': params_exp_raw,
                                'parsed': decoded_params
                            }
                        
                        # params-clk 디코딩 (혹시 있을 경우)
                        if 'params-clk' in exargs:
                            params_clk_raw = exargs['params-clk']
                            decoded_params = self._decode_params_exp_or_clk(str(params_clk_raw))
                            decoded_exargs['params-clk'] = {
                                'raw': params_clk_raw,
                                'parsed': decoded_params
                            }
                        
                        decoded_item['exargs'] = decoded_exargs
                
                decoded_items.append(decoded_item)
            
            return decoded_items
            
        except Exception as e:
            logger.debug(f'expdata 디코딩 중 오류: {e}')
            return None
    
    def _parse_json_param(self, value: str) -> Optional[Any]:
        """
        URL 인코딩된 JSON 문자열을 디코딩 후 파싱 (clk_itm_info, utparam-url 등)
        제어 문자(\\u001e, \\u001f 등)가 포함된 문자열도 파싱되도록 strict=False 사용.
        
        Args:
            value: URL 인코딩된 JSON 문자열 (단일/다중 인코딩 가능)
            
        Returns:
            파싱된 dict/list 또는 None
        """
        if not value or not isinstance(value, str):
            return None
        decoded = value
        for _ in range(3):
            try:
                decoded = unquote(decoded)
                parsed = json.loads(decoded, strict=False)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue
        return None
    
    def _looks_like_json_string(self, value: str) -> bool:
        """문자열이 JSON 배열/객체 형태로 보이는지 확인 (불필요한 파싱 시도 방지)"""
        if not value or not isinstance(value, str):
            return False
        s = value.strip()
        if s.startswith(('[', '{')):
            return True
        try:
            u = unquote(value).strip()
            return u.startswith(('[', '{'))
        except Exception:
            return False
    
    def _decode_gokey(self, gokey: str) -> Dict[str, Any]:
        """
        gokey 문자열을 디코딩하고 파싱 (다단계 중첩 구조 지원)
        
        - expdata, params-clk, params-exp: 전용 디코더 사용 (구조가 특수함).
        - 그 외 키 중 값이 JSON 배열/객체 형태([ 또는 {로 시작)인 경우: 범용 _parse_json_param으로
          파싱하여 nested dict/list로 저장. 이후 _find_value_recursive가 _p_prod/x_object_id 등을
          경로 무관하게 재귀 탐색하므로, clk_itm_info·utparam-url 등 새 키가 추가되어도 코드 수정 불필요.
        
        Args:
            gokey: URL 인코딩된 gokey 문자열
            
        Returns:
            디코딩된 gokey 정보를 담은 딕셔너리
        """
        decoded_data = {}
        
        try:
            # 1. 전체 gokey 디코딩
            decoded_gokey = unquote(gokey)
            decoded_data['decoded_gokey'] = decoded_gokey
            
            # 2. gokey 파싱 (expdata 값 안에 &가 있으므로 단순 split('&') 시 잘림 → 괄호 균형으로 값 경계 판단)
            params = {}
            tokens = decoded_gokey.split('&')
            i = 0
            while i < len(tokens):
                item = tokens[i]
                if '=' not in item:
                    i += 1
                    continue
                key, value = item.split('=', 1)
                decoded_key = unquote(key)
                decoded_value = unquote(value)
                # expdata 값은 JSON 배열 [...] 인데, 내부에 &가 있어서 다음 토큰까지 이어붙여야 함
                if decoded_key == 'expdata' and decoded_value.strip().startswith('['):
                    while value.count('[') != value.count(']') and i + 1 < len(tokens):
                        i += 1
                        value += '&' + tokens[i]
                    decoded_value = unquote(value)
                    decoded_expdata = self._decode_expdata(decoded_value)
                    params[decoded_key] = {'raw': decoded_value, 'parsed': decoded_expdata}
                    i += 1
                    continue
                # params-clk, params-exp도 값에 & 포함 가능
                if decoded_key in ['params-clk', 'params-exp']:
                    # 값이 객체/쿼리 형태로 & 포함할 수 있음; 다음 key= 나올 때까지 묶기 (휴리스틱: = 이 나오되 키가 짧은 경우)
                    while i + 1 < len(tokens):
                        next_tok = tokens[i + 1]
                        if '=' in next_tok:
                            next_key = next_tok.split('=', 1)[0]
                            if next_key and len(unquote(next_key)) <= 20 and not next_key.strip().startswith('['):
                                break
                        value += '&' + next_tok
                        i += 1
                    decoded_value = unquote(value)
                    decoded_params = self._decode_params_exp_or_clk(decoded_value)
                    params[decoded_key] = {'raw': decoded_value, 'parsed': decoded_params}
                    i += 1
                    continue
                if isinstance(decoded_value, str) and self._looks_like_json_string(decoded_value):
                    parsed_any = self._parse_json_param(decoded_value)
                    params[decoded_key] = {'raw': decoded_value, 'parsed': parsed_any} if parsed_any is not None else decoded_value
                else:
                    params[decoded_key] = decoded_value
                i += 1
            
            decoded_data['params'] = params
            
        except Exception as e:
            logger.warning(f'gokey 디코딩 중 오류 발생: {e}')
            decoded_data['error'] = str(e)
            decoded_data['raw'] = gokey
        
        return decoded_data
    
    def _decode_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        payload에서 gokey를 디코딩하여 decoded_payload에 추가
        
        Args:
            payload: 원본 payload 딕셔너리
            
        Returns:
            디코딩된 정보가 추가된 payload 딕셔너리
        """
        if not isinstance(payload, dict):
            return payload
        
        decoded_payload = payload.copy()

        # gokey가 있으면 디코딩
        if 'gokey' in payload and payload['gokey']:
            try:
                decoded_gokey_info = self._decode_gokey(str(payload['gokey']))
                decoded_payload['decoded_gokey'] = decoded_gokey_info
                logger.debug(f'gokey 디코딩 완료: {list(decoded_gokey_info.get("params", {}).keys())}')
            except Exception as e:
                logger.warning(f'gokey 디코딩 실패: {e}')

        # Product Exposure: JSON body로 오는 경우 payload 최상위에 expdata만 있을 수 있음 → decoded_gokey.params에 보정
        decoded_gokey = decoded_payload.get('decoded_gokey') or {}
        params = decoded_gokey.get('params') or {}
        if not params.get('expdata') and payload.get('expdata'):
            raw_exp = payload['expdata']
            if isinstance(raw_exp, str):
                parsed_exp = self._decode_expdata(raw_exp)
            elif isinstance(raw_exp, list):
                parsed_exp = raw_exp  # 이미 배열로 파싱된 경우 그대로 사용
            else:
                parsed_exp = None
            if parsed_exp is not None:
                if not isinstance(decoded_payload.get('decoded_gokey'), dict):
                    decoded_payload['decoded_gokey'] = decoded_gokey if decoded_gokey else {}
                decoded_payload['decoded_gokey'].setdefault('params', {})['expdata'] = {
                    'raw': raw_exp if isinstance(raw_exp, str) else json.dumps(raw_exp),
                    'parsed': parsed_exp,
                }
                logger.debug('Product Exposure: payload.expdata를 decoded_gokey.params.expdata로 보정함')

        return decoded_payload
    
    def _parse_query_string(self, query_string: str) -> Dict[str, Any]:
        """
        쿼리 문자열을 파싱하고 디코딩
        
        Args:
            query_string: URL 인코딩된 쿼리 문자열
            
        Returns:
            파싱된 딕셔너리
        """
        parsed_params = {}
        
        if not query_string:
            return parsed_params
        
        try:
            # &로 분리하여 각 파라미터 파싱
            for item in query_string.split('&'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    decoded_key = unquote(key)
                    decoded_value = unquote(value)
                    
                    # gokey가 있으면 디코딩
                    if decoded_key == 'gokey' and decoded_value:
                        decoded_gokey_info = self._decode_gokey(decoded_value)
                        parsed_params[decoded_key] = decoded_value
                        parsed_params['decoded_gokey'] = decoded_gokey_info
                    else:
                        parsed_params[decoded_key] = decoded_value
        except Exception as e:
            logger.debug(f'쿼리 문자열 파싱 중 오류: {e}')
            parsed_params['_raw'] = query_string
        
        return parsed_params
    
    def _parse_payload(self, post_data: Optional[str]) -> Any:
        """
        POST Body 데이터를 파싱
        
        Args:
            post_data: POST Body 문자열
            
        Returns:
            파싱된 데이터 (dict 또는 str)
        """
        if not post_data:
            return None
        
        # JSON 파싱 시도
        try:
            parsed = json.loads(post_data)
            # dict인 경우 gokey 디코딩 수행
            if isinstance(parsed, dict):
                return self._decode_payload(parsed)
            return parsed
        except (json.JSONDecodeError, TypeError):
            # JSON이 아니면 쿼리 문자열 파싱 시도
            try:
                # 쿼리 문자열 형태인지 확인 (& 또는 = 포함)
                if '&' in post_data or '=' in post_data:
                    return self._parse_query_string(post_data)
            except Exception as e:
                logger.debug(f'쿼리 문자열 파싱 실패: {e}')
            
            # 모든 파싱이 실패하면 raw string 반환
            return post_data
    
    def _on_request(self, request: Any):
        """Backward-compatible request ingestion helper."""
        if not self.is_tracking:
            return
        try:
            url = request.url if isinstance(getattr(request, 'url', None), str) else request.url()
            method = request.method if isinstance(getattr(request, 'method', None), str) else request.method()
            post_data = request.post_data() if callable(getattr(request, 'post_data', None)) else getattr(request, 'post_data', None)
            self.record_request(url=url, method=method, post_data=post_data)
        except Exception as e:
            logger.error('request handling failed: %s', e, exc_info=True)

    def start(self):
        """Mark the current end of the proxy-backed log stream as the scenario start."""
        self.sync_from_source()
        self.is_tracking = True
        self._scenario_start = len(self.logs)
        self._scenario_stop = None
        self._h_ut_pipeline.clear()
        logger.info('tracking start marker set at index=%d', self._scenario_start)
    def _on_new_page(self, page: Any):
        del page
        return

    def stop(self):
        """Freeze the scenario stop marker without tearing down the shared proxy runtime."""
        if not self.is_tracking:
            logger.warning('tracking was not active when stop() was called')
            return
        self.sync_from_source()
        self.is_tracking = False
        self._scenario_stop = len(self.logs)
        logger.info('tracking stop marker set at index=%d', self._scenario_stop)
    def get_logs(self, request_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return logs captured within the scenario marker range."""
        self.sync_from_source()
        active_logs = self._active_logs()
        if request_type:
            return [log for log in active_logs if log['type'] == request_type]
        return active_logs.copy()

    def get_pv_logs(self) -> List[Dict[str, Any]]:
        """
        PV 타입 로그만 반환 (PDP PV 제외)
        
        Returns:
            PV 로그 리스트
        """
        return self.get_logs('PV')
    
    def get_pdp_pv_logs(self) -> List[Dict[str, Any]]:
        """
        PDP PV 타입 로그만 반환 (goodscode가 있는 PV)
        
        Returns:
            PDP PV 로그 리스트
        """
        return self.get_logs('PDP PV')
    
    def get_exposure_logs(self) -> List[Dict[str, Any]]:
        """
        Exposure 타입 로그만 반환
        
        Returns:
            Exposure 로그 리스트
        """
        return self.get_logs('Exposure')
    
    def get_click_logs(self) -> List[Dict[str, Any]]:
        """
        Click 타입 로그만 반환
        
        Returns:
            Click 로그 리스트
        """
        return self.get_logs('Click')
    
    def _find_value_recursive(self, obj: Any, target_keys: List[str], visited: Optional[set] = None) -> Optional[str]:
        """
        재귀적으로 딕셔너리/리스트를 탐색하여 target_keys 중 하나를 찾음
        순환 참조 방지를 위해 visited set 사용
        
        Args:
            obj: 탐색할 객체 (dict, list, 또는 기타)
            target_keys: 찾을 키 목록 (우선순위 순서)
            visited: 방문한 객체 ID 집합 (순환 참조 방지)
        
        Returns:
            찾은 값의 문자열 변환 또는 None
        """
        if visited is None:
            visited = set()
        
        # 순환 참조 방지 (dict와 list만 체크)
        if isinstance(obj, (dict, list)):
            obj_id = id(obj)
            if obj_id in visited:
                return None
            visited.add(obj_id)
        
        # 딕셔너리인 경우
        if isinstance(obj, dict):
            # 우선순위에 따라 키 확인 (_p_prod 우선)
            for key in target_keys:
                if key in obj:
                    value = obj[key]
                    if value:
                        return str(value)
            
            # 'parsed' 키가 있으면 우선적으로 탐색 (디코딩된 데이터 구조)
            if 'parsed' in obj and isinstance(obj['parsed'], (dict, list)):
                result = self._find_value_recursive(obj['parsed'], target_keys, visited)
                if result:
                    return result
            
            # 모든 값에 대해 재귀 탐색
            for value in obj.values():
                result = self._find_value_recursive(value, target_keys, visited)
                if result:
                    return result
        
        # 리스트인 경우
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_value_recursive(item, target_keys, visited)
                if result:
                    return result
        
        # 방문 기록 제거 (재귀 종료 시)
        if isinstance(obj, (dict, list)):
            visited.discard(id(obj))
        
        return None
    
    def _get_goodscode_from_url_query(self, url_str: str, decode_first: bool = False) -> Optional[str]:
        """URL(또는 URL 인코딩 문자열)의 쿼리에서 goodscode 파라미터 추출"""
        if not url_str:
            return None
        try:
            s = unquote(url_str) if decode_first else url_str
            qs = parse_qs(urlparse(s).query)
            for key in _GOODSCODE_PARAM_KEYS:
                if key in qs and qs[key]:
                    val = qs[key][0] if isinstance(qs[key], list) else qs[key]
                    if val:
                        return str(val)
        except Exception:
            pass
        return None
    
    def _extract_goodscode_from_log(self, log: Dict[str, Any]) -> Optional[str]:
        """
        로그에서 goodscode 추출 (다단계 중첩 구조 지원)
        - decoded_gokey 내부는 재귀 탐색으로 _p_prod/x_object_id 자동 발견
        - payload._p_url, log.url 쿼리에서도 추출
        
        Args:
            log: 로그 딕셔너리
        
        Returns:
            추출된 goodscode (_p_prod 우선, 없으면 x_object_id) 또는 None
        """
        
        payload = log.get('payload')
        
        if not isinstance(payload, dict):
            return None
        
        # 1. payload 최상위에서 x_object_id 확인
        if 'x_object_id' in payload:
            value = payload['x_object_id']
            if value:
                return str(value)
        
        # 1.5. payload 최상위에서 _p_prod 확인 (PDP PV 등 m.gif 쿼리스트링 파싱 결과)
        if '_p_prod' in payload and payload['_p_prod']:
            return str(payload['_p_prod'])
        
        # 2. payload에서 직접 확인 (다양한 키 이름 시도)
        for key in _GOODSCODE_PARAM_KEYS:
            if key in payload and payload[key]:
                return str(payload[key])
        
        # 3. decoded_gokey 내부를 재귀적으로 탐색 (_p_prod 우선, 없으면 x_object_id)
        decoded_gokey = payload.get('decoded_gokey', {})
        if decoded_gokey:
            result = self._find_value_recursive(decoded_gokey, ['_p_prod'])
            if result:
                return result
            result = self._find_value_recursive(decoded_gokey, ['x_object_id'])
            if result:
                return result
        
        # 4. decoded_gokey.params에서 직접 확인
        params = decoded_gokey.get('params', {})
        for key in _GOODSCODE_PARAM_KEYS:
            if key in params and params[key]:
                return str(params[key])
        
        # 5. payload._p_url 또는 log.url 쿼리에서 goodscode 추출
        res = self._get_goodscode_from_url_query(payload.get('_p_url') or '', decode_first=True)
        if res:
            return res
        res = self._get_goodscode_from_url_query(log.get('url') or '')
        if res:
            return res
        return None
    
    def _extract_gmkt_area_code_from_log(self, log: Dict[str, Any]) -> Optional[str]:
        """
        로그에서 gmkt_area_code 추출
        
        Args:
            log: 로그 딕셔너리
        
        Returns:
            추출된 gmkt_area_code 또는 None
        """
        payload = log.get('payload', {})
        decoded_gokey = payload.get('decoded_gokey', {})
        params = decoded_gokey.get('params', {})
        
        # Product Exposure: expdata.parsed 배열의 각 항목에서 확인
        if 'expdata' in params:
            expdata = params['expdata']
            if isinstance(expdata, dict) and 'parsed' in expdata:
                parsed_list = expdata['parsed']
                if isinstance(parsed_list, list) and len(parsed_list) > 0:
                    # 첫 번째 항목의 params-exp.parsed.gmkt_area_code 확인
                    first_item = parsed_list[0]
                    if isinstance(first_item, dict) and 'exargs' in first_item:
                        exargs = first_item['exargs']
                        if isinstance(exargs, dict) and 'params-exp' in exargs:
                            params_exp = exargs['params-exp']
                            if isinstance(params_exp, dict) and 'parsed' in params_exp:
                                parsed = params_exp['parsed']
                                if isinstance(parsed, dict) and 'gmkt_area_code' in parsed:
                                    return str(parsed['gmkt_area_code'])
        
        # Product Click: params-clk.parsed.gmkt_area_code 확인
        if 'params-clk' in params:
            params_clk = params['params-clk']
            if isinstance(params_clk, dict) and 'parsed' in params_clk:
                parsed = params_clk['parsed']
                if isinstance(parsed, dict) and 'gmkt_area_code' in parsed:
                    return str(parsed['gmkt_area_code'])
        
        # Module Exposure: params-exp.parsed.gmkt_area_code 확인
        if 'params-exp' in params:
            params_exp = params['params-exp']
            if isinstance(params_exp, dict) and 'parsed' in params_exp:
                parsed = params_exp['parsed']
                if isinstance(parsed, dict) and 'gmkt_area_code' in parsed:
                    return str(parsed['gmkt_area_code'])
        
        return None
    
    def get_logs_by_goodscode(self, goodscode: str, request_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 로그 필터링
        
        Args:
            goodscode: 상품 번호
            request_type: 필터링할 타입 ('PV', 'Exposure', 'Click', 'Unknown'). None이면 모든 타입
        
        Returns:
            해당 goodscode와 일치하는 로그 리스트
        """
        filtered_logs = []
        
        self.sync_from_source()
        for log in self._active_logs():
            # 타입 필터링
            if request_type and log.get('type') != request_type:
                continue
            
            # Product Exposure의 경우: expdata.parsed 배열의 모든 항목을 재귀적으로 확인
            if request_type == 'Product Exposure':
                payload = log.get('payload', {})
                parsed_list = None
                decoded_gokey = payload.get('decoded_gokey', {}) if isinstance(payload, dict) else {}
                if isinstance(decoded_gokey, dict):
                    params = decoded_gokey.get('params', {})
                    if isinstance(params, dict):
                        expdata = params.get('expdata', {})
                        if isinstance(expdata, dict) and 'parsed' in expdata:
                            parsed_list = expdata.get('parsed', [])
                # 자동화 등에서 payload 최상위 expdata로만 올 수 있음 (decoded_gokey.params에 없음)
                if not parsed_list and isinstance(payload, dict) and payload.get('expdata'):
                    raw_exp = payload['expdata']
                    if isinstance(raw_exp, str):
                        parsed_list = self._decode_expdata(raw_exp) or []
                    elif isinstance(raw_exp, list):
                        parsed_list = raw_exp
                if isinstance(parsed_list, list):
                    found = False
                    for item in parsed_list:
                        item_goodscode = self._find_value_recursive(item, ['_p_prod'])
                        if not item_goodscode:
                            item_goodscode = self._find_value_recursive(item, ['x_object_id'])
                        if item_goodscode and str(item_goodscode) == str(goodscode):
                            found = True
                            break
                    if found:
                        filtered_logs.append(log)
                    continue
            
            # 그 외의 경우: 기존 방식으로 goodscode 추출 및 비교
            log_goodscode = self._extract_goodscode_from_log(log)
            if log_goodscode and str(log_goodscode) == str(goodscode):
                filtered_logs.append(log)
            # PDP 클릭 이벤트는 payload에 gokey/goodscode가 없을 수 있음. 단일 goodscode 검증 시 해당 로그 포함
            elif request_type in _PDP_CLICK_TYPES and log_goodscode is None:
                filtered_logs.append(log)
        
        return filtered_logs
    
    def get_pv_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 PV 로그만 반환 (PDP PV 포함)
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 PV/PDP PV 로그 리스트
        """
        # PV와 PDP PV 모두에서 goodscode로 필터링
        pv_logs = self.get_logs_by_goodscode(goodscode, 'PV')
        pdp_pv_logs = self.get_logs_by_goodscode(goodscode, 'PDP PV')
        return pv_logs + pdp_pv_logs
    
    def get_pdp_pv_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 PDP PV 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 PDP PV 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'PDP PV')
    
    def get_exposure_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Exposure 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Exposure 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Exposure')
    
    def get_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Click 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Click 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Click')
    
    def get_module_exposure_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Module Exposure 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Module Exposure 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Module Exposure')
    
    def _find_spm_recursive(self, obj: Any, visited: Optional[set] = None) -> Optional[str]:
        """
        재귀적으로 딕셔너리/리스트를 탐색하여 'spm' 키를 찾음
        순환 참조 방지를 위해 visited set 사용
        
        Args:
            obj: 탐색할 객체 (dict, list, 또는 기타)
            visited: 방문한 객체 ID 집합 (순환 참조 방지)
        
        Returns:
            찾은 spm 값의 문자열 변환 또는 None
        """
        if visited is None:
            visited = set()
        
        # 순환 참조 방지 (dict와 list만 체크)
        if isinstance(obj, (dict, list)):
            obj_id = id(obj)
            if obj_id in visited:
                return None
            visited.add(obj_id)
        
        # 딕셔너리인 경우
        if isinstance(obj, dict):
            # 'spm' 키가 있고 값이 있으면 반환
            if 'spm' in obj and obj['spm']:
                return str(obj['spm'])
            
            # 모든 값에 대해 재귀적으로 탐색
            for value in obj.values():
                result = self._find_spm_recursive(value, visited)
                if result is not None:
                    return result
        
        # 리스트인 경우
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_spm_recursive(item, visited)
                if result is not None:
                    return result
        
        # 순환 참조 방지를 위해 방문 기록 제거
        if isinstance(obj, (dict, list)):
            visited.discard(id(obj))
        
        return None
    
    def _extract_spm_from_log(self, log: Dict[str, Any]) -> Optional[str]:
        """
        로그에서 spm 값 추출 (우선순위 기반 탐색)
        
        Module Exposure의 경우 decoded_gokey.params.spm을 우선적으로 확인하고,
        없으면 재귀적으로 탐색
        
        Args:
            log: 로그 딕셔너리
        
        Returns:
            추출된 spm 값 또는 None
        """
        payload = log.get('payload')
        
        if not isinstance(payload, dict):
            return None
        
        # Module Exposure의 경우: decoded_gokey.params.spm 우선 확인
        decoded_gokey = payload.get('decoded_gokey', {})
        if isinstance(decoded_gokey, dict):
            params = decoded_gokey.get('params', {})
            if isinstance(params, dict) and 'spm' in params and params['spm']:
                return str(params['spm'])
        
        # 우선 경로에서 못 찾았으면 재귀적으로 탐색
        return self._find_spm_recursive(payload)
    
    @staticmethod
    def _normalize_spm_for_banner_match(spm: str) -> str:
        """
        SPM 문자열에 ``banner``(대소문자 무관)가 포함되면, 문자열 맨끝의 연속 숫자를 제거한다.
        ``dtab0_banner40`` ↔ ``dtab0_banner`` / ``dtab0_banner19`` 비교 시 동일 슬롯으로 본다.
        """
        if not spm or not isinstance(spm, str):
            return spm if isinstance(spm, str) else ''
        if 'banner' not in spm.lower():
            return spm
        return re.sub(r'\d+$', '', spm)
    
    def _check_spm_match(self, log_spm: str, target_spm: str) -> bool:
        """
        두 spm 값이 매칭되는지 확인 (양방향 접두사 매칭)
        
        ``banner`` 이 포함된 SPM은 맨끝 연속 숫자를 제거한 뒤 비교한다
        (예: ``...dtab0_banner40`` 과 ``...dtab0_banner`` 는 매칭).
        
        Args:
            log_spm: 로그에서 추출한 spm 값
            target_spm: 비교 대상 spm 값
        
        Returns:
            매칭되면 True, 아니면 False
        
        예시:
            - "gmktpc.searchlist.cpc"와 "gmktpc.searchlist.cpc.d0_0" -> True
            - "gmktpc.searchlist.cpc"와 "gmktpc.searchlist.prime" -> False
            - "gmktpc.searchlist.prime"와 "gmktpc.searchlist.cpc" -> False
        """
        if not log_spm or not target_spm:
            return False
        
        log_spm = self._normalize_spm_for_banner_match(str(log_spm))
        target_spm = self._normalize_spm_for_banner_match(str(target_spm))
        if not log_spm or not target_spm:
            return False
        
        # 정확히 일치
        if log_spm == target_spm:
            return True
        
        # log_spm이 "target_spm."으로 시작하면 매칭 (예: target_spm="gmktpc.searchlist.cpc", log_spm="gmktpc.searchlist.cpc.d0_0")
        if log_spm.startswith(target_spm + '.'):
            return True
        
        # target_spm이 "log_spm."으로 시작하면 매칭 (예: target_spm="gmktpc.searchlist.prime.d0_0", log_spm="gmktpc.searchlist.prime")
        if target_spm.startswith(log_spm + '.'):
            return True
        
        return False
    
    def get_module_exposure_logs_by_spm(self, spm: str) -> List[Dict[str, Any]]:
        """
        spm 기준으로 Module Exposure 로그만 반환
        
        Args:
            spm: SPM 값 (예: "gmktpc.searchlist.cpc")
        
        Returns:
            해당 spm의 Module Exposure 로그 리스트
        """
        filtered_logs = []
        
        # Module Exposure 로그만 필터링
        module_exposure_logs = self.get_logs('Module Exposure')
        
        for log in module_exposure_logs:
            log_spm = self._extract_spm_from_log(log)
            # spm이 정확히 일치하거나, 서로가 접두사 관계인지 확인
            if log_spm:
                if self._check_spm_match(log_spm, spm):
                    filtered_logs.append(log)
                else:
                    # 디버깅: 매칭되지 않은 로그 정보
                    logger.debug(f"SPM 필터링 불일치: log_spm='{log_spm}', target_spm='{spm}'")
            else:
                logger.debug(f"SPM 추출 실패: 로그에서 spm을 찾을 수 없음")
        
        logger.info(f"SPM '{spm}'로 필터링된 Module Exposure 로그: {len(filtered_logs)}/{len(module_exposure_logs)}개")
        
        return filtered_logs
    
    def _extract_spm_from_product_exposure_item(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Product Exposure의 expdata.parsed 배열 항목에서 spm 추출 (재귀적 탐색)
        
        Module Exposure와 동일하게 우선 최상위에서 직접 확인하고,
        없으면 재귀적으로 탐색하여 spm 필드를 찾음
        
        Args:
            item: expdata.parsed 배열의 항목
        
        Returns:
            추출된 spm 값 또는 None
        """
        if not isinstance(item, dict):
            return None
        
        # 우선 최상위에서 직접 spm 필드 확인
        if 'spm' in item and item['spm']:
            return str(item['spm'])
        
        # 없으면 재귀적으로 탐색 (Module Exposure와 동일한 방식)
        return self._find_spm_recursive(item)
    
    def get_product_exposure_logs_by_goodscode(self, goodscode: str, spm: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Product Exposure 로그만 반환
        spm이 제공되면 **SPM 우선** 필터: 전체 Product Exposure 로그에서 exargs 단위로 SPM 매칭 후 goodscode 매칭
        
        Args:
            goodscode: 상품 번호
            spm: SPM 값 (선택적, 예: "gmktpc.searchlist.cpc")
        
        Returns:
            해당 goodscode의 Product Exposure 로그 리스트
        """
        # spm이 없으면 goodscode로만 필터링 (기존 방식)
        if not spm:
            logs = self.get_logs_by_goodscode(goodscode, 'Product Exposure')
            logger.info(f"Product Exposure 로그 (goodscode 기준): {len(logs)}개")
            return logs

        # spm이 있으면 SPM 우선: 전체 Product Exposure 로그를 먼저 수집한 뒤, exargs 단위로 SPM → goodscode 필터
        # (한 요청에 여러 SPM이 섞여 있어 goodscode 선필터 시 로그를 못 찾을 수 있음)
        logs = self.get_logs('Product Exposure')
        filtered_logs = []
        total_items = 0
        matched_items = 0

        for log in logs:
            filtered_log = copy.deepcopy(log)
            payload = filtered_log.get('payload', {})
            if isinstance(payload, dict) and payload.get('_native_h_ut'):
                h_ut = payload.get('h_ut', {})
                kv = h_ut.get('kv', {}) if isinstance(h_ut, dict) else {}
                utlogmap = h_ut.get('utLogMap', {}) if isinstance(h_ut, dict) else {}
                parsed_utlogmap = utlogmap.get('parsed', {}) if isinstance(utlogmap, dict) else {}
                item_spm = kv.get('spm') if isinstance(kv, dict) else None
                item_goodscode = None
                if isinstance(kv, dict):
                    item_goodscode = kv.get('_p_prod')
                if not item_goodscode and isinstance(parsed_utlogmap, dict):
                    item_goodscode = parsed_utlogmap.get('x_object_id')
                total_items += 1
                if (
                    item_spm
                    and self._check_spm_match(str(item_spm), spm)
                    and item_goodscode
                    and str(item_goodscode) == str(goodscode)
                ):
                    filtered_logs.append(filtered_log)
                    matched_items += 1
                continue

            decoded_gokey = payload.get('decoded_gokey', {}) or {}
            params = decoded_gokey.get('params', {}) if isinstance(decoded_gokey, dict) else {}
            expdata = params.get('expdata', {}) if isinstance(params, dict) else {}
            # 자동화 등에서 payload 최상위 expdata로만 올 수 있음 → decoded_gokey.params에 보정
            if (not expdata or not expdata.get('parsed')) and isinstance(payload, dict) and payload.get('expdata'):
                raw_exp = payload['expdata']
                if isinstance(raw_exp, str):
                    parsed_fallback = self._decode_expdata(raw_exp) or []
                elif isinstance(raw_exp, list):
                    parsed_fallback = raw_exp
                else:
                    parsed_fallback = []
                if not isinstance(decoded_gokey, dict):
                    payload['decoded_gokey'] = {}
                    decoded_gokey = payload['decoded_gokey']
                decoded_gokey.setdefault('params', {})['expdata'] = {
                    'raw': raw_exp if isinstance(raw_exp, str) else json.dumps(raw_exp),
                    'parsed': parsed_fallback,
                }
                expdata = decoded_gokey['params']['expdata']

            filtered_items = []
            if isinstance(expdata, dict) and 'parsed' in expdata:
                parsed_list = expdata.get('parsed', [])
                if isinstance(parsed_list, list):
                    for item in parsed_list:
                        total_items += 1

                        # 1) SPM 우선: 타겟 SPM과 매칭되지 않으면 제외
                        item_spm = self._extract_spm_from_product_exposure_item(item)
                        if not item_spm or not self._check_spm_match(item_spm, spm):
                            continue

                        # 2) exargs에서 상품번호(goodscode) 추출
                        item_goodscode = None
                        if isinstance(item, dict) and 'exargs' in item:
                            exargs = item.get('exargs', {})
                            if isinstance(exargs, dict) and 'params-exp' in exargs:
                                params_exp = exargs.get('params-exp', {})
                                if isinstance(params_exp, dict) and 'parsed' in params_exp:
                                    parsed = params_exp.get('parsed', {})
                                    if isinstance(parsed, dict):
                                        if '_p_prod' in parsed:
                                            item_goodscode = str(parsed['_p_prod'])
                                        elif 'utLogMap' in parsed:
                                            utlogmap = parsed.get('utLogMap', {})
                                            if isinstance(utlogmap, dict) and 'parsed' in utlogmap:
                                                utlogmap_parsed = utlogmap.get('parsed', {})
                                                if isinstance(utlogmap_parsed, dict) and 'x_object_id' in utlogmap_parsed:
                                                    item_goodscode = str(utlogmap_parsed['x_object_id'])
                                            elif isinstance(utlogmap, dict) and 'x_object_id' in utlogmap:
                                                item_goodscode = str(utlogmap['x_object_id'])

                        # 3) goodscode가 타겟과 일치하는 항목만 포함 (SPM 이미 매칭됨)
                        if item_goodscode == goodscode:
                            filtered_items.append(item)
                            matched_items += 1
                            logger.debug(f"Product Exposure 매칭: spm={item_spm}, goodscode={item_goodscode}, target_spm={spm}")

            if filtered_items:
                expdata['parsed'] = filtered_items
                filtered_logs.append(filtered_log)
            else:
                logger.debug(f"Product Exposure 로그 제외: goodscode={goodscode}, target_spm={spm}와 매칭되는 exargs 없음")

        logger.info(
            f"SPM '{spm}'로 필터링된 Product Exposure 로그: {len(filtered_logs)}/{len(logs)}개 (매칭된 항목: {matched_items}/{total_items}개)"
        )
        return filtered_logs

    def get_product_exposure_logs_by_spm(self, spm: str) -> List[Dict[str, Any]]:
        """
        SPM만 기준으로 Product Exposure 로그 반환 (상품번호 필터 없음).
        expdata.parsed에서 target SPM과 매칭되는 exargs만 남긴 로그 리스트를 반환.

        Args:
            spm: SPM 값 (예: "gmktm.pdp.pdpjfy")

        Returns:
            해당 SPM에 해당하는 Product Exposure 로그 리스트
        """
        logs = self.get_logs('Product Exposure')
        filtered_logs = []
        total_items = 0
        matched_items = 0

        for log in logs:
            filtered_log = copy.deepcopy(log)
            payload = filtered_log.get('payload', {})
            if isinstance(payload, dict) and payload.get('_native_h_ut'):
                h_ut = payload.get('h_ut', {})
                kv = h_ut.get('kv', {}) if isinstance(h_ut, dict) else {}
                item_spm = kv.get('spm') if isinstance(kv, dict) else None
                total_items += 1
                if item_spm and self._check_spm_match(str(item_spm), spm):
                    filtered_logs.append(filtered_log)
                    matched_items += 1
                continue

            decoded_gokey = payload.get('decoded_gokey', {}) or {}
            params = decoded_gokey.get('params', {}) if isinstance(decoded_gokey, dict) else {}
            expdata = params.get('expdata', {}) if isinstance(params, dict) else {}
            if (not expdata or not expdata.get('parsed')) and isinstance(payload, dict) and payload.get('expdata'):
                raw_exp = payload['expdata']
                if isinstance(raw_exp, str):
                    parsed_fallback = self._decode_expdata(raw_exp) or []
                elif isinstance(raw_exp, list):
                    parsed_fallback = raw_exp
                else:
                    parsed_fallback = []
                if not isinstance(decoded_gokey, dict):
                    payload['decoded_gokey'] = {}
                    decoded_gokey = payload['decoded_gokey']
                decoded_gokey.setdefault('params', {})['expdata'] = {
                    'raw': raw_exp if isinstance(raw_exp, str) else json.dumps(raw_exp),
                    'parsed': parsed_fallback,
                }
                expdata = decoded_gokey['params']['expdata']

            filtered_items = []
            if isinstance(expdata, dict) and 'parsed' in expdata:
                parsed_list = expdata.get('parsed', [])
                if isinstance(parsed_list, list):
                    for item in parsed_list:
                        total_items += 1
                        item_spm = self._extract_spm_from_product_exposure_item(item)
                        if not item_spm or not self._check_spm_match(item_spm, spm):
                            continue
                        filtered_items.append(item)
                        matched_items += 1
                        logger.debug(f"Product Exposure SPM 매칭: spm={item_spm}, target_spm={spm}")

            if filtered_items:
                expdata['parsed'] = filtered_items
                filtered_logs.append(filtered_log)
            else:
                logger.debug(f"Product Exposure 로그 제외: target_spm={spm}와 매칭되는 exargs 없음")

        logger.info(
            f"SPM '{spm}'만으로 필터링된 Product Exposure 로그: {len(filtered_logs)}/{len(logs)}개 (매칭된 항목: {matched_items}/{total_items}개)"
        )
        return filtered_logs

    def get_product_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Product Click 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Product Click 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Product Click')

    def get_general_exposure_logs_by_spm(self, spm: str) -> List[Dict[str, Any]]:
        """
        spm 기준으로 General Exposure 로그만 반환

        Args:
            spm: SPM 값

        Returns:
            해당 spm의 General Exposure 로그 리스트
        """
        filtered_logs = []
        logs = self.get_logs('General Exposure')
        for log in logs:
            log_spm = self._extract_spm_from_log(log)
            if log_spm and self._check_spm_match(log_spm, spm):
                filtered_logs.append(log)
        logger.info(f"SPM '{spm}'로 필터링된 General Exposure 로그: {len(filtered_logs)}/{len(logs)}개")
        return filtered_logs

    def get_general_click_logs_by_spm(self, spm: str) -> List[Dict[str, Any]]:
        """
        spm 기준으로 General Click 로그만 반환

        Args:
            spm: SPM 값

        Returns:
            해당 spm의 General Click 로그 리스트
        """
        filtered_logs = []
        logs = self.get_logs('General Click')
        for log in logs:
            log_spm = self._extract_spm_from_log(log)
            if log_spm and self._check_spm_match(log_spm, spm):
                filtered_logs.append(log)
        logger.info(f"SPM '{spm}'로 필터링된 General Click 로그: {len(filtered_logs)}/{len(logs)}개")
        return filtered_logs

    def get_product_atc_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Product ATC Click 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Product ATC Click 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Product ATC Click')
    
    def get_product_minidetail_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """
        goodscode 기준으로 Product Minidetail 로그만 반환
        
        Args:
            goodscode: 상품 번호
        
        Returns:
            해당 goodscode의 Product Minidetail 로그 리스트
        """
        return self.get_logs_by_goodscode(goodscode, 'Product Minidetail')
    
    def get_pdp_buynow_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """goodscode 기준으로 PDP Buynow Click 로그만 반환"""
        return self.get_logs_by_goodscode(goodscode, 'PDP Buynow Click')
    
    def get_pdp_atc_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """goodscode 기준으로 PDP ATC Click 로그만 반환"""
        return self.get_logs_by_goodscode(goodscode, 'PDP ATC Click')
    
    def get_pdp_gift_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """goodscode 기준으로 PDP Gift Click 로그만 반환"""
        return self.get_logs_by_goodscode(goodscode, 'PDP Gift Click')
    
    def get_pdp_join_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """goodscode 기준으로 PDP Join Click 로그만 반환"""
        return self.get_logs_by_goodscode(goodscode, 'PDP Join Click')
    
    def get_pdp_rental_click_logs_by_goodscode(self, goodscode: str) -> List[Dict[str, Any]]:
        """goodscode 기준으로 PDP Rental Click 로그만 반환"""
        return self.get_logs_by_goodscode(goodscode, 'PDP Rental Click')
    
    def get_decoded_gokey_params(self, log: Dict[str, Any], param_key: Optional[str] = None) -> Dict[str, Any]:
        """
        로그에서 디코딩된 gokey 파라미터 조회
        
        Args:
            log: 로그 딕셔너리
            param_key: 특정 파라미터 키 (예: 'params-clk', 'params-exp'). None이면 전체 파라미터 반환
        
        Returns:
            디코딩된 파라미터 딕셔너리
        """
        payload = log.get('payload')
        
        if not isinstance(payload, dict):
            return {}
        
        decoded_gokey = payload.get('decoded_gokey', {})
        params = decoded_gokey.get('params', {})
        
        if param_key:
            return params.get(param_key, {})
        
        return params
    
    def _validate_payload_legacy(self, log: Dict[str, Any], expected_data: Dict[str, Any], goodscode: Optional[str] = None, event_type: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        로그의 payload 정합성 검증 (재귀적 탐색 방식)
        
        Args:
            log: 검증할 로그 딕셔너리
            expected_data: 기대하는 데이터 (키-값 쌍)
                          - 키는 필드명만 사용 (예: '_p_prod', 'channel_code', 'query')
                          - validate_payload에서 재귀적으로 찾음
            goodscode: 상품 번호 (Product Exposure의 경우 expdata.parsed 배열에서 필터링용)
            event_type: 이벤트 타입 ('Product Exposure', 'Product Click' 등)
        
        Returns:
            (검증 성공 여부, 통과한 필드 정보 딕셔너리) 튜플
            - 검증 성공 시: (True, {필드명: {"expected": 기대값, "actual": 실제값}})
            - 검증 실패 시: AssertionError 발생
        
        Raises:
            AssertionError: 검증 실패 시
        """
        def find_value_recursive(obj: Any, target_key: str, visited: Optional[set] = None) -> Optional[Any]:
            """재귀적으로 키를 찾아서 값 반환. key[N] 형태는 부모 키의 배열 N번째 요소로 해석."""
            if visited is None:
                visited = set()
            
            if isinstance(obj, (dict, list)):
                obj_id = id(obj)
                if obj_id in visited:
                    return None
                visited.add(obj_id)
            
            # key[N] 형태: payload에는 필드가 배열로 있음 (예: device_model: ["Windows", "Macintosh"])
            # config는 flatten 시 device_model[0], device_model[1]로 저장되므로 이 둘을 매칭
            array_index_match = re.match(r'^(.+)\[(\d+)\]$', target_key)
            if array_index_match:
                base_key, index_str = array_index_match.group(1), array_index_match.group(2)
                idx = int(index_str)
                base_value = find_value_recursive(obj, base_key, visited)
                if base_value is not None and isinstance(base_value, list) and 0 <= idx < len(base_value):
                    return base_value[idx]
            
            if isinstance(obj, dict):
                if target_key in obj:
                    return obj[target_key]
                
                if 'parsed' in obj and isinstance(obj['parsed'], (dict, list)):
                    result = find_value_recursive(obj['parsed'], target_key, visited)
                    if result is not None:
                        return result
                
                for value in obj.values():
                    # 문자열이 JSON 객체/배열이면 파싱 후 탐색 (utLogMap.parsed 등이 문자열로 올 때 coupon_price 등 발견)
                    if isinstance(value, str) and value.strip().startswith(('{', '[')):
                        try:
                            parsed = json.loads(value)
                            result = find_value_recursive(parsed, target_key, visited)
                            if result is not None:
                                return result
                        except (json.JSONDecodeError, TypeError):
                            pass
                    result = find_value_recursive(value, target_key, visited)
                    if result is not None:
                        return result
            
            elif isinstance(obj, list):
                for item in obj:
                    result = find_value_recursive(item, target_key, visited)
                    if result is not None:
                        return result
            
            if isinstance(obj, (dict, list)):
                visited.discard(id(obj))
            
            return None
        
        payload = log.get('payload')
        
        if payload is None:
            raise AssertionError(f"로그에 payload가 없습니다. URL: {log.get('url')}")
        
        # payload가 문자열인 경우 (JSON 파싱 실패한 경우)
        if isinstance(payload, str):
            raise AssertionError(
                f"payload가 JSON 형식이 아닙니다. "
                f"URL: {log.get('url')}, Payload: {payload[:100]}..."
            )
        
        # payload가 딕셔너리가 아닌 경우
        if not isinstance(payload, dict):
            raise AssertionError(
                f"payload가 딕셔너리 형식이 아닙니다. "
                f"URL: {log.get('url')}, Payload 타입: {type(payload)}"
            )
        
        # Product Exposure의 경우 expdata.parsed 배열에서 goodscode와 일치하는 항목 찾기
        matched_expdata_item = None
        if event_type == 'Product Exposure' and goodscode:
            decoded_gokey = payload.get('decoded_gokey', {})
            params = decoded_gokey.get('params', {})
            expdata = params.get('expdata', {})
            
            if isinstance(expdata, dict) and 'parsed' in expdata:
                parsed_list = expdata.get('parsed', [])
                if isinstance(parsed_list, list):
                    for item in parsed_list:
                        if isinstance(item, dict) and 'exargs' in item:
                            exargs = item['exargs']
                            if isinstance(exargs, dict) and 'params-exp' in exargs:
                                params_exp = exargs['params-exp']
                                if isinstance(params_exp, dict) and 'parsed' in params_exp:
                                    parsed = params_exp['parsed']
                                    # _p_prod 또는 utLogMap.x_object_id로 goodscode 확인
                                    item_goodscode = None
                                    if isinstance(parsed, dict):
                                        item_goodscode = parsed.get('_p_prod')
                                        if not item_goodscode and 'utLogMap' in parsed:
                                            utlogmap = parsed['utLogMap']
                                            if isinstance(utlogmap, dict) and 'parsed' in utlogmap:
                                                utlogmap_parsed = utlogmap['parsed']
                                                if isinstance(utlogmap_parsed, dict):
                                                    item_goodscode = utlogmap_parsed.get('x_object_id')
                                    
                                    if item_goodscode and str(item_goodscode) == str(goodscode):
                                        matched_expdata_item = parsed
                                        break
        
        # 기대 데이터 검증 (재귀적 탐색 사용)
        errors = []
        passed_fields = {}  # 통과한 필드 정보 {필드명: {"expected": 기대값, "actual": 실제값}}
        for key, expected_value in expected_data.items():
            actual_value = None
            
            # PDP PV는 payload 최상위에 직접 필드가 있으므로 직접 접근
            if event_type == 'PDP PV':
                actual_value = payload.get(key)
            
            # 그 외의 경우: payload 전체에서 재귀적으로 탐색
            # 재귀적 탐색이므로 경로 제한 없이 payload 전체에서 찾음
            # matched_expdata_item은 goodscode 필터링 확인용이며, 실제 탐색은 payload 전체에서 수행
            else:
                actual_value = find_value_recursive(payload, key)
            
            # 값 검증
            field_passed = False
            # skip 값 처리: "__SKIP__"인 경우 필드 존재 여부와 값을 완전히 무시 (테스트레일 기록용으로 passed_fields에 skip 표시)
            if isinstance(expected_value, str) and expected_value == "__SKIP__":
                passed_fields[key] = {
                    "expected": "__SKIP__",
                    "actual": "(skip)",
                }
                continue
            # 빈 문자열("") 기대값 처리: actual_value가 None이어도 통과 (필드가 없어도 빈 값으로 간주)
            if isinstance(expected_value, str) and expected_value == "":
                # 기대값이 빈 문자열이면, actual_value가 None이거나 빈 문자열이면 통과
                if actual_value is None or (isinstance(actual_value, str) and actual_value == ""):
                    field_passed = True
                else:
                    # actual_value가 있으면 실패 (빈 값이어야 하는데 값이 있음)
                    errors.append(
                        f"키 '{key}'의 값이 일치하지 않습니다. "
                        f"기대값 (빈 문자열): '', 실제값: {actual_value}"
                    )
            elif key in ("origin_price", "promotion_price") and _is_price_sentinel_one(
                actual_value
            ):
                # 상품 미노출·플레이스홀더 등으로 실제값이 1만 오는 경우 기대(<원가>/<할인가> 등)와 무관하게 통과
                field_passed = True
            elif actual_value is None:
                errors.append(f"키 '{key}'에 해당하는 값이 없습니다.")
            elif isinstance(expected_value, str) and expected_value == "__MANDATORY__":
                # mandatory 필드: 빈 값만 아니면 통과
                # 빈 값 체크: None, 빈 문자열, 공백만 있는 문자열
                if actual_value is None or (isinstance(actual_value, str) and actual_value.strip() == ""):
                    errors.append(f"키 '{key}'는 mandatory 필드이지만 값이 비어있습니다.")
                else:
                    field_passed = True  # 빈 값이 아니면 통과
            elif isinstance(expected_value, list):
                # expected_value가 리스트인 경우: actual_value가 리스트에 포함되어 있으면 통과
                if actual_value not in expected_value:
                    errors.append(
                        f"키 '{key}'의 값이 일치하지 않습니다. "
                        f"기대값 (리스트 중 하나): {expected_value}, 실제값: {actual_value}"
                    )
                else:
                    field_passed = True
            else:
                # 포함 여부 매칭이 필요한 필드들 (spm 키는 아래 전용 분기에서 비교)
                contains_match_fields = {'spm-url', 'spm-pre', 'spm-cnt'}
                
                if key in contains_match_fields and isinstance(expected_value, str) and isinstance(actual_value, str):
                    # SPM 값 정규화: 마지막 숫자 부분 제거 (예: ditem0 → ditem, ditem1 → ditem)
                    def normalize_spm_value(value: str) -> str:
                        """SPM 값에서 마지막 숫자 부분을 제거하여 정규화"""
                        # 마지막에 오는 숫자 패턴을 제거 (예: ditem0, ditem1 → ditem)
                        # \d+$ : 문자열 끝에 오는 하나 이상의 숫자
                        normalized = re.sub(r'\d+$', '', value)
                        return normalized
                    
                    # 정규화된 값으로 비교
                    expected_normalized = normalize_spm_value(expected_value)
                    actual_normalized = normalize_spm_value(actual_value)
                    
                    # 포함 여부 매칭: 
                    # 1. 정규화된 값이 정확히 일치하거나 (마지막 숫자만 다른 경우)
                    # 2. 정규화된 expected_value가 정규화된 actual_value에 포함되거나
                    # 3. 원본 expected_value가 원본 actual_value에 포함되면 통과
                    # 예: expected="gmktpc.home.searchtop", actual="gmktpc.home.searchtop.dsearchbox.1fbf486arWCtiZ" → 통과
                    # 예: expected="gmktpc.searchlist", actual="gmktpc.searchlist.0.0.28e22ebayJdnYA" → 통과
                    # 예: expected="gmktpc.ordercomplete.ordercompletebt.ditem0", actual="gmktpc.ordercomplete.ordercompletebt.ditem1" → 통과 (마지막 숫자 무시)
                    if (expected_normalized == actual_normalized or 
                        expected_normalized in actual_normalized or 
                        expected_value in actual_value):
                        field_passed = True
                        # 포함 매칭 성공, 다음 필드로 (값 저장은 아래에서)
                    else:
                        errors.append(
                            f"키 '{key}'의 값이 일치하지 않습니다. "
                            f"기대값 (포함 여부): {expected_value}, 실제값: {actual_value}"
                        )
                elif key == 'ab_buckets' and isinstance(expected_value, str):
                    # ab_buckets:
                    # - 기대값이 비어있지 않으면 실제값에 기대값이 포함되면 통과
                    # - 기대값이 빈값이면(상단 분기) 실제값도 빈값이어야 통과
                    actual_text = "" if actual_value is None else str(actual_value)
                    if expected_value and expected_value in actual_text:
                        field_passed = True
                    else:
                        errors.append(
                            f"키 '{key}'의 값이 일치하지 않습니다. "
                            f"기대값 (포함 여부): {expected_value}, 실제값: {actual_value}"
                        )
                elif key in {'query'} and isinstance(expected_value, str) and isinstance(actual_value, str):
                    # query 등: 대소문자 구분 없이 비교
                    if str(expected_value).strip().lower() == str(actual_value).strip().lower():
                        field_passed = True
                    else:
                        errors.append(
                            f"키 '{key}'의 값이 일치하지 않습니다. "
                            f"기대값: {expected_value}, 실제값: {actual_value}"
                        )
                elif key == 'spm':
                    # spm: banner 포함 시 맨끝 연속 숫자 제거 후 동등 비교 (로그 SPM 필터 _check_spm_match와 동일 규칙)
                    exp_n = self._normalize_spm_for_banner_match(
                        str(expected_value) if expected_value is not None else ''
                    )
                    act_n = self._normalize_spm_for_banner_match(
                        str(actual_value) if actual_value is not None else ''
                    )
                    if exp_n == act_n:
                        field_passed = True
                    else:
                        errors.append(
                            f"키 '{key}'의 값이 일치하지 않습니다. "
                            f"기대값: {expected_value}, 실제값: {actual_value}"
                        )
                elif str(expected_value) == str(actual_value):
                    # 타입만 다르고 값이 동일한 경우 통과 (예: 기대 "0" vs 실제 0)
                    field_passed = True
                elif actual_value != expected_value:
                    errors.append(
                        f"키 '{key}'의 값이 일치하지 않습니다. "
                        f"기대값: {expected_value}, 실제값: {actual_value}"
                    )
                else:
                    field_passed = True
            
            # 필드가 통과했으면 기대값/실제값을 함께 기록
            if field_passed:
                passed_fields[key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                }
        
        if errors:
            error_msg = "\n".join(errors)
            # 디코딩된 payload 정보 포함
            decoded_info = payload.get('decoded_gokey', {})
            raise AssertionError(
                f"Payload 검증 실패:\n{error_msg}\n"
                f"디코딩된 gokey 파라미터: {json.dumps(decoded_info.get('params', {}), ensure_ascii=False, indent=2)}"
            )
        
        return True, passed_fields
    
    def validate_payload(self, log: Dict[str, Any], expected_data: Dict[str, Any], goodscode: Optional[str] = None, event_type: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Validate one tracking payload using schema paths first, recursive key lookup second."""
        def find_value_recursive(obj: Any, target_key: str, visited: Optional[set] = None) -> Optional[Any]:
            if visited is None:
                visited = set()
            if isinstance(obj, (dict, list)):
                obj_id = id(obj)
                if obj_id in visited:
                    return None
                visited.add(obj_id)

            array_index_match = re.match(r'^(.+)\[(\d+)\]$', target_key)
            if array_index_match:
                base_key, index_str = array_index_match.group(1), array_index_match.group(2)
                idx = int(index_str)
                base_value = find_value_recursive(obj, base_key, visited)
                if isinstance(base_value, list) and 0 <= idx < len(base_value):
                    return base_value[idx]

            if isinstance(obj, dict):
                if target_key in obj:
                    return obj[target_key]
                if 'parsed' in obj and isinstance(obj['parsed'], (dict, list)):
                    result = find_value_recursive(obj['parsed'], target_key, visited)
                    if result is not None:
                        return result
                for value in obj.values():
                    if isinstance(value, str) and value.strip().startswith(('{', '[')):
                        try:
                            parsed = json.loads(value)
                            result = find_value_recursive(parsed, target_key, visited)
                            if result is not None:
                                return result
                        except (json.JSONDecodeError, TypeError):
                            pass
                    result = find_value_recursive(value, target_key, visited)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_value_recursive(item, target_key, visited)
                    if result is not None:
                        return result

            if isinstance(obj, (dict, list)):
                visited.discard(id(obj))
            return None

        def navigate_path(obj: Any, path: str) -> Optional[Any]:
            if obj is None or not path:
                return None
            cur = obj
            parts = path.split(".")
            i = 0
            while i < len(parts):
                part = parts[i]
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                    i += 1
                    continue
                if isinstance(cur, dict) and isinstance(cur.get("parsed"), (dict, list)):
                    cur = cur["parsed"]
                    continue
                return None
            return cur

        def utlogmap_x_object_id(utlogmap: Any) -> Optional[Any]:
            if not isinstance(utlogmap, dict):
                return None
            parsed = utlogmap.get("parsed")
            if isinstance(parsed, dict) and parsed.get("x_object_id"):
                return parsed.get("x_object_id")
            return utlogmap.get("x_object_id")

        def product_exposure_slots(payload_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
            if payload_obj.get("_native_h_ut"):
                h_ut = payload_obj.get("h_ut", {})
                if isinstance(h_ut, dict):
                    kv = h_ut.get("kv", {})
                    slot = dict(kv) if isinstance(kv, dict) else {}
                    utlogmap = h_ut.get("utLogMap")
                    if isinstance(utlogmap, dict):
                        parsed = utlogmap.get("parsed")
                        if isinstance(parsed, dict):
                            slot["utLogMap"] = parsed
                    if slot:
                        return [slot]
                return []

            decoded = payload_obj.get("decoded_gokey", {})
            params = decoded.get("params", {}) if isinstance(decoded, dict) else {}
            expdata = params.get("expdata", {}) if isinstance(params, dict) else {}
            if (not isinstance(expdata, dict) or "parsed" not in expdata) and payload_obj.get("expdata"):
                raw_exp = payload_obj.get("expdata")
                if isinstance(raw_exp, str):
                    parsed_fallback = self._decode_expdata(raw_exp) or []
                elif isinstance(raw_exp, list):
                    parsed_fallback = raw_exp
                else:
                    parsed_fallback = []
                expdata = {"parsed": parsed_fallback}
            parsed_list = expdata.get("parsed", []) if isinstance(expdata, dict) else []
            out: List[Dict[str, Any]] = []
            if isinstance(parsed_list, list):
                for item in parsed_list:
                    if not isinstance(item, dict):
                        continue
                    exargs = item.get("exargs", {})
                    params_exp = exargs.get("params-exp", {}) if isinstance(exargs, dict) else {}
                    parsed = params_exp.get("parsed", {}) if isinstance(params_exp, dict) else {}
                    if isinstance(parsed, dict):
                        slot = dict(parsed)
                        if item.get("spm") and "spm" not in slot:
                            slot["spm"] = item.get("spm")
                        out.append(slot)
            return out

        def matched_product_exposure_slot(payload_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if event_type != 'Product Exposure' or not goodscode:
                return None
            for slot in product_exposure_slots(payload_obj):
                item_goodscode = slot.get("_p_prod") or utlogmap_x_object_id(slot.get("utLogMap"))
                if item_goodscode and str(item_goodscode) == str(goodscode):
                    return slot
            return None

        def normalize_expected_spec(spec_key: str, spec_value: Any) -> Tuple[str, str, Any]:
            if isinstance(spec_value, dict) and {"path", "field", "expected"}.issubset(spec_value.keys()):
                return str(spec_value["path"]), str(spec_value["field"]), spec_value["expected"]
            return spec_key, spec_key.split(".")[-1], spec_value

        payload = log.get('payload')
        if payload is None:
            raise AssertionError(f"Log payload is missing. URL: {log.get('url')}")
        if isinstance(payload, str):
            raise AssertionError(f"Payload is not JSON. URL: {log.get('url')}, Payload: {payload[:100]}...")
        if not isinstance(payload, dict):
            raise AssertionError(f"Payload is not a dict. URL: {log.get('url')}, type={type(payload)}")

        decoded_gokey = payload.get('decoded_gokey', {})
        params = decoded_gokey.get('params', {}) if isinstance(decoded_gokey, dict) else {}
        h_ut = payload.get('h_ut', {}) if isinstance(payload.get('h_ut'), dict) else {}
        h_ut_kv = h_ut.get('kv', {}) if isinstance(h_ut.get('kv'), dict) else {}
        h_ut_utlogmap = h_ut.get('utLogMap', {}) if isinstance(h_ut.get('utLogMap'), dict) else {}
        h_ut_native_root = {}
        if h_ut_kv or h_ut_utlogmap:
            h_ut_native_root.update(h_ut_kv)
            parsed_utlogmap = h_ut_utlogmap.get('parsed')
            if isinstance(parsed_utlogmap, dict):
                h_ut_native_root['utLogMap'] = parsed_utlogmap
        matched_slot = matched_product_exposure_slot(payload)

        def resolve_actual(path: str, field: str) -> Optional[Any]:
            candidates: List[Any] = []
            if matched_slot is not None:
                candidates.append(matched_slot)
            if h_ut_native_root:
                candidates.append(h_ut_native_root)
            if isinstance(params, dict):
                candidates.append(params)
            candidates.append(payload)

            for candidate in candidates:
                value = navigate_path(candidate, path)
                if value is not None and not isinstance(value, (dict, list)):
                    return value

            for candidate in candidates:
                value = find_value_recursive(candidate, field)
                if value is not None and not isinstance(value, (dict, list)):
                    return value
            return None

        errors = []
        passed_fields = {}
        for spec_key, spec_value in expected_data.items():
            path, field, expected_value = normalize_expected_spec(spec_key, spec_value)
            actual_value = payload.get(field) if event_type == 'PDP PV' else resolve_actual(path, field)
            display_key = path or field

            field_passed = False
            if isinstance(expected_value, str) and expected_value == "__SKIP__":
                passed_fields[display_key] = {"expected": "__SKIP__", "actual": "(skip)"}
                continue
            if isinstance(expected_value, str) and expected_value == "":
                if actual_value is None or (isinstance(actual_value, str) and actual_value == ""):
                    field_passed = True
                else:
                    errors.append(f"'{display_key}' mismatch. expected='', actual={actual_value}")
            elif field in ("origin_price", "promotion_price") and _is_price_sentinel_one(actual_value):
                field_passed = True
            elif actual_value is None:
                errors.append(f"'{display_key}' value is missing.")
            elif isinstance(expected_value, str) and expected_value == "__MANDATORY__":
                if isinstance(actual_value, str):
                    field_passed = actual_value.strip() != ""
                else:
                    field_passed = actual_value is not None
                if not field_passed:
                    errors.append(f"'{display_key}' is mandatory but empty.")
            elif isinstance(expected_value, list):
                if actual_value in expected_value:
                    field_passed = True
                else:
                    errors.append(f"'{display_key}' mismatch. expected one of {expected_value}, actual={actual_value}")
            else:
                contains_match_fields = {'spm-url', 'spm-pre', 'spm-cnt'}
                if field in contains_match_fields and isinstance(expected_value, str) and isinstance(actual_value, str):
                    def normalize_spm_value(value: str) -> str:
                        return re.sub(r'\d+$', '', value)
                    expected_normalized = normalize_spm_value(expected_value)
                    actual_normalized = normalize_spm_value(actual_value)
                    if expected_normalized == actual_normalized or expected_normalized in actual_normalized or expected_value in actual_value:
                        field_passed = True
                    else:
                        errors.append(f"'{display_key}' mismatch. expected contains {expected_value}, actual={actual_value}")
                elif field == 'ab_buckets' and isinstance(expected_value, str):
                    actual_text = "" if actual_value is None else str(actual_value)
                    if expected_value and expected_value in actual_text:
                        field_passed = True
                    else:
                        errors.append(f"'{display_key}' mismatch. expected contains {expected_value}, actual={actual_value}")
                elif field == 'query' and isinstance(expected_value, str) and isinstance(actual_value, str):
                    if expected_value.strip().lower() == actual_value.strip().lower():
                        field_passed = True
                    else:
                        errors.append(f"'{display_key}' mismatch. expected={expected_value}, actual={actual_value}")
                elif field == 'spm':
                    exp_n = self._normalize_spm_for_banner_match(str(expected_value) if expected_value is not None else '')
                    act_n = self._normalize_spm_for_banner_match(str(actual_value) if actual_value is not None else '')
                    if exp_n == act_n:
                        field_passed = True
                    else:
                        errors.append(f"'{display_key}' mismatch. expected={expected_value}, actual={actual_value}")
                elif str(expected_value) == str(actual_value):
                    field_passed = True
                elif actual_value != expected_value:
                    errors.append(f"'{display_key}' mismatch. expected={expected_value}, actual={actual_value}")
                else:
                    field_passed = True

            if field_passed:
                passed_fields[display_key] = {"expected": expected_value, "actual": actual_value}

        if errors:
            decoded_info = payload.get('decoded_gokey', {})
            raise AssertionError(
                "Payload validation failed:\n"
                + "\n".join(errors)
                + "\nDecoded params: "
                + json.dumps(decoded_info.get('params', {}), ensure_ascii=False, indent=2)
            )

        return True, passed_fields

    def clear_logs(self):
        """
        수집된 모든 로그 초기화
        """
        self.logs.clear()
        self._h_ut_pipeline.clear()
        logger.info('로그 초기화 완료')

    def get_h_ut_pipeline(self) -> List[Dict[str, Any]]:
        """시나리오 구간 중 수집된 h-ut → 합성 aplus 적재 요약(저장용)."""
        return list(self._h_ut_pipeline)
    
    def __enter__(self):
        """
        Context manager 진입 시 자동으로 트래킹 시작
        """
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager 종료 시 자동으로 트래킹 중지
        """
        self.stop()


class NetworkTracker:
    """
    검증 스텝에서 사용하는 트래커 파사드.
    기본 구현은 Mitmproxy 기반 TrackingLogStore 백엔드다.
    """

    def __init__(
        self,
        page: Any = None,
        source_path: Optional[str] = None,
        logs: Optional[List[Dict[str, Any]]] = None,
        backend: Optional[TrackerBackend] = None,
    ) -> None:
        self._backend = backend or TrackingLogStore(
            page=page,
            source_path=source_path,
            logs=logs,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._backend, item)

    def start(self) -> None:
        self._backend.start()

    def stop(self) -> None:
        self._backend.stop()

    def clear_logs(self) -> None:
        self._backend.clear_logs()

    def get_logs(self, request_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._backend.get_logs(request_type)
