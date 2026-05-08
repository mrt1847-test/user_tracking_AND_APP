Feature: G마켓 PDP 트래킹 로그 정합성 검증
  상품 상세 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.
  
  Scenario: 상품 상세 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "<module_title>" 모듈 내 <n>번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)

    Examples:
      | goodscode  | module_title  | n | tc_module_exposure | tc_product_exposure | tc_product_click |
      | 8002304850 | pdpjfy         | 1 | C1228932           | C1228933            | C1228935         |
      | 8002304850 | pdpjfy         | 2 | C1228932           | C1228933            | C1228935         |
      | 8002304850 | pdpjfy         | 3 | C1228932           | C1228933            | C1228935         |
      | 8002304850 | pdpjfy         | 4 | C1228932           | C1228933            | C1228935         |