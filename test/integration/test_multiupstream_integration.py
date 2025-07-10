import subprocess
import time
import requests
import os
import signal
import json
import sys
import websocket
import threading

def start_mitmproxy(config_dir, port):
    cmd = [
        ".venv/bin/mitmdump",
        "--mode", f"multiupstream:{config_dir}",
        "--listen-port", str(port),
        "--set", "termlog_verbosity=error",
        "--set", "console_eventlog_verbosity=error",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Wait a bit and check if process is still running
    time.sleep(2)
    if process.poll() is not None:
        # Process has exited, get the output
        stdout, stderr = process.communicate()
        print(f"❌ mitmproxy failed to start:")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        raise Exception("mitmproxy failed to start")
    
    print(f"✅ mitmproxy started successfully on port {port}")
    return process

def check_proxy_connection(host, port, timeout=5):
    """Check if proxy is listening and accepting connections."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"   ❌ Proxy connection check failed: {e}")
        return False

def test_http_load_balancing(proxy_port):
    """Test HTTP load balancing across multiple upstream proxies."""
    print("🌐 Testing HTTP load balancing...")
    
    proxies = {
        "http": f"http://127.0.0.1:{proxy_port}",
        "https": f"http://127.0.0.1:{proxy_port}",
    }
    
    # Test multiple requests to see load balancing in action
    test_urls = [
        "http://httpbin.org/ip",
        "http://httpbin.org/user-agent",
        "http://httpbin.org/headers",
        "http://httpbin.org/get",
        "http://httpbin.org/ip",
        "http://httpbin.org/user-agent",
    ]
    
    successful_requests = 0
    total_requests = len(test_urls)
    
    for i, url in enumerate(test_urls, 1):
        try:
            print(f"  Request {i}/{total_requests}: {url}")
            response = requests.get(url, proxies=proxies, timeout=10, verify=False)
            print(f"    ✅ Status: {response.status_code}")
            
            # Try to get response content for debugging
            try:
                content = response.json()
                if 'origin' in content:
                    print(f"    📍 Origin IP: {content['origin']}")
            except:
                pass
                
            successful_requests += 1
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    print(f"    📊 Success rate: {successful_requests}/{total_requests}")
    return successful_requests == total_requests

def test_websocket_public_echo(proxy_host, proxy_port):
    """Test WebSocket proxying via HTTP upgrade request through the proxy."""
    print("🌐 Testing WebSocket proxying (HTTP upgrade request)...")
    
    # Use the local WebSocket service provided by the user
    ws_url = "http://172.236.138.9:8001/mitm_ws"
    
    def test_websocket_upgrade():
        """Test WebSocket connection via HTTP upgrade request."""
        print(f"    Testing WebSocket upgrade: {ws_url}")
        
        proxies = {
            "http": f"http://{proxy_host}:{proxy_port}",
            "https": f"http://{proxy_host}:{proxy_port}",
        }
        
        headers = {
            "Connection": "Upgrade",
            "Upgrade": "websocket",
            "Sec-WebSocket-Version": "13",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        }
        
        try:
            print(f"      🔄 Sending HTTP upgrade request to {ws_url} via proxy {proxy_host}:{proxy_port}")
            response = requests.get(
                ws_url,
                proxies=proxies,
                headers=headers,
                timeout=10,
                verify=False,
                stream=True  # Keep connection open
            )
            
            print(f"      📊 Response status: {response.status_code}")
            print(f"      📊 Response headers: {dict(response.headers)}")
            
            if response.status_code == 101:
                print(f"      ✅ WebSocket upgrade successful!")
                # Try to read some data to verify connection
                try:
                    # Read a small amount of data to test the connection
                    data = response.raw.read(1024, timeout=5)
                    print(f"      📨 Received data: {data[:100]}...")
                    response.close()
                    return True
                except Exception as e:
                    print(f"      ⚠️  Could not read data: {e}")
                    response.close()
                    return True  # Upgrade was successful even if we can't read data
            else:
                print(f"      ❌ WebSocket upgrade failed: {response.status_code}")
                response.close()
                return False
                
        except Exception as e:
            print(f"      ❌ WebSocket upgrade request failed: {e}")
            return False
    
    # Test WebSocket upgrade
    print(f"    --- Testing WebSocket Upgrade ---")
    success = test_websocket_upgrade()
    
    if success:
        print(f"      ✅ WebSocket upgrade test PASSED")
    else:
        print(f"      ❌ WebSocket upgrade test FAILED")
    
    print(f"    📊 WebSocket test summary: {'1/1' if success else '0/1'} services worked")
    return success

def test_multiupstream_integration():
    config_dir = "test/integration/config"
    proxy_port = 8083
    proxy_host = "127.0.0.1"

    print("🚀 Starting Multi-Upstream Proxy Integration Test")
    print(f"📁 Config directory: {config_dir}")
    print(f"🔌 Proxy port: {proxy_port}")

    # Start mitmproxy
    print("🔄 Starting mitmproxy...")
    mitm = start_mitmproxy(config_dir, proxy_port)
    
    # Check if proxy is listening
    print(f"🔍 Checking if proxy is listening on {proxy_host}:{proxy_port}...")
    if not check_proxy_connection(proxy_host, proxy_port):
        print(f"❌ Proxy is not listening on {proxy_host}:{proxy_port}")
        raise Exception("Proxy failed to start or is not listening")
    print(f"✅ Proxy is listening and accepting connections")
    
    time.sleep(1)

    try:
        # Test HTTP load balancing
        http_success = test_http_load_balancing(proxy_port)
        # Test WebSocket proxying
        ws_success = test_websocket_public_echo(proxy_host, proxy_port)
        
        print("\n📋 Integration Test Summary:")
        print(f"  {'✅' if http_success else '❌'} HTTP load balancing: {'Passed' if http_success else 'Failed'}")
        print(f"  {'✅' if ws_success else '❌'} WebSocket proxying: {'Passed' if ws_success else 'Failed'}")
        
        if http_success and ws_success:
            print("  🎉 All tests passed! Multi-upstream proxy is working correctly.")
        else:
            print("  ⚠️  Some tests failed. Check the configuration and proxy availability.")
        
        return http_success and ws_success
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    
    finally:
        # Clean up
        if 'mitm' in locals() and mitm.poll() is None:
            print("🛑 Stopping mitmproxy...")
            mitm.terminate()
            mitm.wait()

if __name__ == "__main__":
    success = test_multiupstream_integration()
    exit(0 if success else 1) 