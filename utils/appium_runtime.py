import os
import platform
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


class AppiumRuntimeError(RuntimeError):
    pass


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "y", "yes", "on"}


class AppiumRuntime:
    """Session-scoped native Android app runtime.

    The runtime owns external process/environment setup:
    - mitmproxy capture process
    - Android global proxy and mitm CA installation
    - optional local Appium server process
    - Appium UiAutomator2 driver for the Gmarket APK
    """

    def __init__(self, project_root: Path, app_config: dict[str, Any]) -> None:
        self.project_root = Path(project_root)
        self.app_config = app_config
        self.backend = (
            app_config.get("runner_backend")
            or app_config.get("automation_backend")
            or "appium"
        ).strip().lower()
        self.appium_config = dict(app_config.get("appium") or {})
        self.proxy_config = dict(app_config.get("proxy") or {})
        self.capture_file = self.project_root / "json" / "proxy_capture.jsonl"
        self._proxy_process: subprocess.Popen[str] | None = None
        self._appium_process: subprocess.Popen[str] | None = None
        self._appium_log_fp: Optional[Any] = None

    @property
    def proxy_host(self) -> str:
        return str(self.proxy_config.get("listen_host") or "127.0.0.1")

    @property
    def proxy_port(self) -> int:
        return int(self.proxy_config.get("listen_port") or 8081)

    @property
    def proxy_device_host(self) -> str:
        configured = self.proxy_config.get("device_host")
        if configured:
            return str(configured)
        if self.proxy_host in {"127.0.0.1", "localhost"}:
            return "10.0.2.2"
        return self.proxy_host

    @property
    def capture_domains(self) -> list[str]:
        raw = self.proxy_config.get("capture_domains") or [
            "aplus.gmarket.co.kr",
            "aplus.gmarket.com",
        ]
        return [str(item) for item in raw]

    @property
    def app_package(self) -> str:
        return str(self.appium_config.get("appPackage") or "com.ebay.kr.gmarket")

    @property
    def app_activity(self) -> str:
        return str(
            self.appium_config.get("appActivity")
            or "com.ebay.kr.gmarket.eBayKoreaGmarketActivity"
        )

    def validate_backend(self) -> None:
        if self.backend not in {"appium", "appium_android", "appium_hybrid_android"}:
            raise AppiumRuntimeError(
                f"Unsupported backend '{self.backend}'. "
                "Native Android Appium execution requires "
                "'appium', 'appium_android', or 'appium_hybrid_android'."
            )
        mobile_profile = str(self.app_config.get("mobile_profile") or "").strip().lower()
        if mobile_profile == "iphone":
            raise AppiumRuntimeError(
                "The Appium APK runtime currently supports Android profiles only. "
                "Set config.json mobile_profile to an Android value such as 'galaxy_s20'."
            )

    def _require_binary(self, name: str) -> str:
        resolved = shutil.which(name)
        if not resolved:
            raise AppiumRuntimeError(f"Required binary '{name}' was not found in PATH.")
        return resolved

    def _platform_block(self) -> dict[str, Any]:
        system = platform.system().lower()
        if "windows" in system:
            return dict(
                self.app_config.get("win")
                or self.app_config.get("windows")
                or {}
            )
        if "darwin" in system or "mac" in system:
            return dict(self.app_config.get("mac") or self.app_config.get("darwin") or {})
        return dict(self.app_config.get("linux") or {})

    def _configured_path(self, *keys: str, required: bool = False) -> Optional[str]:
        platform_block = self._platform_block()
        raw: Any = None
        for key in keys:
            raw = self.appium_config.get(key)
            if raw:
                break
            raw = platform_block.get(key)
            if raw:
                break
        if raw is None or str(raw).strip() == "":
            if required:
                raise AppiumRuntimeError(
                    f"Missing required Appium path setting. Checked keys: {', '.join(keys)}"
                )
            return None

        candidate = Path(os.path.expandvars(os.path.expanduser(str(raw))))
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        if required and not candidate.exists():
            raise AppiumRuntimeError(f"Configured path does not exist: {candidate}")
        if candidate.exists():
            return str(candidate.resolve())
        return str(candidate)

    def _run(
        self,
        *args: str,
        check: bool = True,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            check=check,
            timeout=timeout,
            text=True,
            capture_output=True,
        )

    def adb(
        self,
        *args: str,
        check: bool = True,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess[str]:
        adb_path = self._require_binary("adb")
        cmd = [adb_path]
        udid = self.appium_config.get("udid") or self.appium_config.get("deviceSerial")
        if udid:
            cmd.extend(["-s", str(udid)])
        cmd.extend(args)
        return self._run(*cmd, check=check, timeout=timeout)

    def _wait_for_port(self, host: str, port: int, timeout_s: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return
            except OSError:
                time.sleep(0.2)
        raise AppiumRuntimeError(f"Timed out waiting for {host}:{port} to accept connections.")

    def _is_port_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    def _server_host_port(self) -> tuple[str, int]:
        server_url = str(self.appium_config.get("server_url") or "http://127.0.0.1:4723")
        parsed = urlparse(server_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 4723
        return host, port

    def ensure_appium_server(self) -> None:
        host, port = self._server_host_port()
        if self._is_port_open(host, port):
            return

        if not _as_bool(self.appium_config.get("manage_server"), default=True):
            raise AppiumRuntimeError(
                f"Appium server is not running at {host}:{port}. "
                "Start Appium manually or set appium.manage_server=true."
            )

        command = self.appium_config.get("server_command")
        if command:
            cmd = shlex.split(str(command))
        else:
            appium_bin = self._require_binary("appium")
            allow_insecure = (
                self.appium_config.get("allow_insecure")
                or self.appium_config.get("allowInsecure")
                or ["chromedriver_autodownload"]
            )
            if isinstance(allow_insecure, str):
                allow_value = allow_insecure
            else:
                allow_value = ",".join(str(item) for item in allow_insecure)
            cmd = [appium_bin]
            if allow_value:
                cmd.extend(["--allow-insecure", allow_value])

        log_dir = self.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._appium_log_fp = (log_dir / "appium_server.log").open("a", encoding="utf-8")
        self._appium_process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            stdout=self._appium_log_fp,
            stderr=subprocess.STDOUT,
            text=True,
        )
        timeout_s = float(self.appium_config.get("server_start_timeout", 20))
        self._wait_for_port(host, port, timeout_s=timeout_s)

    def stop_appium_server(self) -> None:
        if self._appium_process and self._appium_process.poll() is None:
            self._appium_process.terminate()
            try:
                self._appium_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._appium_process.kill()
        self._appium_process = None
        if self._appium_log_fp:
            try:
                self._appium_log_fp.close()
            except Exception:
                pass
        self._appium_log_fp = None

    def start_proxy(self) -> None:
        self.validate_backend()
        self._require_binary("mitmdump")
        if self._proxy_process and self._proxy_process.poll() is None:
            return

        self.capture_file.parent.mkdir(parents=True, exist_ok=True)
        self.capture_file.write_text("", encoding="utf-8")
        env = os.environ.copy()
        env["TRACKING_PROXY_OUTPUT"] = str(self.capture_file)
        env["TRACKING_CAPTURE_DOMAINS"] = ",".join(self.capture_domains)

        addon_path = self.project_root / "utils" / "mitm_capture_addon.py"
        cmd = [
            "mitmdump",
            "-q",
            "-s",
            str(addon_path),
            "--listen-host",
            self.proxy_host,
            "--listen-port",
            str(self.proxy_port),
            "--set",
            "block_global=false",
        ]
        self._proxy_process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._wait_for_port(self.proxy_host, self.proxy_port)

    def stop_proxy(self) -> None:
        if not self._proxy_process:
            return
        if self._proxy_process.poll() is None:
            self._proxy_process.terminate()
            try:
                self._proxy_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proxy_process.kill()
        self._proxy_process = None

    def configure_android_proxy(self) -> None:
        proxy_value = f"{self.proxy_device_host}:{self.proxy_port}"
        self.adb("wait-for-device")
        self.adb("shell", "settings", "put", "global", "http_proxy", proxy_value)

    def clear_android_proxy(self) -> None:
        try:
            self.adb("shell", "settings", "put", "global", "http_proxy", ":0", check=False)
            self.adb("shell", "settings", "delete", "global", "http_proxy", check=False)
            self.adb("shell", "settings", "delete", "global", "global_http_proxy_host", check=False)
            self.adb("shell", "settings", "delete", "global", "global_http_proxy_port", check=False)
        except Exception:
            pass

    def install_mitm_certificate(self) -> None:
        if not _as_bool(self.proxy_config.get("install_ca"), default=True):
            return

        self._require_binary("openssl")
        cert_path_cfg = self.proxy_config.get("ca_cert_path")
        cert_path = (
            Path(os.path.expanduser(os.path.expandvars(str(cert_path_cfg))))
            if cert_path_cfg
            else Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
        )
        if not cert_path.exists():
            raise AppiumRuntimeError(
                f"mitmproxy CA certificate was not found at {cert_path}. "
                "Start mitmproxy once locally so it can generate the CA."
            )

        self.adb("root", check=False, timeout=30)
        self.adb("wait-for-device")
        self.adb("remount", check=False, timeout=60)

        cert_hash = self._run(
            "openssl",
            "x509",
            "-inform",
            "PEM",
            "-subject_hash_old",
            "-in",
            str(cert_path),
            "-noout",
        ).stdout.strip().splitlines()[0]
        cert_target_name = f"{cert_hash}.0"
        system_target = f"/system/etc/security/cacerts/{cert_target_name}"

        self.adb("push", str(cert_path), system_target, timeout=60)
        self.adb("shell", "chmod", "644", system_target, timeout=30)
        verify = self.adb("shell", "ls", system_target, timeout=30)
        if cert_target_name not in verify.stdout:
            raise AppiumRuntimeError(
                "Failed to verify mitmproxy CA certificate installation on the emulator."
            )

    def _native_app_capabilities(self) -> dict[str, Any]:
        require_apk = self.backend == "appium_hybrid_android"
        app_path = self._configured_path("app", "app_path", required=require_apk)
        chromedriver_path = self._configured_path("chromedriverExecutable", "chrome_path")
        package = self.app_package
        activity = self.app_activity
        caps: dict[str, Any] = {
            "platformName": self.appium_config.get("platformName", "Android"),
            "appium:automationName": self.appium_config.get("automationName", "UiAutomator2"),
            "appium:deviceName": self.appium_config.get("deviceName", "Android Emulator"),
            "appium:newCommandTimeout": int(self.appium_config.get("newCommandTimeout", 900)),
            "appium:adbExecTimeout": int(self.appium_config.get("adbExecTimeout", 60000)),
            "appium:noReset": (
                False if require_apk else _as_bool(self.appium_config.get("noReset"), default=False)
            ),
            "appium:fullReset": _as_bool(self.appium_config.get("fullReset"), default=False),
            "appium:autoGrantPermissions": _as_bool(
                self.appium_config.get("autoGrantPermissions"),
                default=True,
            ),
            "appium:appPackage": package,
            "appium:appActivity": activity,
            "acceptInsecureCerts": _as_bool(
                self.appium_config.get("acceptInsecureCerts"),
                default=True,
            ),
        }
        if app_path:
            caps["appium:app"] = app_path
        if self.appium_config.get("udid"):
            caps["appium:udid"] = str(self.appium_config["udid"])
        if chromedriver_path:
            caps["appium:chromedriverExecutable"] = chromedriver_path
        if _as_bool(self.appium_config.get("autoWebview"), default=False):
            caps["appium:autoWebview"] = True

        chrome_options = dict(self.appium_config.get("chromeOptions") or {})
        if package:
            chrome_options.setdefault("androidPackage", package)
            chrome_options.setdefault("androidProcess", package)
        if chrome_options:
            caps["goog:chromeOptions"] = chrome_options

        extra_caps = self.appium_config.get("capabilities")
        if isinstance(extra_caps, dict):
            for key, value in extra_caps.items():
                caps[str(key)] = value
        return caps

    def create_driver(self) -> Any:
        try:
            from appium import webdriver as appium_webdriver
            from appium.options.android import UiAutomator2Options
        except Exception as exc:  # pragma: no cover - depends on local runtime
            raise AppiumRuntimeError(
                "Appium Python client is not installed. Install the project runtime dependencies first."
            ) from exc

        server_url = str(self.appium_config.get("server_url") or "http://127.0.0.1:4723")
        options = UiAutomator2Options()
        options.load_capabilities(self._native_app_capabilities())
        return appium_webdriver.Remote(server_url, options=options)

    def launch_app(self, driver: Any) -> None:
        if not _as_bool(self.appium_config.get("launch_activity_on_start"), default=True):
            return

        package = self.app_package
        activity = self.app_activity
        if not package:
            return

        if package and activity:
            try:
                driver.start_activity(package, activity)
                return
            except Exception:
                pass
            try:
                driver.execute_script(
                    "mobile: startActivity",
                    {"appPackage": package, "appActivity": activity},
                )
                return
            except Exception:
                pass

        try:
            driver.activate_app(package)
        except Exception as exc:
            raise AppiumRuntimeError(f"Failed to launch Android app package '{package}'.") from exc

    def bootstrap(self) -> Any:
        self.validate_backend()
        self.start_proxy()
        self.install_mitm_certificate()
        self.configure_android_proxy()
        self.ensure_appium_server()
        driver = self.create_driver()
        self.launch_app(driver)
        return driver

    def shutdown(self, driver: Any | None = None) -> None:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        self.clear_android_proxy()
        self.stop_proxy()
        self.stop_appium_server()

    def verify_local_environment(self) -> dict[str, str]:
        info: dict[str, str] = {}
        info["adb"] = self._require_binary("adb")
        info["mitmdump"] = self._require_binary("mitmdump")
        info["openssl"] = self._require_binary("openssl")
        try:
            info["appium"] = self._require_binary("appium")
        except AppiumRuntimeError as exc:
            info["appium"] = str(exc)
        info["appium_server_url"] = str(
            self.appium_config.get("server_url") or "http://127.0.0.1:4723"
        )
        host, port = self._server_host_port()
        info["appium_server_running"] = str(self._is_port_open(host, port))
        info["app_package"] = self.app_package
        info["app_activity"] = self.app_activity
        devices = self.adb("devices", timeout=30)
        info["adb_devices"] = devices.stdout.strip()
        return info
