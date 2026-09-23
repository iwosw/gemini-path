"""Open Gemini in an isolated Chromium profile with a selected SNI gateway.

No Windows DNS/hosts/proxy settings are modified. TLS remains between Chrome
and Google; a successful anonymous handshake does not prove account access.
"""

import argparse
import ipaddress
import os
from pathlib import Path
import socket
import ssl
import subprocess


# Public gateway documented at https://www.comss.ru/page.php?id=2641 and
# https://github.com/Renkiy/Antigravity-Unlock/blob/main/tools/pin_hosts.py
# It may change or stop working. The preflight fails closed when it does.
GATEWAY = "45.88.174.254"
HOSTS = ("gemini.google.com", "accounts.google.com")
SITE = "https://gemini.google.com/app"


def browser_candidates():
    locations = (
        ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
        ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
        ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
    )
    return [Path(os.environ[name]) / suffix for name, suffix in locations if os.environ.get(name)]


def find_browser():
    for candidate in browser_candidates():
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Chrome или Microsoft Edge не найдены. Установите один из них.")


def profile_dir():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ValueError("LOCALAPPDATA не задан; некуда сохранить отдельный профиль браузера.")
    return Path(base) / "GeminiPath" / "browser-profile"


def resolver_rules(ip=GATEWAY):
    address = ipaddress.IPv4Address(ip)
    return ",".join(f"MAP {host} {address}" for host in HOSTS)


def check_gateway(ip=GATEWAY, timeout=5):
    address = str(ipaddress.IPv4Address(ip))
    context = ssl.create_default_context()
    for host in HOSTS:
        with socket.create_connection((address, 443), timeout=timeout) as connection:
            with context.wrap_socket(connection, server_hostname=host) as secure:
                if secure.version() is None:
                    raise ConnectionError(f"Не удалось установить TLS с {host}.")
    return address


def open_site(ip=GATEWAY, browser=None):
    # Verify both the route and Google's real certificate before starting a
    # login session. Never disable Chrome certificate validation.
    address = check_gateway(ip)
    executable = Path(browser) if browser else find_browser()
    if executable.name.lower() not in {"chrome.exe", "msedge.exe"} or not executable.is_file():
        raise ValueError("Для отдельного профиля поддерживаются Chrome и Microsoft Edge.")
    profile = profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable), f"--user-data-dir={profile}", "--new-window",
        "--no-first-run", "--no-proxy-server", "--disable-quic",
        f"--host-resolver-rules={resolver_rules(address)}", SITE,
    ]
    subprocess.Popen(command, close_fds=True)
    return f"Gemini открыт в отдельном профиле через {address}. Проверка TLS пройдена; доступ аккаунта проверяется в чате."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "open"))
    parser.add_argument("--ip", default=GATEWAY, help="IP проверенного SNI-шлюза")
    args = parser.parse_args()
    try:
        if args.action == "check":
            print(f"TLS Google проверен через {check_gateway(args.ip)} для: {', '.join(HOSTS)}")
        else:
            print(open_site(args.ip))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Ошибка: {error}\n")


if __name__ == "__main__":
    main()
