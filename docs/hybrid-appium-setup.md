# Android 하이브리드 앱 설정 가이드

이 문서는 `Appium + mitmproxy` 기반으로 Android 하이브리드 앱(WebView 포함) 테스트를 실행하기 위한 설정 절차를 정리합니다.

## 1) 사전 준비

- Python 3.11+
- Node.js + npm (Appium 서버용)
- Android SDK / `adb`
- Android Emulator 또는 디버그 가능한 실기기
- mitmproxy (`mitmdump`)
- OpenSSL (mitm CA 해시 계산용)

## 2) 의존성 설치

```bash
pip install -r requirements.txt
```

Appium 서버가 로컬에 없으면 설치:

```bash
npm install -g appium
```

## 3) APK 준비

- 테스트용 APK를 프로젝트 경로에 배치
- 기본 예시 경로: `apps/gmarket-debug.apk`

`config.json`의 `appium.app` 경로와 실제 파일 경로가 일치해야 합니다.

## 4) config.json 핵심 설정

하이브리드 앱 기준 필수/권장 값:

```json
{
  "runner_backend": "appium_hybrid_android",
  "automation_backend": "appium",
  "appium": {
    "server_url": "http://127.0.0.1:4723",
    "manage_server": true,
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Emulator",
    "app": "apps/gmarket-debug.apk",
    "appPackage": "com.ebay.kr.gmarket",
    "appActivity": "com.ebay.kr.gmarket.eBayKoreaGmarketActivity",
    "noReset": false,
    "autoGrantPermissions": true,
    "preferWebview": true,
    "webviewConnectTimeout": 15000
  },
  "proxy": {
    "backend": "mitmproxy",
    "listen_host": "127.0.0.1",
    "device_host": "10.0.2.2",
    "listen_port": 8081,
    "sslInsecure": true,
    "connectionStrategy": "lazy",
    "install_ca": true,
    "capture_domains": [
      "aplus.gmarket.co.kr",
      "aplus.gmarket.com"
    ]
  }
}
```

설정 포인트:

- `runner_backend`: 하이브리드 앱 전환 시 `appium_hybrid_android` 사용
- `appium.app`: APK 경로(하이브리드 모드에서는 사실상 필수)
- `noReset: false`: 매 실행 설치/초기화 정책 유지
- `proxy.device_host`: 에뮬레이터는 일반적으로 `10.0.2.2`
- `proxy.sslInsecure`: mitmproxy가 upstream 서버 인증서 검증에 막히지 않도록 `--ssl-insecure` 적용
- `proxy.connectionStrategy`: 필요 시 `lazy`로 조기 upstream 연결을 줄임

## 5) 로그인 셀렉터 설정 (`app_login`)

WebView 내부 DOM 기반으로 로그인하는 경우:

```json
{
  "app_login": {
    "enabled": true,
    "require_webview": true,
    "entry_selector": "a.link.link__myg",
    "username_selector": "#typeMemberInputId",
    "password_selector": "#typeMemberInputPassword",
    "submit_selector": "#btn_memberLogin",
    "success_selector": "text=로그아웃"
  }
}
```

앱 UI가 바뀌면 해당 selector를 우선 업데이트하세요.

## 6) 프록시/인증서 동작 방식

- `AppiumRuntime`이 실행 중 자동으로 다음 순서 수행:
  1. `mitmdump` 실행
  2. 단말 프록시 설정 적용
  3. mitm CA 설치(`install_ca=true`일 때)
  4. Appium 드라이버 생성 및 앱 실행
- 수집 로그 파일: `json/proxy_capture.jsonl`

## 7) 실행

```bash
python -m pytest -v test/dev/test_gemini.py
```

또는 전체:

```bash
python -m pytest -v test/prod/
```

## 8) 실패 시 점검 체크리스트

- `adb devices`에 디바이스가 보이는지
- `appium.server_url` 포트(기본 4723) 충돌 여부
- `appium.app` 경로가 실제 존재하는지
- 앱 실행 후 `WEBVIEW_*` 컨텍스트가 노출되는지 (`preferWebview`/`require_webview`)
- 프록시 캡처 파일(`json/proxy_capture.jsonl`)이 생성되는지
- 앱에 SSL pinning이 적용되어 프록시 복호화를 차단하지 않는지

## 9) 운영 권장 사항

- 초기 안정화는 에뮬레이터 1종 고정으로 진행
- TestRail/Sheets 연동은 기존 흐름을 유지하고, 수집부만 변경
- 시나리오별 캡처 로그를 별도 보관해 정합성 이슈 재현성을 확보
