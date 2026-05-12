# 외부 런타임 설치/설정 가이드

이 문서는 `requirements.txt`로 설치되지 않는 외부 런타임(도구) 설치와 설정만 정리합니다.

대상:
- Appium Server (Node.js 생태계)
- Appium UiAutomator2 Driver (Appium 드라이버)
- Android SDK / Emulator / adb
- mitmproxy 인증서/프록시 관련 사전 작업

## 1) Python 의존성 vs 외부 런타임 구분

`requirements.txt`는 Python 패키지만 설치합니다.

이미 포함된 항목:
- `Appium-Python-Client`
- `selenium`
- `mitmproxy`

별도 설치가 필요한 항목:
- `appium` CLI/서버 (Node.js)
- `uiautomator2` 드라이버 (Appium 2 드라이버)
- Android Emulator/SDK/ADB (Android Studio 또는 Command-line tools)
- JDK + `JAVA_HOME` (Android Studio JBR 재활용 가능, APK 서명 검증용)

## 2) 필수 외부 도구 설치

### 2-1. Node.js 설치

- [Node.js LTS](https://nodejs.org/) 설치
- 설치 확인:

```bash
node -v
npm -v
```

### 2-2. Appium Server 설치

```bash
npm install -g appium
```

설치 확인:

```bash
appium -v
```

### 2-3. UiAutomator2 드라이버 설치 (Appium 2)

```bash
appium driver install uiautomator2
```

설치 확인:

```bash
appium driver list --installed
```

출력에 `uiautomator2`가 있어야 합니다.

### 2-4. JDK / JAVA_HOME 설정

UiAutomator2 드라이버는 APK 서명을 검증할 때 내부적으로 `apksigner`/`java.exe`를 호출합니다. `JAVA_HOME`이 비어 있으면 다음 에러가 발생합니다.

```
Cannot verify the signature of '...apk'. Original error:
The 'java.exe' binary could not be found neither in PATH nor under JAVA_HOME
(The JAVA_HOME environment variable is not set for the current process)
```

별도 JDK를 설치해도 되지만, **Android Studio에 번들된 JBR(JetBrains Runtime, OpenJDK 호환)** 을 그대로 사용하는 것이 가장 빠릅니다.

기본 경로 (Windows, Android Studio 정식 설치):

```
C:\Program Files\Android\Android Studio\jbr
```

영구 설정 (사용자 환경변수, 관리자 권한 불필요):

```powershell
setx JAVA_HOME "C:\Program Files\Android\Android Studio\jbr"
setx ANDROID_SDK_ROOT "C:\Users\<사용자>\AppData\Local\Android\Sdk"
```

> `setx`는 새로 여는 터미널부터 적용됩니다. 이미 열려 있는 PowerShell 창에는 반영되지 않으므로, 설정 후에는 새 창에서 테스트를 실행하세요.

같은 PowerShell 창에서 즉시 적용하려면:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_SDK_ROOT = 'C:\Users\<사용자>\AppData\Local\Android\Sdk'
```

설치/설정 확인:

```powershell
echo $env:JAVA_HOME
& "$env:JAVA_HOME\bin\java.exe" -version
```

> `appium-adb`는 `JAVA_HOME`이 잡혀 있으면 `%JAVA_HOME%\bin\java.exe`를 우선 사용하므로, `PATH`에 `bin`을 추가할 필요는 없습니다. 다른 도구와의 일관성이 필요하면 `PATH`에도 `%JAVA_HOME%\bin`을 추가하세요.

자동 점검 스크립트:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\probe_java.ps1
```

## 3) Android SDK / Emulator 준비

### 3-1. Android Studio 또는 SDK Command-line tools 설치

필수 구성:
- Android SDK Platform-tools (`adb`)
- Emulator
- 테스트 대상 API 레벨 시스템 이미지 (예: Android 16)

확인:

```bash
adb version
emulator -version
```

### 3-2. AVD 생성

예시 이름: `AOS16`

생성 후 확인:

```bash
emulator -list-avds
```

## 4) mitmproxy 사전 준비

### 4-1. mitmproxy 실행 가능 여부

```bash
mitmdump --version
```

### 4-2. CA 인증서 생성

아직 생성되지 않았다면 `mitmproxy` 또는 `mitmdump`를 1회 실행해 로컬 CA를 생성합니다.

기본 경로(Windows):
- `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.pem`

코드에서 이 인증서를 사용해 에뮬레이터에 설치를 시도합니다.

## 5) 프로젝트 설정과 맞춰야 할 항목

`config.json`에서 아래 항목을 환경과 일치시킵니다.

- `runner_backend`: `appium_hybrid_android` 권장
- `appium.server_url`: 기본 `http://127.0.0.1:4723`
- `appium.manage_server`: `true`면 테스트 시 Appium 자동 기동
- `appium.app`: APK 경로
- `appium.appPackage`, `appium.appActivity`
- `proxy.listen_host`, `proxy.listen_port`
- `proxy.device_host`

주의:
- 포트(`8080`/`8081`)는 팀 내에서 하나로 통일하세요.
- 수동 실행 방식이면, 에뮬레이터 프록시 옵션과 `config.json` 포트가 반드시 같아야 합니다.

## 6) 권장 실행 절차 (수동 + 자동 혼합)

1. 에뮬레이터 실행 (필요 시 프록시 옵션 포함)
2. Python 의존성 설치
3. 테스트 실행 (`pytest ...`)

실행 중 런타임 동작:
- `mitmdump` 자동 시작
- 단말 프록시 설정
- mitm CA 설치 시도
- Appium 서버 자동 시작(미실행 시)

즉, 에뮬레이터 부팅만 먼저 보장하면 나머지는 코드가 자동으로 처리하도록 구성되어 있습니다.

## 7) 점검 커맨드 모음

```bash
python scripts/check_mobile_runtime.py
adb devices
appium driver list --installed
pytest test/dev/test_gemini.py -v
```

JDK / Appium 부팅을 별도로 점검하고 싶다면 (Windows):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\probe_java.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\appium_smoke.ps1
```

## 8) 자주 발생하는 문제

- `Could not connect to proxy ... timed out`
  - mitmproxy 미실행 또는 포트 불일치 가능성이 큼
- `No WEBVIEW context`
  - 앱/빌드/디버그 설정 또는 WebView 노출 타이밍 점검 필요
- `Appium server is not running ...`
  - `manage_server=false`이거나 `appium` 바이너리 미설치
- `adb` 명령 실패
  - SDK path/PATH 설정 또는 에뮬레이터 미부팅 확인
- `Cannot verify the signature of '...apk' ... 'java.exe' binary could not be found ...`
  - `JAVA_HOME` 미설정. 2-4 절 참고하여 `JAVA_HOME`을 Android Studio JBR 경로로 지정하고 새 터미널에서 재실행
- `--allow-insecure` 관련 `The full feature name must include both the destination automation name or the '*' wildcard ...`
  - Appium 3.x 부터 `<automationName>:<feature>` 형식 필수. `config.json`의 `appium.allow_insecure`를 `uiautomator2:chromedriver_autodownload` 등으로 변경



  CA 인증서 에뮬레이터 설정법

  mitmproxy 실행
  mitmdump -p 8080 --listen-host 0.0.0.0 --ssl-insecure --set connection_strategy=lazy

  에뮬레이터 기기 프록시 연결후 실행행
  emulator -avd AOS16 -no-snapshot-load -http-proxy http://127.0.0.1:8080

  기기에서 http://mitm.it 접속 후 CA 인증서 다운로드
  setting > CA certificate 검색후 다운받은 CA 인증서 설치치
