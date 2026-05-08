Feature: G마켓 RVH 트래킹 로그 정합성 검증
  RVH 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: RVH 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 RVH 페이지로 이동한다
    Then RVH으로 이동했다
    Given 최근 본 내역이 존재한다
    When 사용자가 최근본 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1229019)

