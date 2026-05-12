# User Tracking Automation MWeb

G마켓 Android 하이브리드 앱(WebView 포함)의 사용자 트래킹 로그를 수집하고, BDD 시나리오 기준으로 기대 스키마와 정합성을 검증하는 테스트 자동화 프로젝트입니다.

`pytest-bdd`와 Appium(Android + APK)을 사용해 실제 하이브리드 앱 흐름을 실행하고, mitmproxy로 캡처한 `aplus.gmarket.co.kr` / `aplus.gmarket.com` POST 요청을 이벤트 타입별로 분류해 검증합니다.

## 목차

- [주요 기능](#주요-기능)
- [프로젝트 구조](#프로젝트-구조)
- [설치](#설치)
- [실행](#실행)
- [환경 설정](#환경-설정)
- [트래킹 스키마](#트래킹-스키마)
- [주요 컴포넌트](#주요-컴포넌트)
- [Google Sheets 연동](#google-sheets-연동)
- [TestRail 연동](#testrail-연동)
- [문제 해결](#문제-해결)
- [하이브리드 앱 셋업 가이드](docs/hybrid-appium-setup.md)

## 주요 기능

1. **BDD 기반 시나리오 실행**
   - `features/dev`, `features/prod` 아래의 Gherkin feature 파일 실행
   - `test/dev`, `test/prod`의 pytest 로더가 각 feature 파일을 연결
   - 공통 step definition은 `steps/`에 분리

2. **하이브리드 앱 자동화**
   - Appium(Android UiAutomator2) 기반 실행
   - 매 실행 APK 설치(`appium.app`) 후 앱 시작
   - `config.json`의 `mobile_profile`로 모바일 뷰포트와 User-Agent 선택
   - 현재 지원 프로필: `iphone`, `galaxy_s20`
   - 세션 시작 시 Appium 세션 로그인 수행

3. **네트워크 트래킹 로그 수집**
   - mitmproxy + `utils/mitm_capture_addon.py`로 POST 요청 수집
   - `aplus.gmarket.co.kr`, `aplus.gmarket.com` 도메인 요청 감지
   - `utLogMap`, `params-exp`, `params-clk`, `gokey` 등 주요 payload 디코딩
   - 새 탭/새 페이지 전환 시에도 `BrowserSession`으로 active page 추적

4. **이벤트 타입별 정합성 검증**
   - 모듈별 JSON 스키마와 실제 로그 비교
   - 상품번호, 검색어, 가격, 환경 값 등 플레이스홀더 자동 치환
   - `mandatory`, `skip`, 빈 문자열, 리스트 OR 조건 지원

5. **외부 도구 연동**
   - TestRail Run 생성/재사용, step 결과 기록, 실패 스크린샷 첨부
   - Google Sheets와 `tracking_schemas/` JSON 간 변환
   - `tracking_all_*.json` 로그를 스키마 생성용 시트로 역변환

## 프로젝트 구조

```text
user_tracking_automation_mweb/
├── features/
│   ├── dev/                         # 개발/검증용 feature
│   │   ├── gemini_tracking.feature
│   │   ├── gemini2_tracking.feature
│   │   ├── gemini_sort_tracking.feature
│   │   ├── kotlin_tracking.feature
│   │   └── pdpjfy_tracking.feature
│   └── prod/                        # 운영 시나리오 feature
│       ├── cart_tracking.feature
│       ├── lp_tracking.feature
│       ├── my_tracking.feature
│       ├── order_complete_tracking.feature
│       ├── pdp_tracking.feature
│       ├── pdp_tracking2.feature
│       ├── rvh_tracking.feature
│       ├── srp_tracking.feature
│       └── srp_tracking2.feature
├── test/
│   ├── dev/                         # dev feature pytest 로더
│   │   ├── test_gemini.py
│   │   ├── test_jfy.py
│   │   └── test_kotlin.py
│   └── prod/                        # prod feature pytest 로더
│       ├── test_cart.py
│       ├── test_home.py
│       ├── test_lp.py
│       ├── test_my.py
│       ├── test_order.py
│       ├── test_pdp.py
│       └── test_srp.py
├── steps/                           # pytest-bdd step definitions
├── pages/                           # Mobile Web Page Object Model
├── utils/                           # 트래킹, 검증, URL, 인증, 시트 유틸
├── scripts/
│   ├── json_to_sheets.py            # tracking_all/schema JSON -> Google Sheets
│   ├── sheets_to_json.py            # Google Sheets -> tracking_schemas JSON
│   └── compare_config_tracking.py   # 로그와 스키마 필드 비교 보조
├── tracking_schemas/
│   ├── CART/
│   ├── GEMINI/
│   ├── HOME/
│   ├── JFY/
│   ├── KOTLIN/
│   ├── LP/
│   ├── MY/
│   ├── ORDER/
│   ├── PDP/
│   ├── SRP/
│   └── schema_template.json         # 시트/스키마 생성 기준 템플릿
├── json/                            # 실행 중 저장되는 tracking_all 등 로그
├── docs/
│   └── bdd-steps.md
├── conftest.py                      # fixtures, 로그인, 브라우저, TestRail 훅
├── config.json                      # 실행 환경, TestRail, Sheets 설정
├── pytest.ini
├── requirements.txt
├── Pipfile / Pipfile.lock
└── state.json                       # 실행 시 생성/갱신되는 로그인 상태
```

## 설치

### 필수 요구사항

- Python 3.11 권장 (`Pipfile` 기준)
- Android Emulator 또는 실기기(adb 연결)
- Appium Server
- mitmproxy(mitmdump), adb, openssl

### pip 사용

```bash
pip install -r requirements.txt
```

### pipenv 사용

```bash
pipenv install
```

## 실행

테스트는 `test/prod/` 또는 `test/dev/` 아래의 pytest 로더로 실행합니다.

현재 pytest 로더와 feature 매핑:

| pytest 로더 | 연결된 feature |
| --- | --- |
| `test/prod/test_srp.py` | `features/prod/srp_tracking.feature` |
| `test/prod/test_lp.py` | `features/prod/lp_tracking.feature` |
| `test/prod/test_pdp.py` | `features/prod/pdp_tracking.feature` |
| `test/prod/test_cart.py` | `features/prod/cart_tracking.feature` |
| `test/prod/test_my.py` | `features/prod/my_tracking.feature` |
| `test/prod/test_order.py` | `features/prod/order_complete_tracking.feature` |
| `test/prod/test_home.py` | `features/prod/rvh_tracking.feature` |
| `test/dev/test_kotlin.py` | `features/dev/kotlin_tracking.feature` |
| `test/dev/test_gemini.py` | `features/dev/gemini2_tracking.feature` |
| `test/dev/test_jfy.py` | `features/dev/pdpjfy_tracking.feature` |

`features/` 안에 있는 다른 feature 파일은 보관/추가 시나리오이며, 실행하려면 별도 pytest 로더를 추가하거나 기존 로더의 `scenarios(...)` 경로를 바꿔야 합니다.

```bash
# prod 전체 실행
pytest test/prod/ -v

# prod 특정 영역 실행
pytest test/prod/test_srp.py -v
pytest test/prod/test_pdp.py -v
pytest test/prod/test_cart.py -v

# dev 특정 시나리오 실행
pytest test/dev/test_kotlin.py -v
pytest test/dev/test_gemini.py -v
pytest test/dev/test_jfy.py -v

# 캐시 제거 후 실행
pytest --cache-clear test/dev/test_kotlin.py -v
```

pipenv 환경에서는 앞에 `pipenv run`을 붙이면 됩니다.

```bash
pipenv run pytest test/prod/ -v
pipenv run pytest --cache-clear test/dev/test_kotlin.py -v
```

로그를 파일로 함께 남기려면 Windows PowerShell에서는 `Tee-Object`를 사용합니다.

```powershell
pipenv run pytest test/prod/ -v *>&1 | Tee-Object -FilePath pytest.log
pipenv run pytest --cache-clear test/dev/test_kotlin.py -v *>&1 | Tee-Object -FilePath pytest_kotlin.log
```

## 환경 설정

### `.env`

프로젝트 루트에 `.env` 파일을 두고 계정 및 TestRail 인증 정보를 설정합니다. 실제 계정 정보는 저장소에 커밋하지 않습니다.

```env
# TestRail: config.json의 testrail_report가 "Y"일 때 필요
TESTRAIL_USERNAME=<TestRail_ID_or_email>
TESTRAIL_PASSWORD=<TestRail_API_key_or_password>

# stg/prod 일반 회원
NORMAL_MEMBER_ID=<member_id>
NORMAL_MEMBER_PASSWORD=<member_password>

# dev 일반 회원
DEV_NORMAL_MEMBER_ID=<dev_member_id>
DEV_NORMAL_MEMBER_PASSWORD=<dev_member_password>

# 필요 시 회원 타입별 계정
CLUB_MEMBER_ID=<club_member_id>
CLUB_MEMBER_PASSWORD=<club_member_password>
BUSINESS_MEMBER_ID=<business_member_id>
BUSINESS_MEMBER_PASSWORD=<business_member_password>
```

현재 `utils/credentials.py`는 로그인 계정 접두사를 `dev`와 `stg/prod` 기준으로 분기합니다. `environment`를 `elsa`로 사용하는 경우 URL은 지원되지만, 로그인 계정 분기는 별도 보완이 필요할 수 있습니다.

### `config.json`

`config.json`은 실행 환경, 모바일 프로필, TestRail, Google Sheets 설정을 관리합니다.

주요 키:

- `environment`: 실행 환경. URL 기준으로 `dev`, `stg`, `prod`, `elsa` 지원
- `runner_backend`: 실행 백엔드. `appium_hybrid_android`(권장) 또는 `appium_android`/`appium`
- `mobile_profile`: 모바일 에뮬레이션. `iphone` 또는 `galaxy_s20`
- `appium`: Appium 서버/디바이스/APK/앱 액티비티 설정
- `proxy`: mitmproxy 수집 설정(`listen_host`, `listen_port`, `capture_domains`, `sslInsecure`, `ignoreHosts`)
- `testrail_report`: TestRail 기록 여부. `"Y"` / `"N"`
- `testrail_run_name`: 새 Run 이름. `{datetime}` 치환 가능
- `testrail_run_create`: `true`면 새 Run 생성, `false`면 기존 Run 사용
- `testrail_run_id`: 기존 Run에 기록할 때 사용하는 Run ID
- `testrail_close_run_on_finish`: 세션 종료 시 새로 만든 Run 자동 종료 여부
- `project_id`, `suite_id`, `section_id`, `milestone_id`: TestRail 기본 설정
- `spreadsheet_id`: Google Sheets 문서 ID
- `kotlin`, `gemini` 등 스위트 블록: 실행 경로에 따라 TestRail ID를 오버레이

현재 기본 형태:

```json
{
  "testrail_report": "N",
  "testrail_run_name": "User Tracking Aoutomation Test-mweb {datetime}",
  "testrail_run_create": false,
  "testrail_run_id": "",
  "testrail_close_run_on_finish": "Y",
  "milestone_id": "",
  "project_id": "",
  "section_id": "",
  "suite_id": "",
  "kotlin": {
    "milestone_id": "1673",
    "project_id": "219",
    "section_id": "111257",
    "suite_id": "3582"
  },
  "gemini": {
    "milestone_id": "1671",
    "project_id": "222",
    "section_id": "111278",
    "suite_id": "3588"
  },
  "tr_url": "http://172.30.2.20",
  "multiple_test_use": false,
  "environment": "prod",
  "mobile_profile": "galaxy_s20",
  "spreadsheet_id": "1iv_ok0kTzWWPhzyRRbpEEnH3DPGE7VSJg2mmdlRPD78"
}
```

하이브리드 앱 실행 시 필수 권장값:

```json
{
  "runner_backend": "appium_hybrid_android",
  "appium": {
    "app": "apps/gmarket-debug.apk",
    "appPackage": "com.ebay.kr.gmarket",
    "appActivity": "com.ebay.kr.gmarket.eBayKoreaGmarketActivity",
    "noReset": false
  },
  "proxy": {
    "install_ca": true,
    "device_host": "10.0.2.2"
  }
}
```

TestRail 스위트 오버레이는 실행 경로에 `test_<스위트명>`이 포함되면 자동 적용됩니다. 더 세밀한 매칭이 필요하면 스위트 블록에 `path_markers`를 둘 수 있습니다.

```json
{
  "kotlin": {
    "path_markers": ["test/dev/test_kotlin.py", "kotlin_tracking"],
    "project_id": "219",
    "suite_id": "3582",
    "section_id": "111257",
    "milestone_id": "1673"
  }
}
```

## 트래킹 스키마

모듈별 기대값은 `tracking_schemas/<AREA>/<MODULE>.json`에 둡니다. `tracking_schemas/schema_template.json`은 Google Sheets 변환과 신규 스키마 생성 시 기준 구조로 사용됩니다.

지원 이벤트 섹션:

- `pv`
- `pdp_pv`
- `module_exposure`
- `product_exposure`
- `product_click`
- `product_atc_click`
- `product_minidetail`
- `general_exposure`
- `general_click`
- `pdp_buynow_click`
- `pdp_atc_click`
- `pdp_gift_click`
- `pdp_join_click`
- `pdp_rental_click`

주요 플레이스홀더:

- `<상품번호>`: 실제 상품번호
- `<검색어>`: 검색 키워드
- `<원가>`, `<할인가>`, `<쿠폰적용가>`: 화면 또는 payload에서 추출한 가격
- `<is_ad>`: 시나리오에서 채운 광고 여부
- `<trafficType>`: 트래픽 타입
- `<environment>`: `config.json`의 `environment`

특수 값:

- `"mandatory"`: 값이 반드시 있어야 함
- `"skip"`: 검증하지 않음
- `""`: 실제 값도 빈 문자열이어야 함
- `["A", "B"]`: 후보 중 하나와 일치하면 통과

모듈명이 같고 n번째 케이스를 분리해야 할 때는 `모듈명(n).json`을 사용할 수 있습니다. 검증 로직은 `nth`가 전달되면 `모듈명(n).json`을 먼저 찾고, 없으면 `모듈명.json`으로 폴백합니다.

## 주요 컴포넌트

### `conftest.py`

- Appium runtime, driver, `browser_session` fixture 관리
- 테스트 세션 시작 시 Appium 로그인 수행
- TestRail 설정 병합, Run 생성/재사용, step 결과 기록
- 실패 시 스크린샷 및 로그 첨부

### `utils/NetworkTracker.py`

네트워크 요청을 수집하고 이벤트 타입을 분류합니다.

주요 분류:

- `PV`, `PDP PV`
- `Module Exposure`, `Product Exposure`
- `Product Click`, `Product ATC Click`, `Product Minidetail`
- `General Exposure`, `General Click`
- `PDP Buynow Click`, `PDP ATC Click`, `PDP Gift Click`, `PDP Join Click`, `PDP Rental Click`

### `utils/validation_helpers.py`

- feature 경로에서 영역 추론
- 모듈 JSON 로드
- 기대값 생성 및 플레이스홀더 치환
- 이벤트 타입별 로그 필터링 및 정합성 검증

### `utils/urls.py`

`config.json`의 `environment`에 따라 mweb URL을 반환합니다.

- `base_url()`
- `search_url(keyword, spm=None)`
- `product_url(goodscode, spm=None)`
- `cart_url(spm=None)`
- `my_url(spm=None)`
- `list_url(category_id, spm=None)`
- `order_complete_url(pno, spm=None)`

## Google Sheets 연동

Google Sheets 연동에는 `config.json`의 `spreadsheet_id`와 서비스 계정 JSON 파일이 필요합니다. 현재 프로젝트 루트의 `python-link-test-380006-2868d392d217.json` 형식의 서비스 계정 파일을 사용하는 흐름입니다.

### 네이티브 h-ut와 `json/` 산출

Android 네이티브 트래킹은 로컬 큐에 쌓였다가 `h-ut.gmarket.co.kr/upload`로 gzip 배치 POST 됩니다. mitm은 **HTTP가 나간 뒤**만 캡처하므로, 아직 flush되지 않은 이벤트는 파일에 없습니다. `Then 모든 트래킹 로그를 JSON 파일로 저장함` 단계에서는 저장 직전 `sync_from_source()`로 `proxy_capture.jsonl`을 한 번 더 반영합니다.

- **`tracking_all_*.json`**: 루트가 이벤트 배열입니다. 네이티브에서 온 항목은 기존 aplus POST와 같은 형태로 맞춰 두었고, 출처 메타는 항목에 **`h_ut_capture`**(예: `parent_request_id`, `upload_timestamp`, `event_index`)로 붙을 수 있습니다.
- **`tracking_h_ut_pipeline_*.json`**: 같은 실행에서 h-ut JSONL 이벤트 줄 → 합성 aplus 적재 요약을 `h_ut_pipeline` 배열로 둡니다. `json_to_sheets.py`는 `tracking_all`만 대상으로 하므로, 시트 변환에는 넣지 않아도 됩니다.

### tracking_all JSON을 시트로 변환

```bash
python scripts/json_to_sheets.py \
  --input json/tracking_all_먼저_둘러보세요.json \
  --module "먼저 둘러보세요" \
  --area SRP
```

파일명이 `tracking_all_<모듈명>.json` 또는 `tracking_all_<모듈명>(숫자).json`이면 `--module`을 생략할 수 있습니다.

```bash
python scripts/json_to_sheets.py \
  --input "json/tracking_all_today_branddeal(1).json" \
  --area KOTLIN
```

PowerShell에서 괄호가 들어간 파일명은 따옴표로 감싸는 편이 안전합니다.

### 시트를 스키마 JSON으로 변환

```bash
# 단일 모듈 변환
python scripts/sheets_to_json.py \
  --module "먼저 둘러보세요" \
  --area SRP \
  --overwrite

# 영역 시트 전체를 모듈별 JSON으로 변환
python scripts/sheets_to_json.py \
  --sheet \
  --area KOTLIN \
  --overwrite
```

기본적으로 `schema_template.json`과 병합해 구조를 유지합니다. 시트 데이터만으로 생성하려면 `--no-structure-merge`를 사용합니다.

자세한 옵션:

```bash
python scripts/json_to_sheets.py --help
python scripts/sheets_to_json.py --help
```

## TestRail 연동

`config.json`의 `testrail_report`를 `"Y"`로 설정하면 TestRail 연동이 활성화됩니다.

동작 방식:

1. 세션 시작 시 `section_id` 및 하위 섹션의 TC를 조회
2. `testrail_run_create=true`면 새 Run 생성
3. `testrail_run_create=false`면 `testrail_run_id`의 기존 Run에 기록
4. BDD step에서 추출한 TC 번호에 결과 기록
5. 실패 시 스크린샷과 로그 첨부
6. 새로 만든 Run은 `testrail_close_run_on_finish=Y`일 때 종료

기존 Run 재사용 예시:

```json
{
  "testrail_report": "Y",
  "testrail_run_create": false,
  "testrail_run_id": "12345"
}
```

새 Run 생성 예시:

```json
{
  "testrail_report": "Y",
  "testrail_run_create": true,
  "testrail_run_id": "",
  "testrail_close_run_on_finish": "Y"
}
```

## 문제 해결

### 로그인 또는 Appium 세션 시작 실패

- `.env`에 현재 `environment`에 맞는 계정 키가 있는지 확인합니다.
- `dev`는 `DEV_NORMAL_MEMBER_ID`, `DEV_NORMAL_MEMBER_PASSWORD`를 우선 사용합니다.
- `stg`, `prod`는 `NORMAL_MEMBER_ID`, `NORMAL_MEMBER_PASSWORD`를 사용합니다.
- Appium 서버가 실행 중인지(`http://127.0.0.1:4723`) 확인합니다.
- `adb devices`로 디바이스가 정상 연결되었는지 확인합니다.

### 트래킹 로그가 수집되지 않음

- 시나리오에서 네트워크 트래킹 시작 step이 실행됐는지 확인합니다.
- `mitmdump`가 실행 가능한지 확인합니다.
- 단말에 mitmproxy 인증서가 설치되어 HTTPS 복호화가 가능한지 확인합니다.
- 요청 도메인이 `aplus.gmarket.co.kr`, `aplus.gmarket.com`, 또는 `h-ut.gmarket.co.kr/upload`인지 확인합니다.
- `h-ut.gmarket.co.kr/upload`에서 `Certificate verify failed: self-signed certificate in certificate chain`가 보이면 `proxy.sslInsecure: true`인지 확인합니다. 자동 실행되는 `mitmdump`에는 `--ssl-insecure`가 붙어야 합니다.
- `Client TLS handshake failed ... certificate unknown`가 캡처 대상이 아닌 Google/시스템 도메인에서 반복되면 `proxy.ignoreHosts`에 정규식(예: `^gmscompliance-pa\\.googleapis\\.com(:443)?$`)을 추가해 mitm TLS 가로채기를 우회합니다.
- 클릭/노출 후 충분한 대기 시간이 있는지 확인합니다.
- 새 탭으로 이동하는 흐름이면 `browser_session` active page가 전환됐는지 확인합니다.

### 정합성 검증 실패

- `tracking_schemas/<AREA>/<MODULE>.json`의 이벤트 섹션명이 실제 이벤트 타입과 맞는지 확인합니다.
- SPM 값이 실제 로그와 같은 depth로 잘려 있는지 확인합니다.
- 가격 필드는 클릭 전 화면에서 추출한 값과 payload 값이 다를 수 있어 `<원가>`, `<할인가>`, `<쿠폰적용가>` 치환 값을 확인합니다.
- 검증 대상이 아닌 동적 값은 `"skip"`으로 둡니다.
- 반드시 존재해야 하는 값은 `"mandatory"`를 사용합니다.

### Google Sheets 변환 실패

- 서비스 계정 JSON 파일이 프로젝트 루트에 있는지 확인합니다.
- Google Sheets 문서가 서비스 계정 이메일에 공유되어 있는지 확인합니다.
- `spreadsheet_id`가 올바른지 확인합니다.
- 괄호가 포함된 파일명은 PowerShell에서 따옴표로 감쌉니다.

### TestRail 기록 실패

- `TESTRAIL_USERNAME`, `TESTRAIL_PASSWORD`가 `.env`에 있는지 확인합니다.
- `tr_url`, `project_id`, `suite_id`, `section_id`, `milestone_id`가 실행 대상 스위트에 맞게 병합되는지 확인합니다.
- `testrail_run_create=false`인 경우 `testrail_run_id`는 비어 있으면 안 됩니다.

## 참고 파일

| 파일 | 역할 |
| --- | --- |
| `config.json` | 실행 환경, 모바일 프로필, TestRail, Sheets 설정 |
| `.env` | 계정 및 TestRail 인증 정보 |
| `conftest.py` | pytest fixture, 로그인 상태, TestRail 훅 |
| `utils/NetworkTracker.py` | 네트워크 로그 수집 및 이벤트 분류 |
| `utils/validation_helpers.py` | 스키마 로드, 기대값 생성, 정합성 검증 |
| `utils/urls.py` | 환경별 mweb URL |
| `utils/credentials.py` | 환경별 로그인 계정 로드 |
| `tracking_schemas/schema_template.json` | 스키마/시트 구조 템플릿 |
| `docs/bdd-steps.md` | BDD step 문서 |

## 라이선스

이 프로젝트는 내부 사용을 위한 자동화 프로젝트입니다.
