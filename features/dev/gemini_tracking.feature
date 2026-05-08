Feature: G마켓 SRP 트래킹 로그 정합성 검증
  검색 결과 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 검색 결과 페이지에서 카탈로그 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    And 검색 결과 페이지에 "<module_title>" 모듈이 있다
    When 사용자가 "<module_title>" 모듈 내 1번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | keyword          | module_title      | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 생수            | 카탈로그 그룹형     | C1413652           | C1413653            | C1413654         | C1413655       |
      | 냉장고            | 카탈로그 속성형     | C1413645           | C1413646            | C1413647         | C1413648       |
      | 물티슈            | 카탈로그 일반형     | C1413606           | C1413607            | C1413608         | C1413609       |

  Scenario: 검색 결과 페이지에서 카탈로그 모듈별 더보기 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    And 검색 결과 페이지에 "<module_title>" 모듈이 있다
    And 더보기 버튼을 클릭한다
    When 사용자가 "<module_title>" 모듈 내 6번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | keyword          | module_title      | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 라면             | 카탈로그 그룹형     | C1228846           | C1413656            | C1413657         | C1413658       |
      | 밥솥            | 카탈로그 속성형     | C1228846           | C1413649            | C1413650         | C1413651       |
      | 물티슈            | 카탈로그 일반형     | C1228846           | C1413642            | C1413643         | C1413644       |





  Scenario: 검색 결과 페이지에서 정렬후 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    When 검색 결과 페이지에서 "<module_title>" 정렬을 선택한다
    When 사용자가 "<module_title>" 모듈 내 1번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | keyword          | module_title      | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 물티슈            | 판매 인기순     | C1228806           | C1413736            | C1413753         | C1413754       |
      | 물티슈            | 상품평 많은순     | C1228806           | C1413755            | C1413756         | C1413757       |
      | 샴푸            | 신규 상품순     | C1228902           | C1413758            | C1413759         | C1413760       |

  Scenario: 검색 결과 페이지에서 정렬후 필터적용시시 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    When 검색 결과 페이지에서 "<module_title>" 정렬을 선택한다
    And 사용자가 "다이나믹 필터" 필터 1번째를 적용한다
    When 사용자가 "<module_title>" 모듈 내 <n>번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)

    Examples:
      | keyword          | module_title   | n | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 물티슈            | 판매 인기순     | 2 | C1228806           | C1413761            | C1413762         | C1413763       |
      | 물티슈            | 상품평 많은순   | 2 | C1228846           | C1413764            | C1413765         | C1413766       |
      | 샴푸            | 신규 상품순     | 2 | C1228902           | C1413767            | C1413768         | C1413769       |

     