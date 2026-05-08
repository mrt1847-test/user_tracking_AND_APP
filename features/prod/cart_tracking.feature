Feature: G마켓 CART 트래킹 로그 정합성 검증
  CART 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: CART 페이지에서 장바구니 최저가 모듈 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    And 장바구니 비우기
    When 사용자가 "2763835829" 상품을 장바구니에 추가한다
    Then 장바구니 페이지가 표시된다
    Given 장바구니 페이지에 "장바구니 최저가" 모듈이 있다
    When 사용자가 "장바구니 최저가" 장바구니 모듈 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Given 이전페이지로 이동해서 장바구니 페이지로 이동
    When 모듈 내 장바구니 버튼 클릭
    Then 장바구니 담기 완료되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1228994)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1228995)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1228998)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: C1228997)

  Scenario: CART 페이지에서 장바구니 BT 모듈듈 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 장바구니 페이지로 이동한다
    Then 장바구니 페이지가 표시된다
    Given 장바구니 페이지에 "장바구니 BT" 모듈이 있다
    When 사용자가 "장바구니 BT" 장바구니 모듈 내 상품을 확인하고 클릭한다
    Then 상품 페이지로 이동되었다
    Given 이전페이지로 이동해서 장바구니 페이지로 이동
    When 모듈 내 장바구니 버튼 클릭
    Then 장바구니 담기 완료되었다
    Then 모든 트래킹 로그를 JSON 파일로 저장함
    Then Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1229000)
    And Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: C1229001)
    And Product Click 로그가 정합성 검증을 통과해야 함 (TC: C1229004)
    And Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: C1229003)

