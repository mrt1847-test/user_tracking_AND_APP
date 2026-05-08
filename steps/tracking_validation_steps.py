"""
BDD Step Definitions for Tracking Validation
트래킹 로그 정합성 검증을 위한 재사용 가능한 스텝 정의 (module_config.json만 사용)
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from pytest_bdd import then, parsers
from utils.validation_helpers import (
    validate_event_type_logs,
    load_module_config,
    _find_spm_recursive,
    get_event_logs,
    module_title_to_filename,
)

logger = logging.getLogger(__name__)


def _check_and_validate_event_logs(
    tc_id: str,
    event_type: str,
    event_config_key: str,
    tracker,
    module_title: str,
    frontend_data,
    area: str,
    bdd_context,
    goodscode: str = '',
) -> bool:
    """
    이벤트 로그 수집 확인 및 정합성 검증 (단순화된 로직)
    
    Returns:
        True: 성공 또는 스킵, False: 실패
    """
    # skip_reason 확인
    skip_reason = None
    if hasattr(bdd_context, 'get'):
        skip_reason = bdd_context.get('skip_reason')
    elif hasattr(bdd_context, 'store'):
        skip_reason = bdd_context.store.get('skip_reason')
    
    if skip_reason:
        logger.warning(f"[TestRail TC: {tc_id}] Skip: {skip_reason}")
        return True
    
    # module_config 확인 (nth 있으면 모듈명(nth).json 우선)
    nth = bdd_context.get('nth') or (getattr(bdd_context, 'store', None) and bdd_context.store.get('nth'))
    module_config = load_module_config(area=area, module_title=module_title, nth=nth)
    module_config_data = module_config if isinstance(module_config, dict) else {}
    
    if event_config_key not in module_config_data:
        logger.info(f"[TestRail TC: {tc_id}] 모듈 '{module_title}'에 {event_type}이 정의되어 있지 않아 검증을 스킵합니다.")
        return True
    
    # 1. 로그 수집 확인
    logs = get_event_logs(tracker, event_type, goodscode, module_config_data)
    
    # 2. 프론트 실패 여부 확인 (로그 유무와 관계없이 확인)
    frontend_failed = False
    frontend_error = None
    if hasattr(bdd_context, 'get'):
        frontend_failed = bdd_context.get('frontend_action_failed', False)
        frontend_error = bdd_context.get('frontend_error_message')
    elif hasattr(bdd_context, 'store'):
        frontend_failed = bdd_context.store.get('frontend_action_failed', False)
        frontend_error = bdd_context.store.get('frontend_error_message')
    
    # 3. 로그가 없으면 실패 처리
    if len(logs) == 0:
        if frontend_failed:
            # 프론트 실패로 인한 로그 수집 실패
            error_message = f"[TestRail TC: {tc_id}] {event_type} 로그가 수집되지 않았습니다.\n[프론트 실패 사유]\n{frontend_error or '프론트 동작 실패'}"
            logger.error(error_message)
        else:
            # 이벤트 수집 오류
            error_message = f"[TestRail TC: {tc_id}] {event_type} 로그가 수집되지 않았습니다.\n[이벤트 수집 오류]"
            logger.error(error_message)
        
        # TestRail 기록을 위해 실패 플래그 설정
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        return False
    
    # 4. 로그가 있으면 정합성 검증 수행 (프론트 실패 여부와 관계없이 검증 진행)
    logger.info(f"[TestRail TC: {tc_id}] {event_type} 로그 정합성 검증 시작")
    success, errors, passed_fields = validate_event_type_logs(
        tracker=tracker,
        event_type=event_type,
        goodscode=goodscode,
        module_title=module_title,
        frontend_data=frontend_data,
        module_config=module_config
    )
    
    # 통과한 필드 목록을 bdd_context에 저장 (TestRail 로그에 표시하기 위해)
    bdd_context['validation_passed_fields'] = passed_fields
    
    if not success:
        # 검증 실패 시 실패 처리 (프론트 실패 여부와 관계없이)
        error_message = f"[TestRail TC: {tc_id}] {event_type} 로그 정합성 검증 실패:\n[필드값 정합성 오류]\n" + "\n".join(errors)
        # 통과한 필드가 있으면 표시
        if passed_fields and isinstance(passed_fields, dict):
            error_message += f"\n\n[통과한 필드]\n"
            for field, value in passed_fields.items():
                if isinstance(value, dict):
                    expected = value.get("expected")
                    actual = value.get("actual")
                    error_message += f"{field}: expected={expected}, actual={actual}\n"
                else:
                    # 하위 호환: 과거 포맷(값만 저장된 경우)
                    error_message += f"{field}: {value}\n"
        logger.error(error_message)
        
        # TestRail 기록을 위해 실패 플래그 설정
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        return False
    
    # 5. 검증 통과 시 pass 처리 (프론트 실패가 있어도 로그가 있고 검증이 통과하면 pass)
    bdd_context['validation_failed'] = False
    if frontend_failed:
        logger.info(f"[TestRail TC: {tc_id}] {event_type} 로그 정합성 검증 통과 (프론트 실패가 있었지만 이벤트 로그 검증 통과)")
    else:
        logger.info(f"[TestRail TC: {tc_id}] {event_type} 로그 정합성 검증 통과")
    return True


def _get_common_context(bdd_context):
    """공통 context 값 확인 및 반환"""
    from utils.validation_helpers import extract_price_info_from_pdp_pv
    
    tracker = bdd_context.get('tracker')
    if not tracker:
        raise ValueError("bdd_context에 'tracker'가 없습니다. 네트워크 트래킹을 시작해주세요.")
    
    goodscode = bdd_context.get('goodscode')
    if not goodscode:
        raise ValueError("bdd_context에 'goodscode'가 없습니다.")
    
    module_title = bdd_context.get('module_title')
    if not module_title:
        raise ValueError("bdd_context에 'module_title'가 없습니다.")
    
    area = bdd_context.get('area')
    if not area:
        raise ValueError("bdd_context에 'area'가 없습니다. Feature 파일 경로에서 영역을 추론하지 못했습니다.")
    
    keyword = bdd_context.get('keyword', '')
    category_id = bdd_context.get('category_id', '')
    
    # is_ad 가져오기 (bdd_context.store 또는 bdd_context에서)
    is_ad = None
    if hasattr(bdd_context, 'store') and hasattr(bdd_context.store, 'get'):
        is_ad = bdd_context.store.get('is_ad')
    elif hasattr(bdd_context, 'get'):
        is_ad = bdd_context.get('is_ad')
    
    # 🔥 PDP PV 로그에서 가격 정보 추출 (프론트엔드 대신)
    price_info = extract_price_info_from_pdp_pv(tracker, goodscode)
    
    frontend_data = price_info.copy() if price_info else {}
    if keyword:
        frontend_data['keyword'] = keyword
    if category_id:
        frontend_data['category_id'] = category_id
    if is_ad is not None:
        frontend_data['is_ad'] = is_ad
    
    return tracker, goodscode, module_title, frontend_data if frontend_data else None, area


def _get_common_context_for_module_exposure(bdd_context):
    """
    Module Exposure 전용 context.
    섹션 이동만 한 시나리오 등 goodscode가 없을 때는 PDP PV 기반 가격 추출을 생략하고 goodscode는 빈 문자열로 둔다.
    goodscode가 있으면 기존 _get_common_context와 동일하게 PDP PV에서 frontend_data를 채운다.
    """
    from utils.validation_helpers import extract_price_info_from_pdp_pv

    tracker = bdd_context.get('tracker')
    if not tracker:
        raise ValueError("bdd_context에 'tracker'가 없습니다. 네트워크 트래킹을 시작해주세요.")

    module_title = bdd_context.get('module_title')
    if not module_title:
        raise ValueError("bdd_context에 'module_title'가 없습니다.")

    area = bdd_context.get('area')
    if not area:
        raise ValueError("bdd_context에 'area'가 없습니다. Feature 파일 경로에서 영역을 추론하지 못했습니다.")

    raw_gs = bdd_context.get('goodscode')
    if raw_gs is None or raw_gs == '':
        goodscode = ''
    else:
        goodscode = str(raw_gs).strip()

    keyword = bdd_context.get('keyword', '')
    category_id = bdd_context.get('category_id', '')

    is_ad = None
    if hasattr(bdd_context, 'store') and hasattr(bdd_context.store, 'get'):
        is_ad = bdd_context.store.get('is_ad')
    elif hasattr(bdd_context, 'get'):
        is_ad = bdd_context.get('is_ad')

    frontend_data = {}
    if goodscode:
        price_info = extract_price_info_from_pdp_pv(tracker, goodscode)
        if price_info:
            frontend_data = price_info.copy()
    else:
        logger.debug(
            "Module Exposure 검증: goodscode 없음 — PDP PV 기반 가격 데이터는 사용하지 않습니다."
        )

    if keyword:
        frontend_data['keyword'] = keyword
    if category_id:
        frontend_data['category_id'] = category_id
    if is_ad is not None:
        frontend_data['is_ad'] = is_ad

    return tracker, goodscode, module_title, frontend_data if frontend_data else None, area


@then("PV 로그가 정합성 검증을 통과해야 함")
def then_pv_logs_should_pass_validation(bdd_context):
    """PV 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        
        # module_config.json에서 PV가 정의되어 있는지 확인 (nth 있으면 모듈명(nth).json 우선)
        nth = bdd_context.get('nth') or (getattr(bdd_context, 'store', None) and bdd_context.store.get('nth'))
        module_config = load_module_config(area=area, module_title=module_title, nth=nth)
        module_config_data = module_config if isinstance(module_config, dict) else {}
        event_config_key = 'pv'
        
        if event_config_key not in module_config_data:
            logger.info(f"모듈 '{module_title}'에 PV가 정의되어 있지 않아 검증을 스킵합니다.")
            return
        
        logger.info("PV 로그 정합성 검증 시작")
        success, errors, passed_fields = validate_event_type_logs(
            tracker=tracker,
            event_type='PV',
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            module_config=module_config
        )
        
        # 통과한 필드 목록을 bdd_context에 저장
        bdd_context['validation_passed_fields'] = passed_fields
        
        if not success:
            error_message = "PV 로그 정합성 검증 실패:\n" + "\n".join(errors)
            # 통과한 필드가 있으면 표시
            if passed_fields and isinstance(passed_fields, dict):
                error_message += f"\n\n[통과한 필드]\n"
                for field, value in passed_fields.items():
                    if isinstance(value, dict):
                        expected = value.get("expected")
                        actual = value.get("actual")
                        error_message += f"{field}: expected={expected}, actual={actual}\n"
                    else:
                        # 하위 호환: 과거 포맷(값만 저장된 경우)
                        error_message += f"{field}: {value}\n"
            logger.error(error_message)
            # TestRail 기록을 위해 실패 플래그 설정 (TC 번호는 없지만)
            bdd_context['validation_failed'] = True
            bdd_context['validation_error_message'] = error_message
            # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)
        else:
            logger.info("PV 로그 정합성 검증 통과")
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"PV 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'PDP PV 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_pv_logs_should_pass_validation(tc_id, bdd_context):
    """PDP PV 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_pv_logs_should_pass_validation 실행: tc_id={tc_id}")
    # TC 번호가 비어있으면 검증 건너뛰기
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP PV 로그 검증을 건너뜁니다.")
        return
    
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        
        # TestRail TC 번호를 context에 저장
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        
        # 단순화된 검증 로직 사용
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP PV',
            event_config_key='pdp_pv',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"[TestRail TC: {tc_id}] PDP PV 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'Module Exposure 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_module_exposure_logs_should_pass_validation(tc_id, bdd_context):
    """Module Exposure 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_module_exposure_logs_should_pass_validation 실행: tc_id={tc_id}")
    # TC 번호가 비어있으면 검증 건너뛰기
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 Module Exposure 로그 검증을 건너뜁니다.")
        return
    
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context_for_module_exposure(
            bdd_context
        )
        
        # TestRail TC 번호를 context에 저장
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        
        # 단순화된 검증 로직 사용
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='Module Exposure',
            event_config_key='module_exposure',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"[TestRail TC: {tc_id}] Module Exposure 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'Product Exposure 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_product_exposure_logs_should_pass_validation(tc_id, bdd_context):
    """Product Exposure 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_product_exposure_logs_should_pass_validation 실행: tc_id={tc_id}")
    # TC 번호가 비어있으면 검증 건너뛰기
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 Product Exposure 로그 검증을 건너뜁니다.")
        return
    
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        
        # TestRail TC 번호를 context에 저장
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        
        # 단순화된 검증 로직 사용
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='Product Exposure',
            event_config_key='product_exposure',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"[TestRail TC: {tc_id}] Product Exposure 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'Product Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_product_click_logs_should_pass_validation(tc_id, bdd_context):
    """Product Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_product_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    # TC 번호가 비어있으면 검증 건너뛰기
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 Product Click 로그 검증을 건너뜁니다.")
        return
    
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        
        # TestRail TC 번호를 context에 저장
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        
        # 단순화된 검증 로직 사용
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='Product Click',
            event_config_key='product_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"[TestRail TC: {tc_id}] Product Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'General Exposure 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_general_exposure_logs_should_pass_validation(tc_id, bdd_context):
    """General Exposure 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_general_exposure_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 General Exposure 로그 검증을 건너뜁니다.")
        return

    try:
        tracker, _, module_title, frontend_data, area = _get_common_context_for_module_exposure(
            bdd_context
        )
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='General Exposure',
            event_config_key='general_exposure',
            tracker=tracker,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] General Exposure 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'General Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_general_click_logs_should_pass_validation(tc_id, bdd_context):
    """General Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_general_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 General Click 로그 검증을 건너뜁니다.")
        return

    try:
        tracker, _, module_title, frontend_data, area = _get_common_context_for_module_exposure(
            bdd_context
        )
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='General Click',
            event_config_key='general_click',
            tracker=tracker,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] General Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'Product ATC Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_product_atc_click_logs_should_pass_validation(tc_id, bdd_context):
    """Product ATC Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_product_atc_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    # TC 번호가 비어있으면 검증 건너뛰기
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 Product ATC Click 로그 검증을 건너뜁니다.")
        return
    
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        
        # TestRail TC 번호를 context에 저장
        logger.debug(f"bdd_context['testrail_tc_id']에 {tc_id} 저장")
        bdd_context['testrail_tc_id'] = tc_id
        
        # 단순화된 검증 로직 사용
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='Product ATC Click',
            event_config_key='product_atc_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        # 예외 발생 시 bdd_context에 실패 정보 저장하고 계속 진행
        error_message = f"[TestRail TC: {tc_id}] Product ATC Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
        # 예외를 다시 발생시키지 않음 (다음 스텝 계속 실행)


@then(parsers.re(r'Product Minidetail 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_product_minidetail_logs_should_pass_validation(tc_id, bdd_context):
    """Product Minidetail 로그 정합성 검증 (가격 관련 필드 제외, module_config.json에 정의된 경우만)"""
    logger.debug(f"then_product_minidetail_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 Product Minidetail 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='Product Minidetail',
            event_config_key='product_minidetail',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] Product Minidetail 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'PDP Buynow Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_buynow_click_logs_should_pass_validation(tc_id, bdd_context):
    """PDP Buynow Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_buynow_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP Buynow Click 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP Buynow Click',
            event_config_key='pdp_buynow_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] PDP Buynow Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'PDP ATC Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_atc_click_logs_should_pass_validation(tc_id, bdd_context):
    """PDP ATC Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_atc_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP ATC Click 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP ATC Click',
            event_config_key='pdp_atc_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] PDP ATC Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'PDP Gift Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_gift_click_logs_should_pass_validation(tc_id, bdd_context):
    """PDP Gift Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_gift_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP Gift Click 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP Gift Click',
            event_config_key='pdp_gift_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] PDP Gift Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'PDP Join Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_join_click_logs_should_pass_validation(tc_id, bdd_context):
    """PDP Join Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_join_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP Join Click 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP Join Click',
            event_config_key='pdp_join_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] PDP Join Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'PDP Rental Click 로그가 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_pdp_rental_click_logs_should_pass_validation(tc_id, bdd_context):
    """PDP Rental Click 로그 정합성 검증 (module_config.json에 정의된 경우만)"""
    logger.debug(f"then_pdp_rental_click_logs_should_pass_validation 실행: tc_id={tc_id}")
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 PDP Rental Click 로그 검증을 건너뜁니다.")
        return
    try:
        tracker, goodscode, module_title, frontend_data, area = _get_common_context(bdd_context)
        bdd_context['testrail_tc_id'] = tc_id
        _check_and_validate_event_logs(
            tc_id=tc_id,
            event_type='PDP Rental Click',
            event_config_key='pdp_rental_click',
            tracker=tracker,
            goodscode=goodscode,
            module_title=module_title,
            frontend_data=frontend_data,
            area=area,
            bdd_context=bdd_context
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] PDP Rental Click 로그 검증 중 예외 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['testrail_tc_id'] = tc_id
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then("모든 트래킹 로그를 JSON 파일로 저장함")
def then_save_all_tracking_logs_to_json(bdd_context):
    """
    모든 트래킹 로그를 JSON 파일로 저장.
    goodscode가 없어도 Module/General 등 SPM 기반 로그는 저장한다
    (General 클릭·섹션 이동만 하는 시나리오). goodscode가 있으면 PDP·상품 이벤트도 포함한다.
    tracker·module_title이 없을 때만 저장을 생략한다.
    """
    tracker = bdd_context.get("tracker")
    if not tracker:
        logger.warning(
            "트래킹 JSON 저장 생략: bdd_context에 tracker가 없습니다. (이전 스텝 실패 가능)"
        )
        return

    goodscode = bdd_context.get("goodscode") or (
        getattr(bdd_context, "store", None) and bdd_context.store.get("goodscode")
    )
    if not goodscode:
        logger.debug(
            "goodscode 없음: PDP PV·Product 계열 로그는 JSON에 포함하지 않습니다. "
            "(General 전용·섹션 이동만 등 정상 케이스일 수 있음)"
        )

    module_title = bdd_context.get("module_title")
    if not module_title:
        logger.warning(
            "트래킹 JSON 저장 생략: module_title이 없습니다. (이전 스텝 실패 가능)"
        )
        return

    nth = bdd_context.get("nth") or (
        getattr(bdd_context, "store", None) and bdd_context.store.get("nth")
    )
    try:
        _save_tracking_logs(
            bdd_context, tracker, goodscode or None, module_title, nth=nth
        )
    except Exception as e:
        logger.error(
            "트래킹 JSON 저장 중 오류 (다음 스텝은 계속 진행): %s",
            e,
            exc_info=True,
        )


@then("모든 로그 검증이 완료되었음")
def then_all_validations_completed(bdd_context):
    """모든 검증 오류를 한 번에 확인"""
    validation_errors = bdd_context.store.get('validation_errors', [])
    if validation_errors:
        error_message = "다음 검증이 실패했습니다:\n" + "\n".join(validation_errors)
        logger.error(error_message)
        raise AssertionError(error_message)
    logger.info("모든 로그 검증이 성공적으로 완료되었습니다.")


def _save_tracking_logs(bdd_context, tracker, goodscode, module_title, nth=None):
    """
    트래킹 로그를 JSON 파일로 저장 (tracking_all만 저장). nth가 있으면 tracking_all_모듈명(nth).json
    goodscode가 없으면 PV·Module Exposure·General 등만 포함하고, PDP PV·Product·PDP 클릭 계열은 생략한다.
    """
    try:
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        area = bdd_context.get('area')
        if not area:
            raise ValueError("bdd_context에 'area'가 없습니다. Feature 파일 경로에서 영역을 추론하지 못했습니다.")
        module_config = load_module_config(area=area, module_title=module_title, nth=nth)
        
        # 모듈별 설정에서 SPM 가져오기 (이벤트 타입별 섹션에서, 재귀적으로 탐색)
        module_spm = None
        general_exposure_spm = None
        general_click_spm = None
        if isinstance(module_config, dict):
            # module_exposure 섹션에서 spm 가져오기 (재귀적으로 탐색)
            module_exposure = module_config.get('module_exposure', {})
            if module_exposure:
                module_spm = _find_spm_recursive(module_exposure)
            general_exposure = module_config.get('general_exposure', {})
            if general_exposure:
                general_exposure_spm = _find_spm_recursive(general_exposure)
            general_click = module_config.get('general_click', {})
            if general_click:
                general_click_spm = _find_spm_recursive(general_click)

        module_safe = module_title_to_filename(module_title)
        effective_goodscode = ("" if goodscode is None else str(goodscode)).strip()

        # 각 이벤트 타입별 로그 저장 (주석 처리: tracking_all만 저장하도록 함)
        # event_configs = [
        #     ('pv', 'get_pv_logs', None),
        #     ('pdp_pv', 'get_pdp_pv_logs', None),
        #     ('module_exposure', 'get_module_exposure_logs_by_spm', None),
        #     ('product_exposure', 'get_product_exposure_logs_by_goodscode', None),
        #     ('product_click', 'get_product_click_logs_by_goodscode', None),
        #     ('product_atc_click', 'get_product_atc_click_logs_by_goodscode', None),
        #     ('product_minidetail', 'get_product_minidetail_logs_by_goodscode', None),
        #     ('pdp_buynow_click', 'get_pdp_buynow_click_logs_by_goodscode', None),
        #     ('pdp_atc_click', 'get_pdp_atc_click_logs_by_goodscode', None),
        #     ('pdp_gift_click', 'get_pdp_gift_click_logs_by_goodscode', None),
        #     ('pdp_join_click', 'get_pdp_join_click_logs_by_goodscode', None),
        #     ('pdp_rental_click', 'get_pdp_rental_click_logs_by_goodscode', None),
        # ]
        # for event_type, method_name, method_arg in event_configs:
        #     get_logs_method = getattr(tracker, method_name)
        #     if method_name in ['get_pv_logs', 'get_pdp_pv_logs']:
        #         if method_name == 'get_pv_logs':
        #             logs = get_logs_method()
        #         else:
        #             logs = tracker.get_pdp_pv_logs_by_goodscode(goodscode)
        #     elif method_name == 'get_module_exposure_logs_by_spm':
        #         if module_spm:
        #             logs = get_logs_method(module_spm)
        #         else:
        #             logs = tracker.get_logs('Module Exposure')
        #             logger.warning(f"모듈 '{module_title}'의 SPM 값이 없어 전체 Module Exposure 로그를 사용합니다.")
        #     elif method_name == 'get_product_exposure_logs_by_goodscode':
        #         if module_spm:
        #             logs = get_logs_method(goodscode, module_spm)
        #         else:
        #             logs = get_logs_method(goodscode)
        #     elif method_name == 'get_product_click_logs_by_goodscode':
        #         logs = get_logs_method(goodscode)
        #     else:
        #         logs = get_logs_method(goodscode)
        #     pdp_click_save_only_when_exists = {
        #         'pdp_buynow_click', 'pdp_atc_click', 'pdp_gift_click', 'pdp_join_click', 'pdp_rental_click'
        #     }
        #     if event_type in pdp_click_save_only_when_exists and len(logs) == 0:
        #         continue
        #     filepath = Path(f'json/tracking_{event_type}_{goodscode}_{timestamp}.json')
        #     filepath.parent.mkdir(parents=True, exist_ok=True)
        #     with open(filepath, 'w', encoding='utf-8') as f:
        #         json.dump(logs, f, ensure_ascii=False, indent=2, default=str)
        #     if len(logs) > 0:
        #         logger.info(f"{event_type} 로그 저장 완료: {filepath.resolve()} (로그 개수: {len(logs)})")
        #     else:
        #         logger.warning(f"{event_type} 로그가 없어 빈 파일로 저장했습니다: {filepath.resolve()}")
        #
        # 전체 로그 저장
        all_logs = []
        all_logs.extend(tracker.get_pv_logs())
        
        if isinstance(module_spm, str) and module_spm:
            module_exposure_logs = tracker.get_module_exposure_logs_by_spm(module_spm)
            all_logs.extend(module_exposure_logs)
            logger.info(f"SPM '{module_spm}'로 필터링된 Module Exposure 로그: {len(module_exposure_logs)}개")
        elif isinstance(module_spm, list):
            module_exposure_logs = []
            for spm in module_spm:
                module_exposure_logs.extend(tracker.get_module_exposure_logs_by_spm(spm))
            all_logs.extend(module_exposure_logs)
            logger.info(f"SPM 목록 {module_spm}로 OR 필터링된 Module Exposure 로그: {len(module_exposure_logs)}개")
        else:
            all_logs.extend(tracker.get_logs('Module Exposure'))
            logger.warning(f"모듈 '{module_title}'의 SPM 값이 없어 전체 Module Exposure 로그를 사용합니다.")

        if effective_goodscode:
            all_logs.extend(tracker.get_pdp_pv_logs_by_goodscode(effective_goodscode))
            if isinstance(module_spm, str) and module_spm:
                product_exposure_logs = tracker.get_product_exposure_logs_by_goodscode(
                    effective_goodscode, module_spm
                )
            elif isinstance(module_spm, list):
                product_exposure_logs = []
                for spm in module_spm:
                    product_exposure_logs.extend(
                        tracker.get_product_exposure_logs_by_goodscode(effective_goodscode, spm)
                    )
            else:
                product_exposure_logs = tracker.get_product_exposure_logs_by_goodscode(
                    effective_goodscode
                )
            all_logs.extend(product_exposure_logs)
            all_logs.extend(tracker.get_product_click_logs_by_goodscode(effective_goodscode))
        else:
            logger.debug(
                "goodscode 없음: PDP PV·Product Exposure·Product Click 로그는 tracking_all에 포함하지 않음"
            )

        if isinstance(general_exposure_spm, str) and general_exposure_spm:
            general_exposure_logs = tracker.get_general_exposure_logs_by_spm(general_exposure_spm)
            all_logs.extend(general_exposure_logs)
            logger.info(f"SPM '{general_exposure_spm}'로 필터링된 General Exposure 로그: {len(general_exposure_logs)}개")
        elif isinstance(general_exposure_spm, list):
            general_exposure_logs = []
            for spm in general_exposure_spm:
                general_exposure_logs.extend(tracker.get_general_exposure_logs_by_spm(spm))
            all_logs.extend(general_exposure_logs)
            logger.info(f"SPM 목록 {general_exposure_spm}로 OR 필터링된 General Exposure 로그: {len(general_exposure_logs)}개")
        else:
            general_exposure_logs = tracker.get_logs('General Exposure')
            all_logs.extend(general_exposure_logs)
            logger.warning(f"모듈 '{module_title}'의 general_exposure SPM 값이 없어 전체 General Exposure 로그를 사용합니다.")

        if isinstance(general_click_spm, str) and general_click_spm:
            general_click_logs = tracker.get_general_click_logs_by_spm(general_click_spm)
            all_logs.extend(general_click_logs)
            logger.info(f"SPM '{general_click_spm}'로 필터링된 General Click 로그: {len(general_click_logs)}개")
        elif isinstance(general_click_spm, list):
            general_click_logs = []
            for spm in general_click_spm:
                general_click_logs.extend(tracker.get_general_click_logs_by_spm(spm))
            all_logs.extend(general_click_logs)
            logger.info(f"SPM 목록 {general_click_spm}로 OR 필터링된 General Click 로그: {len(general_click_logs)}개")
        else:
            general_click_logs = tracker.get_logs('General Click')
            all_logs.extend(general_click_logs)
            logger.warning(f"모듈 '{module_title}'의 general_click SPM 값이 없어 전체 General Click 로그를 사용합니다.")

        if effective_goodscode:
            all_logs.extend(tracker.get_product_atc_click_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_product_minidetail_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_pdp_buynow_click_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_pdp_atc_click_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_pdp_gift_click_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_pdp_join_click_logs_by_goodscode(effective_goodscode))
            all_logs.extend(tracker.get_pdp_rental_click_logs_by_goodscode(effective_goodscode))

        if len(all_logs) > 0:
            if nth is not None and str(nth).strip() != '':
                all_filepath = Path(f'json/tracking_all_{module_safe}({nth}).json')
            else:
                all_filepath = Path(f'json/tracking_all_{module_safe}.json')
            all_filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(all_filepath, 'w', encoding='utf-8') as f:
                json.dump(all_logs, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"전체 트래킹 로그 저장 완료: {all_filepath.resolve()} (로그 개수: {len(all_logs)})")

        # # Product Exposure 이벤트만 SPM 기준으로 별도 파일 저장 (상품번호 필터 없음)
        # if module_spm:
        #     product_exposure_logs = tracker.get_product_exposure_logs_by_spm(module_spm)
        #     if product_exposure_logs:
        #         if nth is not None and str(nth).strip() != '':
        #             pe_filepath = Path(f'json/tracking_product_exposure_{module_safe}({nth}).json')
        #         else:
        #             pe_filepath = Path(f'json/tracking_product_exposure_{module_safe}.json')
        #         pe_filepath.parent.mkdir(parents=True, exist_ok=True)
        #         with open(pe_filepath, 'w', encoding='utf-8') as f:
        #             json.dump(product_exposure_logs, f, ensure_ascii=False, indent=2, default=str)
        #         logger.info(f"Product Exposure 로그 저장 완료: {pe_filepath.resolve()} (로그 개수: {len(product_exposure_logs)})")
        #     else:
        #         logger.debug(f"SPM '{module_spm}'에 해당하는 Product Exposure 로그가 없어 별도 파일을 저장하지 않습니다.")
        # else:
        #     logger.debug(f"모듈 '{module_title}'의 SPM이 없어 Product Exposure 별도 저장을 건너뜁니다.")
    except Exception as e:
        logger.error(f"트래킹 로그 JSON 저장 중 오류 발생: {e}", exc_info=True)
