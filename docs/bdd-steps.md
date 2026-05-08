# BDD 스텝 참조 (`steps/`)

pytest-bdd 기반 시나리오에서 사용하는 스텝 정의 모음이다. Feature 파일의 한글 문장이 아래 표의 **Gherkin 문구**와 매칭되며, 테스트 수집 시 `conftest` 등에서 이 패키지가 로드되어야 한다.

## 공통 사항

| 항목 | 설명 |
| --- | --- |
| Fixture | 대부분 `browser_session`, `bdd_context`를 사용한다. [`tracking_steps.py`](../steps/tracking_steps.py)의 네트워크 스텝은 `page`를 직접 받는다. |
| 소프트 실패 | 여러 스텝은 예외 대신 [`record_frontend_failure`](../utils/frontend_helpers.py)로 `frontend_action_failed` 등을 설정하고 시나리오를 이어 간다. |
| TestRail | 스텝 문자열에 **정합성 검증**이 포함되면 [`conftest.py`](../conftest.py)의 `pytest_bdd_after_step` 훅이 `validation_failed`·`validation_error_message`·`testrail_tc_id`를 참고해 결과를 기록한다. `(TC: C1234567)` 형태의 TC는 `tc_id` 등으로 추출된다. |
| TC 정규식 스텝 | [`tracking_validation_steps.py`](../steps/tracking_validation_steps.py) 및 정렬 검증 Then: `tc_id`가 비어 있으면 해당 검증을 건너뛴다. |

### 스텝이 아닌 헬퍼

[`tracking_validation_steps.py`](../steps/tracking_validation_steps.py) 내부의 `_check_and_validate_event_logs`, `_get_common_context`, `_save_tracking_logs` 는 Feature에서 직접 호출하지 않는다.

---

## [`login_steps.py`](../steps/login_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| Given | 사용자가 로그인되어 있다 | — | `user_is_logged_in` | |
| When | 사용자가 로그인 버튼을 클릭한다 | — | `user_clicks_login_button` | |
| When | 사용자가 "{member_type}"으로 로그인한다 | member_type | `user_logs_in_as_member_type` | |
| When | 사용자가 아이디 "{username}" 비밀번호 "{password}"로 로그인한다 | username, password | `user_logs_in_with_credentials` | |
| Then | 로그인이 완료되었다 | — | `login_is_completed` | |
| When | 사용자가 로그아웃한다 | — | `user_logs_out` | |
| Then | 로그아웃이 완료되었다 | — | `logout_is_completed` | |
| When | 사용자가 비회원으로 구매하기 버튼을 클릭한다 | — | `user_click_nonmember_button` | |
| Given | 사용자가 로그아웃되어 있다 | — | `user_is_logged_in` | Given "로그아웃" 과 구현 함수명이 동일 (`user_is_logged_in`) — 코드 기준 동작 확인 필요 |

---

## [`home_steps.py`](../steps/home_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| Given | 사용자가 G마켓 홈페이지에 접속한다 | — | `user_navigates_to_homepage` | |
| Given | G마켓 홈 페이지에 접속했음 | — | `given_gmarket_home_page_accessed` | `request` 사용 |
| Then | 홈페이지가 표시된다 | — | `homepage_is_displayed` | |
| Given | 브라우저가 실행되었다 | — | `browser_is_launched` | |
| Then | 페이지가 로드되었다 | — | `page_is_loaded` | |
| Given | 최근 본 내역이 존재한다 | — | `recent_viewed_exists` | 소프트 실패 가능 |
| When | 사용자가 RVH 페이지로 이동한다 | — | `add_product_to_cart` | 함수명·When 문구 불일치(레거시) |
| Then | RVH으로 이동했다 | — | `cart_page_is_displayed` | 함수명·Then 문구 불일치(레거시) |
| When | 사용자가 최근본 상품을 확인하고 클릭한다 | — | `click_recently_viewed_product` | |

---

## [`srp_lp_steps.py`](../steps/srp_lp_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| When | 사용자가 "{keyword}"을 검색한다 | keyword | `when_user_searches_keyword` | 소프트 실패 |
| Then | 검색 결과 페이지가 표시된다 | — | `then_search_results_page_is_displayed` | 소프트 실패 |
| Given | 사용자가 "{keyword}"을 검색했다 | keyword | `given_user_searched_keyword` | 소프트 실패 |
| Given | 검색 결과 페이지에 "{module_title}" 모듈이 있다 | module_title | `module_exists_in_search_results` | `request`, skip_reason 등 |
| When | 사용자가"{keyword}""{goodscode}" 최상단 클릭아이템 모듈 패이지로 이동한다 | keyword, goodscode | `user_goes_to_top_search_module_page` | Feature 문구에 공백 없음(의도적) |
| When | 사용자가 "{module_title}" 모듈 내 {nth:d}번째 상품을 확인하고 클릭한다 | module_title, nth | `user_confirms_and_clicks_product_in_module` | |
| When | 사용자가 "{module_title}" 모듈 내 {nth:d}번째 상품을 확인하고 클릭한다 (type2) | module_title, nth | `user_confirms_and_clicks_product_in_module_type2` | |
| When | 사용자가 카테고리 아이디 "{category_id}" 로 이동한다 | category_id | `when_user_goes_to_category` | LP |
| Given | 사용자가 카테고리 아이디 "{category_id}" 로 이동했다 | category_id | `given_user_went_to_category` | |
| Then | 리스트 페이지가 표시된다 | — | `then_list_page_is_displayed` | |
| Then | 상품 페이지로 이동되었다 | — | `product_page_is_opened` | goodscode 기반 URL |
| Given | 더보기 버튼을 클릭한다 | — | `click_more_button` | Decorator는 Given, 동작은 클릭 |
| When | 검색 결과 페이지에서 "{sort_option}" 정렬을 선택한다 | sort_option | `select_sort_option` | `selected_sort_option` 저장 |
| When | 사용자가 "{filter_name}" 필터 {nth:d}번째를 적용한다 | filter_name, nth | `select_filter` | |
| When | 검색 결과 페이지에서 "{sort_option}" 정렬을 적용한다 | sort_option | `apply_sort_option` | 내부에서 `select_sort_option` 호출 |
| Then | `상품평 수 내림차순 정렬이 정합성 검증을 통과해야 함 (TC: (?P<tc_id>.*))` | tc_id (`parsers.re`) | `then_review_counts_descending_should_pass_validation` | `browser_session` 필요, `validation_*`, TestRail |
| Then | `goodscode 오름차순 정렬이 정합성 검증을 통과해야 함 (TC: (?P<tc_id>.*))` | tc_id (`parsers.re`) | `then_goodcodes_ascending_should_pass_validation` | **비고:** Gherkin은 "오름차순" 이지만 구현은 **엄격 goodscode 내림차순**(이전 &gt; 다음, `curr >= prev` 시 위반). |

---

## [`product_steps.py`](../steps/product_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| Given | 상품 "{goodscode}"의 상세페이지로 접속했음 | goodscode | `go_to_product_page` | |
| Then | 상품 상세 페이지가 표시된다 | — | `product_detail_page_is_displayed` | |
| Given | 상품 상세 페이지가 표시된다 | — | `product_detail_page_is_displayed_given` | |
| Then | 상품 페이지로 이동되었다 | — | `product_page_is_opened` | |
| Then | 레이어 "{module_title}"가 출력되었다 | module_title | `product_page_is_opened` | 위 Then과 **함수명 동일** — 서로 다른 스텝 |
| When | 사용자가 구매하기 버튼을 클릭한다 | — | `user_clicks_buy_now_button` | |
| When | 사용자가 PDP에서 "{module_title}" 모듈 내 상품을 확인하고 클릭한다 | module_title | `user_confirms_and_clicks_product_in_pdp_module` | |
| When | 사용자가 PDP에서 "{location_title}"을 클릭한다 | location_title | `user_confirms_and_clicks_product_in_pdp_related_detail_module` | |
| When | 사용자가 PDP에서 "{button_title}" 버튼을 확인하고 클릭한다 | button_title | `user_confirms_and_clicks_product_in_pdp_related_module` | |
| Then | 버튼 "{module_title}"가 클릭되었다 | module_title | `other_page_is_opened` | |
| When | 사용자가 상품 옵션을 입력한다 | — | `user_inputs_product_option` | |
| When | 사용자가 BuyBox에서 "{module_title}" 모듈 내 상품을 확인하고 클릭한다 | module_title | `user_confirms_and_clicks_product_in_BuyBox_module` | |
| When | 사용자가 PDP에서 "{module_title}" 모듈 내 {n}번째 상품을 확인하고 클릭한다 | module_title, n | `user_confirms_and_clicks_product_in_pdp_module` | **비고:** 바로 위 When과 **Python 함수명이 동일**. 후행 정의가 이름 공간을 덮어쓰므로 유지보수 시 함수명 분리 권장. |

---

## [`cart_steps.py`](../steps/cart_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| Given | 장바구니 비우기 | — | `clear_cart` | 소프트 실패 |
| When | 사용자가 "{goodscode}" 상품을 장바구니에 추가한다 | goodscode | `add_product_to_cart` | |
| When | 사용자가 장바구니 페이지로 이동한다 | — | `add_product_to_cart` | 함수명 동일(다른 스텝) |
| Then | 장바구니 페이지가 표시된다 | — | `cart_page_is_displayed` | |
| Given | 장바구니 페이지에 "{module_title}" 모듈이 있다 | module_title | `cart_page_has_module` | |
| When | 사용자가 "{module_title}" 장바구니 모듈 내 상품을 확인하고 클릭한다 | module_title | `clicks_product_in_cart_module` | |
| Given | 이전페이지로 이동해서 장바구니 페이지로 이동 | — | `goes_back_to_previous_page` | |
| When | 모듈 내 장바구니 버튼 클릭 | — | `clicks_cart_button_in_module` | |
| Then | 장바구니 담기 완료되었다 | — | `cart_added_successfully` | |

---

## [`order_steps.py`](../steps/order_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| When | 장바구니 번호 "{cart_num}" 인 주문완료 페이지에 접속했음 | cart_num | `goes_to_order_complete_page` | |
| Then | 주문완료 페이지가 표시된다 | — | `order_complete_page_is_displayed` | |
| Given | 주문완료 페이지에 "{module_title}" 모듈이 있다 | module_title | `module_exists_in_order_complete_page` | |
| When | 사용자가 "{module_title}" 모듈 내 상품을 확인하고 옵션선택을 클릭한다 | module_title | `user_confirms_and_clicks_product_in_module` | |
| When | 사용자가 "{module_title}" 모듈 내 상품을 확인하고 상품을 클릭한다 | module_title | `user_confirms_and_clicks_product_in_module_click` | |

---

## [`my_steps.py`](../steps/my_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| When | 사용자가 My 페이지 주문내역으로 이동한다 | — | `when_user_goes_to_my_order_history` | |
| Then | 주문내역으로 이동했다 | — | `then_order_history_page_is_displayed` | |
| Given | 주문내역이 존재한다 | — | `given_order_history_has_items` | |
| When | 사용자가 "{module_title}" 내 상품을 확인하고 클릭한다 | module_title | `when_user_confirms_and_clicks_product_in_order_history` | |

---

## [`tracking_steps.py`](../steps/tracking_steps.py)

| 유형 | Gherkin 문구(템플릿) | 파라미터 | 구현 함수 | 비고 |
| --- | --- | --- | --- | --- |
| Given | 네트워크 트래킹이 시작되었음 | — | `given_network_tracking_started` | `page`, `bdd_context` |
| When | 네트워크 요청이 완료될 때까지 대기함 | — | `when_wait_for_network_request_completion` | 인자 없음 |
| When | 네트워크 트래킹을 중지함 | — | `when_stop_network_tracking` | |

---

## [`tracking_validation_steps.py`](../steps/tracking_validation_steps.py)

공통: TC가 있는 Then은 `_check_and_validate_event_logs`(또는 PV 단독 로직)로 `module_config`/수집 로그를 검증하고, `bdd_context['testrail_tc_id']`·`validation_failed` 등을 설정한다.

| 유형 | Gherkin / 패턴 | 파라미터 | 구현 함수 |
| --- | --- | --- | --- |
| Then | PV 로그가 정합성 검증을 통과해야 함 | — | `then_pv_logs_should_pass_validation` |
| Then | `… PDP PV 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_pv_logs_should_pass_validation` |
| Then | `… Module Exposure 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_module_exposure_logs_should_pass_validation` |
| Then | `… Product Exposure 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_product_exposure_logs_should_pass_validation` |
| Then | `… Product Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_product_click_logs_should_pass_validation` |
| Then | `… Product ATC Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_product_atc_click_logs_should_pass_validation` |
| Then | `… Product Minidetail 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_product_minidetail_logs_should_pass_validation` |
| Then | `… PDP Buynow Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_buynow_click_logs_should_pass_validation` |
| Then | `… PDP ATC Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_atc_click_logs_should_pass_validation` |
| Then | `… PDP Gift Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_gift_click_logs_should_pass_validation` |
| Then | `… PDP Join Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_join_click_logs_should_pass_validation` |
| Then | `… PDP Rental Click 로그가 정합성 검증을 통과해야 함 (TC: …)` | tc_id | `then_pdp_rental_click_logs_should_pass_validation` |
| Then | 모든 트래킹 로그를 JSON 파일로 저장함 | — | `then_save_all_tracking_logs_to_json` |
| Then | 모든 로그 검증이 완료되었음 | — | `then_all_validations_completed` | 누적 오류 시 AssertionError |

정규식 Then의 전체 패턴은 소스의 `parsers.re(r'…')`와 동일하며, 예시는 다음과 같다:  
`PDP PV 로그가 정합성 검증을 통과해야 함 (TC: <tc_id>)`

---

## [`checkout_steps.py`](../steps/checkout_steps.py)

현재 스텝 정의 없음. Checkout용 placeholder 파일이다.

---

## 스텝 개수 점검 (요약)

`steps/*.py`에서 `@given` / `@when` / `@then` 데코레이터 줄을 집계한 값이다.

| 파일 | 개수 |
| --- | ---: |
| login_steps.py | 9 |
| home_steps.py | 9 |
| srp_lp_steps.py | 17 |
| product_steps.py | 13 |
| cart_steps.py | 9 |
| order_steps.py | 5 |
| my_steps.py | 4 |
| tracking_steps.py | 3 |
| tracking_validation_steps.py | 14 |
| **합계** | **83** |

`checkout_steps.py`, `__init__.py` 는 스텝 0.
