Feature: G마켓 SRP 트래킹 로그 정합성 검증
  검색 결과 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 검색 결과 페이지에서 카탈로그 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    And 검색 결과 페이지에 "<module_title>" 모듈이 있다
    When 사용자가 "<module_title>" 모듈 내 <n>번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | keyword    | n | module_title  | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 콜라        | 2 | 반복구매       | C1829286           | C1829287            | C1829288         | C1829289       |
      | 염색약      | 1 | 반복구매        | C1829286          | C1829290            | C1829291         | C1829292       |
      | 양말        | 1 | 반복구매        | C1829286          | C1829293            | C1829294         | C1829295       |
      | 양말        | 2 | 반복구매        | C1829286	        | C1829332            | C1829333         | C1829334       |
      | 물티슈      | 1 | 장바구니 모듈    | C1829277          | C1829278            | C1829279         |        |
      | 물티슈      | 1 | 장바구니VT      | C1829277           | C1829281            | C1829282         |        |
      | 물티슈      | 2 | 장바구니VT      | C1829277           | C1829283            | C1829284         |        |
