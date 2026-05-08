Feature: G마켓 SRP 트래킹 로그 정합성 검증
  검색 결과 페이지에서 상품 클릭 시 트래킹 로그의 정합성을 검증합니다.

  Scenario: 검색 결과 페이지에서 정렬후 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    When 검색 결과 페이지에서 "<module_title>" 정렬을 적용한다
    Then 상품평 수 내림차순 정렬이 정합성 검증을 통과해야 함 (TC: <tc_review_sort>)

    Examples:
      | keyword          | module_title      | tc_review_sort |
      | 콜라            | 상품평 많은순       | C1418593       |
      | 생수            | 상품평 많은순     | C1418594      |
      | 라면              | 상품평 많은순       | C1418595      |

  Scenario: 검색 결과 페이지에서 신규 상품순 정렬후 상품 클릭 시 트래킹 로그 검증
    Given G마켓 홈 페이지에 접속했음
    And 네트워크 트래킹이 시작되었음
    When 사용자가 "<keyword>"을 검색한다
    Then 검색 결과 페이지가 표시된다
    Given 사용자가 "<keyword>"을 검색했다
    When 검색 결과 페이지에서 "<module_title>" 정렬을 적용한다
    Then goodscode 오름차순 정렬이 정합성 검증을 통과해야 함 (TC: <tc_review_sort>)

    Examples:
      | keyword          | module_title      | tc_review_sort |
      | 라면            | 신규 상품순       | C1418664       |
      | 생수            | 신규 상품순     | C1418665     |
      | 샴푸              | 신규 상품순       | C1418666      |

