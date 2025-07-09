import subprocess
import time
import requests
import os
import signal

def start_mitmproxy(config_dir, port):
    cmd = [
        ".venv/bin/mitmdump",
        "--mode", f"multiupstream:{config_dir}",
        "--listen-port", str(port),
        "--set", "termlog_verbosity=error",
        "--set", "console_eventlog_verbosity=error",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def test_multiupstream_integration():
    config_dir = "test/integration/config"
    proxy_port = 8083

    # 启动 mitmproxy
    mitm = start_mitmproxy(config_dir, proxy_port)
    time.sleep(3)

    try:
        proxies = {
            "http": f"http://127.0.0.1:{proxy_port}",
            "https": f"http://127.0.0.1:{proxy_port}",
        }
        # 这里假设 11113/11114 端口有 mock 上游代理在监听
        resp1 = requests.get("http://www.google.com", proxies=proxies, timeout=5)
        print("Google status:", resp1.status_code)
        resp2 = requests.get("http://www.baidu.com", proxies=proxies, timeout=5)
        print("Baidu status:", resp2.status_code)
        resp3 = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=5)
        print("Httpbin status:", resp3.status_code)
    finally:
        mitm.terminate()
        mitm.wait()

if __name__ == "__main__":
    test_multiupstream_integration() 