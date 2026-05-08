"""
로그인 계정 정보 관리
.env 파일에서 회원 종류별 계정 정보를 읽어옴
config.json의 환경 설정에 따라 dev/elsa와 stg/prod로 분기
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv  # type: ignore
from typing import Dict

# .env 파일 로드 (프로젝트 루트 기준)
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
# override=True: 기존 환경 변수를 .env 파일의 값으로 덮어씀
# verbose=True: 로드된 변수 정보 출력 (디버깅용)
load_dotenv(dotenv_path=env_path, override=True)


class MemberType:
    """회원 종류 상수"""
    NORMAL = "normal"  # 일반회원
    CLUB = "club"  # 클럽회원
    BUSINESS = "business"  # 사업자회원


def _load_config() -> Dict:
    """config.json 파일 로드"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_environment() -> str:
    """config.json에서 현재 환경 반환 (dev/stg/prod/elsa)"""
    config = _load_config()
    return config.get('environment', 'prod')


def _get_env_prefix() -> str:
    """
    환경에 따른 환경 변수 접두사 반환
    
    Returns:
        dev/elsa: "DEV_" (elsa는 mweb dev 계열 URL·계정과 동일하게 사용)
        stg/prod: "" (접두사 없음)
    """
    environment = _get_environment()
    
    # stg/prod는 하나의 분기로 처리 (접두사 없음)
    if environment in ('dev', 'elsa'):
        return "DEV_"
    elif environment in ['stg', 'prod']:
        return ""
    else:
        raise ValueError(f"지원하지 않는 환경입니다: {environment}. (dev/stg/prod/elsa)")


def get_credentials(member_type: str) -> Dict[str, str]:
    """
    회원 종류별 계정 정보 반환
    config.json의 환경 설정에 따라 dev/elsa와 stg/prod로 분기
    
    Args:
        member_type: 회원 종류 (normal/club/business)
    
    Returns:
        {"username": str, "password": str}
    
    Raises:
        ValueError: 회원 종류가 잘못되었거나 계정 정보가 없을 때
    """
    member_type_map = {
        MemberType.NORMAL: {
            "base_id_key": "NORMAL_MEMBER_ID",
            "base_password_key": "NORMAL_MEMBER_PASSWORD",
            "name": "일반회원"
        },
        MemberType.CLUB: {
            "base_id_key": "CLUB_MEMBER_ID",
            "base_password_key": "CLUB_MEMBER_PASSWORD",
            "name": "클럽회원"
        },
        MemberType.BUSINESS: {
            "base_id_key": "BUSINESS_MEMBER_ID",
            "base_password_key": "BUSINESS_MEMBER_PASSWORD",
            "name": "사업자회원"
        }
    }
    
    if member_type not in member_type_map:
        raise ValueError(f"지원하지 않는 회원 종류입니다: {member_type}. (normal/club/business)")
    
    # 환경에 따른 접두사 가져오기
    env_prefix = _get_env_prefix()
    environment = _get_environment()
    
    config = member_type_map[member_type]
    
    # 환경 변수 키 생성 (접두사 추가)
    id_key = f"{env_prefix}{config['base_id_key']}" if env_prefix else config['base_id_key']
    password_key = f"{env_prefix}{config['base_password_key']}" if env_prefix else config['base_password_key']
    
    # 환경 변수 다시 로드 (함수 호출 시점에 확실히 로드되도록)
    load_dotenv(dotenv_path=env_path, override=True)
    
    username = os.getenv(id_key)
    password = os.getenv(password_key)
    
    if not username or not password:
        # 디버깅: 실제로 어떤 키들이 있는지 확인
        all_env_keys = [k for k in os.environ.keys() if 'MEMBER' in k or 'NORMAL' in k]
        raise ValueError(
            f"{config['name']} 계정 정보가 .env 파일에 설정되지 않았습니다. "
            f"환경: {environment}, 키: {id_key}, {password_key}\n"
            f".env 파일 경로: {env_path}\n"
            f".env 파일 존재 여부: {env_path.exists()}\n"
            f"관련 환경 변수 키 목록: {all_env_keys}"
        )
    
    return {
        "username": username,
        "password": password
    }

