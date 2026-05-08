"""
로그인 관련 Step Definitions
로그인 / 회원 상태
"""
from pytest_bdd import given, when, then, parsers
from pages.home_page import HomePage
from pages.login_page import LoginPage
from utils.credentials import MemberType
import logging

logger = logging.getLogger(__name__)


@given("사용자가 로그인되어 있다")
def user_is_logged_in(browser_session):
    """
    사용자가 로그인 상태인지 확인하고, 로그인되어 있지 않으면 로그인 수행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    
    # 이미 로그인되어 있는지 확인
    if not home_page.is_logged_in():
        logger.info("로그인되지 않음. 로그인 수행")
        home_page.click_login()
        
        # 로그인 페이지에서 로그인 수행 (기본: 일반회원)
        login_page = LoginPage(browser_session.page)
        login_page.login_as(MemberType.NORMAL)
        login_page.wait_for_login_complete()
    else:
        logger.info("이미 로그인되어 있음")


@when("사용자가 로그인 버튼을 클릭한다")
def user_clicks_login_button(browser_session):
    """
    사용자가 로그인 버튼 클릭
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    home_page.click_login()
    logger.info("로그인 버튼 클릭 완료")


@when(parsers.parse('사용자가 "{member_type}"으로 로그인한다'))
def user_logs_in_as_member_type(browser_session, member_type):
    """
    사용자가 회원 종류별로 로그인 (.env에서 계정 정보 읽어옴)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        member_type: 회원 종류 (일반회원/클럽회원/사업자회원)
    """
    # 회원 종류 매핑
    member_type_map = {
        "일반회원": MemberType.NORMAL,
        "클럽회원": MemberType.CLUB,
        "사업자회원": MemberType.BUSINESS
    }
    
    if member_type not in member_type_map:
        raise ValueError(f"지원하지 않는 회원 종류입니다: {member_type}. (일반회원/클럽회원/사업자회원)")
    
    login_page = LoginPage(browser_session.page)
    login_page.login_as(member_type_map[member_type])
    login_page.wait_for_login_complete()
    logger.info(f"{member_type}으로 로그인 완료")


@when(parsers.parse('사용자가 아이디 "{username}" 비밀번호 "{password}"로 로그인한다'))
def user_logs_in_with_credentials(browser_session, username, password):
    """
    사용자가 아이디와 비밀번호로 로그인 (Atomic POM 조합)
    직접 계정 정보를 입력하는 경우 사용
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        username: 사용자 아이디
        password: 비밀번호
    """
    login_page = LoginPage(browser_session.page)
    login_page.fill_username(username)
    login_page.fill_password(password)
    login_page.click_login_button()
    login_page.wait_for_login_complete()
    logger.info(f"로그인 완료: {username}")


@then("로그인이 완료되었다")
def login_is_completed(browser_session):
    """
    로그인이 성공적으로 완료되었는지 확인
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    login_page = LoginPage(browser_session.page)
    assert login_page.is_login_successful(), "로그인에 실패했습니다"
    logger.info("로그인 완료 확인")


@when("사용자가 로그아웃한다")
def user_logs_out(browser_session):
    """
    사용자가 로그아웃
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    home_page.click_logout()
    logger.info("로그아웃 완료")


@then("로그아웃이 완료되었다")
def logout_is_completed(browser_session):
    """
    로그아웃이 성공적으로 완료되었는지 확인
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    assert not home_page.is_logged_in(), "로그아웃에 실패했습니다"
    logger.info("로그아웃 완료 확인")


@when("사용자가 비회원으로 구매하기 버튼을 클릭한다")
def user_click_nonmember_button(browser_session):
    """
    사용자가 비회원으로 구매하기 버튼 클릭
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    actual_page = browser_session.page
    login_page = LoginPage(actual_page)
    actual_page.wait_for_load_state("networkidle")

    login_page.click_nonmember_button()
    logger.info("비회원으로 구매하기 버튼 클릭 완료")


@given("사용자가 로그아웃되어 있다")
def user_is_logged_in(browser_session):
    """
    사용자가 로그아웃 상태인지 확인하고, 로그인되어 있으면 로그아웃 수행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    
    # 이미 로그인되어 있는지 확인
    if home_page.is_logged_in():
        logger.info("로그인되어있음. 로그아웃 수행")
        home_page.click_logout()
        
    else:
        logger.info("이미 로그아웃되어 있음")