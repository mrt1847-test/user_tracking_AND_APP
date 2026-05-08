Feature: G마켓 PDP 트래킹 로그 정합성 검증
  상품 상세 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.
  
  Scenario: 상품 상세 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "<module_title>" 모듈 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)
        
    Examples:
      | goodscode  | module_title                | tc_module_exposure | tc_product_exposure | tc_product_click | tc_atc_click   |
      | 4448231882 | 함께 보면 좋은 상품이에요       | C1228932           | C1228933            | C1228935         |               |
      | 4448231882 | 함께 구매하면 좋은 상품이에요   | C1228936           | C1228937            | C1228939         |                |
      | 4448231882 | 이 판매자의 인기상품이에요      | C1228944           | C1228945            | C1228947         |                |
      | 2522715372 | 이마트몰VT                   | C1228951           | C1228952            | C1228954         | C1228955       |
      | 2522715372 | 이마트몰BT                   | C1228957           | C1228958            | C1228960         | C1228961       |
      | 2522715372 | 이 브랜드의 인기상품           | C1228963           | C1228964            | C1228966         | C1228967       |  
      | 2522715372 | 점포 행사 상품이에요           | C1228969           | C1228970            | C1228972         | C1228973       |
      | 4457587710 | BuyBox                      | C1228940           | C1228941            | C1228943         |                |
      
  
  Scenario: 상품 상세 페이지에서 그룹 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "<module_title>" 모듈 내 상품을 확인하고 클릭한다
    Then 레이어 "연관상품 상세보기"가 출력되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    
    Examples:
      | goodscode  | module_title                | tc_module_exposure | tc_product_exposure | tc_product_click |
      | 3039555146 | 연관상품                     | C1228975           | C1228976            | C1228978         |


  Scenario: 그룹 연관상품 상세보기 페이지에서 연관 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "<location_title>"을 클릭한다
    And 사용자가 PDP에서 "<module_title>" 모듈 내 상품을 확인하고 클릭한다
    Then 레이어 "연관상품 상세보기"가 출력되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
    
    Examples:
      | goodscode  | location_title     | module_title     | tc_module_exposure | tc_product_exposure | tc_product_click |
      | 3039555146 | 연관상품 더보기 버튼 | 연관상품 더보기   | C1228979           | C1228980            | C1228982         |
      | 3039555146 | 연관상품            | 연관상품 상세보기 |                    | C1228983            | C1228984         |


  Scenario: 그룹 상품 상세 페이지에서 버튼 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "연관상품"을 클릭한다
    And 사용자가 PDP에서 "<location_title>"을 클릭한다
    And 사용자가 상품 옵션을 입력한다
    And 사용자가 PDP에서 "<module_title>" 버튼을 확인하고 클릭한다
    Then 버튼 "<module_title>"가 클릭되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    And PDP Buynow Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_buynow_click>)
    And PDP ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)
    And PDP Gift Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_gift_click>)

    Examples:
      | goodscode  | location_title | module_title     | tc_buynow_click | tc_atc_click | tc_gift_click |
      | 4457587710 | 구매하기        | 연관상품 구매하기 | C1228987        |              |               |
      | 4457587710 | 구매하기        | 연관상품 장바구니 |                 | C1228986     |               |
      | 4457587710 | 선물하기        | 연관상품 선물하기 |                 |              | C1228985      |


  Scenario: 상품 상세 페이지에서 버튼 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "<goodscode>"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "<location_title>"을 클릭한다
    And 사용자가 상품 옵션을 입력한다
    And 사용자가 PDP에서 "<module_title>" 버튼을 확인하고 클릭한다
    Then 버튼 "<module_title>"가 클릭되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    And PDP Buynow Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_buynow_click>)
    And PDP ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)
    And PDP Gift Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_gift_click>)
    And PDP Rental Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_rental_click>)
    And PDP Join Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_join_click>)
    
    Examples:
      | goodscode  | location_title | module_title     | tc_buynow_click | tc_atc_click | tc_gift_click | tc_rental_click | tc_join_click |
      | 4448231882 | 구매하기        | 일반상품 구매하기 | C1228950        |              |               |                 |               |
      | 4448231882 | 구매하기        | 일반상품 장바구니 |                 | C1228949     |               |                 |               |
      | 4448231882 | 선물하기        | 일반상품 선물하기 |                 |              | C1228948      |                 |               |
      | 2698619898 | 상담 신청하기   | 상담신청          |                 |              |               | C1228988        |               |
      | 2529094051 | 가입 신청하기   | 가입신청          |                 |              |               |                 | C1228989      |


  Scenario: BuyBox 페이지에서 모듈 내 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 상품 "4457587710"의 상세페이지로 접속했음
    When 사용자가 PDP에서 "가격 비교하기"을 클릭한다
    And 사용자가 BuyBox에서 "낮은가격순" 모듈 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1228990)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1228991)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1228993)