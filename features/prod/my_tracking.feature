Feature: G마켓 My 트래킹 로그 정합성 검증
  My 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: My 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 My 페이지 주문내역으로 이동한다
    Then 주문내역으로 이동했다
    Given 주문내역이 존재한다
    When 사용자가 "주문내역" 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1229013)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: 	C1229014)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1229017)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: C1229016)

