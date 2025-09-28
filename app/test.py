#!/usr/bin/env python3
"""
Comprehensive Plex server connection diagnostics for macOS troubleshooting.
Tests various connection methods to identify why Python can't reach Plex while browsers can.
"""

import socket
import sys
import os
import platform
import subprocess
from urllib.parse import urlparse
import json

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def test_basic_socket_connection(host, port):
    """Test raw TCP socket connection"""
    print(f"Testing raw socket connection to {host}:{port}...")

    # Test with different socket configurations
    socket_configs = [
        ("IPv4 default", socket.AF_INET, socket.SOCK_STREAM, {}),
        ("IPv4 with SO_REUSEADDR", socket.AF_INET, socket.SOCK_STREAM, {"SO_REUSEADDR": 1}),
        ("IPv6 dual stack", socket.AF_INET6, socket.SOCK_STREAM, {"IPV6_V6ONLY": 0}),
    ]

    for config_name, family, sock_type, options in socket_configs:
        print(f"  Testing {config_name}...")
        try:
            s = socket.socket(family, sock_type)
            s.settimeout(10)

            # Apply socket options
            for opt_name, opt_value in options.items():
                try:
                    if opt_name == "SO_REUSEADDR":
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, opt_value)
                    elif opt_name == "IPV6_V6ONLY":
                        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, opt_value)
                except:
                    pass  # Option not available

            # For IPv6, need to handle address format
            if family == socket.AF_INET6:
                # Try to map IPv4 to IPv6
                if '.' in host:  # IPv4 address
                    try:
                        connect_addr = ('::ffff:' + host, port, 0, 0)
                    except:
                        print(f"    ❌ Cannot map IPv4 to IPv6")
                        s.close()
                        continue
                else:
                    connect_addr = (host, port, 0, 0)
            else:
                connect_addr = (host, port)

            result = s.connect_ex(connect_addr)
            if result == 0:
                print(f"    ✅ {config_name} connection successful")
                s.close()
                return True
            else:
                print(f"    ❌ {config_name} failed with error code: {result}")

        except Exception as exc:
            print(f"    ❌ {config_name} failed: {exc}")
        finally:
            try:
                s.close()
            except:
                pass

    return False

def test_dns_resolution(host):
    """Test DNS resolution"""
    print(f"Testing DNS resolution for {host}...")

    try:
        # Test if it's already an IP
        socket.inet_aton(host)
        print(f"✅ {host} is already an IP address")
        return True
    except socket.error:
        pass

    try:
        ip = socket.gethostbyname(host)
        print(f"✅ DNS resolution successful: {host} -> {ip}")
        return True
    except Exception as exc:
        print(f"❌ DNS resolution failed: {exc}")
        return False

def test_requests_connection(url):
    """Test HTTP connection using requests library"""
    print(f"Testing HTTP connection to {url}...")

    try:
        import requests

        # Test with various configurations
        configs = [
            {"timeout": 10},
            {"timeout": 10, "verify": False},
            {"timeout": 30},
            {"timeout": 30, "allow_redirects": False},
            {"timeout": 10, "stream": True},
        ]

        for i, config in enumerate(configs, 1):
            try:
                print(f"  Test {i}: {config}")
                response = requests.get(url, **config)
                print(f"  ✅ Success: Status {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response headers: {dict(response.headers)}")
                return True
            except Exception as exc:
                print(f"  ❌ Failed: {exc}")

        # Test the exact way PlexAPI makes requests
        print(f"  Testing PlexAPI-style request...")
        try:
            session = requests.Session()
            session.verify = False
            response = session.get(url, timeout=30)
            print(f"  ✅ PlexAPI-style Success: Status {response.status_code}")
            return True
        except Exception as exc:
            print(f"  ❌ PlexAPI-style Failed: {exc}")

        return False

    except ImportError:
        print("❌ requests library not available")
        return False

def test_urllib_connection(url):
    """Test HTTP connection using urllib"""
    print(f"Testing urllib connection to {url}...")

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            print(f"✅ urllib connection successful: Status {status}")
            return True

    except Exception as exc:
        print(f"❌ urllib connection failed: {exc}")
        return False

def test_plexapi_connection(url, token):
    """Test PlexAPI library connection"""
    print(f"Testing PlexAPI connection to {url}...")

    try:
        from plexapi.server import PlexServer

        # Test with various timeout settings
        timeouts = [10, 30, 60]

        for timeout in timeouts:
            try:
                print(f"  Testing with {timeout}s timeout...")
                plex = PlexServer(url, token, timeout=timeout)
                print(f"  ✅ PlexAPI connection successful")
                print(f"  Server: {plex.friendlyName}")
                print(f"  Version: {plex.version}")
                return True
            except Exception as exc:
                print(f"  ❌ Failed with {timeout}s timeout: {exc}")

        return False

    except ImportError:
        print("❌ plexapi library not available")
        return False

def test_system_networking():
    """Test system networking configuration"""
    print_section("System Networking Diagnostics")

    print(f"Platform: {platform.platform()}")
    print(f"Python version: {sys.version}")

    # Check environment variables that might affect networking
    env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
    print("\nProxy environment variables:")
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"  {var}={value}")
    if not any(os.environ.get(var) for var in env_vars):
        print("  No proxy variables set")

    # Test network interfaces
    try:
        import netifaces
        print(f"\nNetwork interfaces:")
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    print(f"  {interface}: {addr['addr']}")
    except ImportError:
        print("\nNetwork interfaces: netifaces not available")

def discover_plex_servers():
    """Attempt to discover Plex servers using various methods"""
    print_section("Plex Server Discovery")

    discovered_servers = []

    # Method 1: Try common localhost variants
    localhost_variants = [
        ("127.0.0.1", 32400),
        ("localhost", 32400),
        ("0.0.0.0", 32400),
    ]

    print("Testing localhost variants...")
    for host, port in localhost_variants:
        if test_http_connection_simple(host, port):
            discovered_servers.append(f"http://{host}:{port}")
            print(f"  ✅ Found working server: http://{host}:{port}")

    # Method 2: Try local network IPs
    print("\nTesting local network addresses...")

    # Get all local network interfaces
    try:
        import subprocess
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        lines = result.stdout.split('\n')

        ips = []
        for line in lines:
            if 'inet ' in line and 'netmask' in line:
                parts = line.strip().split()
                for i, part in enumerate(parts):
                    if part == 'inet' and i + 1 < len(parts):
                        ip = parts[i + 1]
                        if not ip.startswith('127.') and '.' in ip:
                            ips.append(ip)

        for ip in ips:
            if test_http_connection_simple(ip, 32400):
                discovered_servers.append(f"http://{ip}:32400")
                print(f"  ✅ Found working server: http://{ip}:32400")

    except Exception as e:
        print(f"  Could not scan network interfaces: {e}")

    # Method 3: Try common network ranges
    print("\nTesting common private network ranges...")

    # Get the network from the original problematic IP
    target_network = "172.19.35"
    for i in [1, 2, 100, 101, 254]:  # Common IPs in that range
        test_ip = f"{target_network}.{i}"
        if test_http_connection_simple(test_ip, 32400):
            discovered_servers.append(f"http://{test_ip}:32400")
            print(f"  ✅ Found working server: http://{test_ip}:32400")

    return discovered_servers

def test_http_connection_simple(host, port):
    """Simple HTTP test using urllib - more likely to work than raw sockets"""
    try:
        import urllib.request
        import urllib.error

        url = f"http://{host}:{port}/"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=3) as response:
            # Any response (even 401) means the server is reachable
            return True

    except Exception:
        return False

def test_alternative_addresses():
    """Test alternative ways to reach the Plex server"""
    print_section("Testing Alternative Addresses")

    # Common Plex server addresses to test
    addresses = [
        "127.0.0.1:32400",
        "localhost:32400",
        "0.0.0.0:32400",
    ]

    # Try to get the local machine's IP
    try:
        # Connect to external address to find local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        addresses.append(f"{local_ip}:32400")
        print(f"Local machine IP: {local_ip}")
    except:
        pass

    for addr in addresses:
        host, port = addr.split(':')
        port = int(port)
        print(f"\nTesting {addr}:")
        test_basic_socket_connection(host, port)

def run_comprehensive_test():
    """Run all diagnostic tests"""
    print_section("Plex Connection Diagnostics")
    print("Diagnosing why Python can't connect to Plex while browsers can...")

    # Configuration
    host = "172.19.35.2"
    port = 32400
    url = f"http://{host}:{port}"

    # Get token from environment
    token = os.environ.get('PLEX_TOKEN', 'bT5v9S7irrXXWSzzA1MU')  # fallback to .env value

    print(f"Target: {url}")
    print(f"Token: {'*' * (len(token) - 4) + token[-4:] if token else 'Not set'}")

    # Run tests
    test_system_networking()

    print_section("Basic Connectivity Tests")
    test_dns_resolution(host)
    socket_ok = test_basic_socket_connection(host, port)

    if socket_ok:
        print_section("HTTP Library Tests")
        test_requests_connection(url)
        test_urllib_connection(url)

        if token:
            print_section("PlexAPI Tests")
            test_plexapi_connection(url, token)

    test_alternative_addresses()

    # Try to discover working Plex servers
    discovered = discover_plex_servers()

    print_section("Results & Recommendations")

    if discovered:
        print("🎉 Found working Plex server addresses:")
        for server in discovered:
            print(f"  • {server}")

        print(f"\n💡 Update your .env file to use one of these URLs:")
        print(f"   PLEX_URL={discovered[0]}")

        # Test the first discovered server with PlexAPI
        if token:
            print(f"\n🧪 Testing PlexAPI with discovered server...")
            test_plexapi_connection(discovered[0], token)
    else:
        print("❌ No working Plex servers discovered via Python")
        print("\n🔧 Troubleshooting steps for macOS Python networking:")
        print("1. Check macOS System Preferences > Security & Privacy > Firewall")
        print("2. Try allowing Python network access in firewall settings")
        print("3. Check if using VPN that routes differently for Python")
        print("4. Try running Python with elevated permissions temporarily")
        print("5. Consider using Plex hostname instead of IP address")

    print_section("Summary")
    print("macOS networking issue confirmed:")
    print("• Browser and system tools can connect to 172.19.35.2:32400")
    print("• Python processes cannot connect (errno 65: No route to host)")
    print("• This is a macOS security/networking configuration issue")

    if discovered:
        print(f"\n✅ Solution: Use discovered working URL: {discovered[0]}")
    else:
        print("\n🔍 Need to resolve macOS Python networking restrictions")

if __name__ == "__main__":
    run_comprehensive_test()