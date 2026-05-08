Feature: G마켓 Home 트래킹 로그 정합성 검증
  검색 결과 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 홈 섹션 모듈별 상품 클릭 시 트래킹 로그 검증
    Given 네트워크 트래킹이 시작되었음
    Given G마켓 홈 페이지에 접속했음
    When 사용자가 "<section_name>" 섹션으로 이동한다
    Then "<section_name>" 섹션으로 이동했다
    Given 섹션에 "<n>"번째 "<module_title>" 모듈이 있다
    When 홈에서 사용자가 "<n>"번째 "<module_title>" 모듈 내 <nth>번째 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)

    Examples:
      | section_name  | n | module_title        | nth | tc_module_exposure | tc_product_exposure | tc_product_click | 
      | 홈            | 1 | today_itemcarousel  | 1 | C1829145           | C1829146            | C1829147        | 
      | 홈            | 1 | today_newlowest     | 1 | C1829139           | C1829140            | C1829141         | 
      | 홈            | 1 | today_livedeal      | 1 | C1829151           | C1829152            | C1829153         | 
      | 홈            | 1 | today_shortsdeal    | 1 | C1829154           | C1829155            | C1829156         | 
      | 홈            | 1 | today_branddeal     | 1 | C1829142           | C1829143            | C1829144         | 
      | 홈            | 1 | today_hmjfy0        | 1 | C1829136           | C1829137            | C1829138         |
      | 홈            | 1 | today_campaign      | 1 | C1829148           | C1829149            | C1829150         | 
      | 홈            | 1 | today_brandspecial  | 1 | C1829142           | C1829143            | C1829144         | 
      | 슈퍼딜        | 1 | superdeal_campaign  | 1 | C1829148           | C1829149            | C1829150         | 
  
  Scenario: 홈 섹션 모듈별 General 트래킹 로그 검증
    Given 네트워크 트래킹이 시작되었음
    Given G마켓 홈 페이지에 접속했음
    When 사용자가 "<section_name>" 섹션으로 이동한다
    Then "<section_name>" 섹션으로 이동했다
    Given 섹션에 "<n>"번째 "<module_title>" 모듈이 있다
    When 홈에서 사용자가 "<n>"번째 "<module_title>" 모듈 내 General 요소를 클릭한다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then General Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_general_exposure>)
    And General Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_general_click>)

    Examples:
      | section_name  | n | module_title        | tc_general_exposure | tc_general_click | 
      | 홈            | 1 | today_itemcarousel  | C1829963            | C1829964        | 
      | 홈            | 1 | today_newlowest     | C1829965            | C1829966         | 
      | 홈            | 1 | today_hmjfy1        | C1857258            | C1857274         |
      | 홈            | 1 | today_campaign      | C1836147            | C1836284         | 
      | 슈퍼딜         | 1 | superdeal_campaign  | C1836147            | C1836284         | 

  
  
  Scenario: 홈 섹션 이동시 module exposure 트래킹 로그 검증
    Given 네트워크 트래킹이 시작되었음
    Given G마켓 홈 페이지에 접속했음
    When 사용자가 "<section_name>" 섹션으로 이동한다
    Then "<module_title>" 섹션으로 이동했다
    Then 페이지 로딩 대기
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)

    Examples:
      | section_name  | module_title     | tc_module_exposure |
      | 슈퍼딜         | 슈퍼딜            | 	C1829157          |
      | 이마트몰       | 이마트몰           | C1829158           | 
      | 베스트         | 베스트            | C1829159           | 
      | 스타배송       | 스타배송           | C1829160           | 
      | 뷰티           | 뷰티              | C1829161           |  

  
  
  