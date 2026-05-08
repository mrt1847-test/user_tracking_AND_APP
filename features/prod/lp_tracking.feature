Feature: G마켓 LP 트래킹 로그 정합성 검증
  LP 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 검색 결과 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 카테고리 아이디 "<category_id>" 로 이동한다
    Then 리스트 페이지가 표시된다
    Given 검색 결과 페이지에 "<module_title>" 모듈이 있다
    When 사용자가 "<module_title>" 모듈 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | category_id | module_title      | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click |
      | 200002934   | 먼저 둘러보세요     | C1228908           | C1228909            | C1228911         | C1228912     |
      | 200002934   | 인기 상품이에요     | C1228920           | C1228921            | C1228923         | C1228924     |
      | 200002934   | 스타배송           | C1228914           | C1228915            | C1228917         | C1228918     |
      | 200002934   | 일반상품           | C1228926           | C1228927            | C1228929         | C1228930     |
     