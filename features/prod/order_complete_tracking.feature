Feature: G마켓 주문완료 트래킹 로그 정합성 검증
  주문완료 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 주문완료 페이지에서 모듈별 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 장바구니 번호 "5460279163" 인 주문완료 페이지에 접속했음
    Then 주문완료 페이지가 표시된다
    Given 주문완료 페이지에 "주문완료 BT" 모듈이 있다
    When 사용자가 "주문완료 BT" 모듈 내 상품을 확인하고 상품을 클릭한다
    Then 상품 페이지로 이동되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1229007)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1229008)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1229011)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: C1229010)

  # Scenario: 주문완료 페이지에서 주문완료 BT 모듈에서서 옵션선택 클릭 시 트래킹 로그 검증
  #   Given G마켓 홈 페이지에 접속했음
  #   And 네트워크 트래킹이 시작되었음
  #   When 장바구니 번호 "5460279163" 인 주문완료 페이지에 접속했음
  #   Then 주문완료 페이지가 표시된다
  #   Given 주문완료 페이지에 "주문완료 BT" 모듈이 있다
  #   When 사용자가 "주문완료 BT" 모듈 내 상품을 확인하고 옵션선택을 클릭한다
  #   Then 상품 페이지로 이동되었다
  #   Then 모든 트래킹 로그를 JSON 파일로 저장함
  #   Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_module_exposure>)
  #   And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_exposure>)
  #   And Product Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_product_click>)
  #   And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: <tc_atc_click>)
