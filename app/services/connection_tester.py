"""
Plex connection testing and troubleshooting utility for macOS networking issues.
Provides robust connection testing and helpful error messages.
"""

import socket
import logging
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import subprocess


logger = logging.getLogger(__name__)


class PlexConnectionError(Exception):
    """Raised when Plex connection fails with troubleshooting guidance"""

    def __init__(self, message: str, troubleshooting_steps: List[str]):
        super().__init__(message)
        self.troubleshooting_steps = troubleshooting_steps


class PlexConnectionTester:
    """Tests Plex server connectivity and provides troubleshooting guidance"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def test_connection(self, plex_url: str) -> bool:
        """
        Test if the given Plex URL is reachable via Python.
        Returns True if successful, False otherwise.
        """
        try:
            parsed = urlparse(plex_url)
            host = parsed.hostname
            port = parsed.port or 32400

            return self._test_socket_connection(host, port)
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False

    def test_with_fallbacks(self, plex_url: str) -> Tuple[bool, Optional[str]]:
        """
        Test the primary URL and fallback alternatives.
        Returns (success, working_url) tuple.
        """
        # Test the primary URL first
        if self.test_connection(plex_url):
            return True, plex_url

        # Extract host for fallback testing
        try:
            parsed = urlparse(plex_url)
            original_host = parsed.hostname
            port = parsed.port or 32400
        except:
            return False, None

        # Generate fallback URLs to test
        fallback_hosts = self._generate_fallback_hosts(original_host)

        for host in fallback_hosts:
            fallback_url = f"http://{host}:{port}"
            if self.test_connection(fallback_url):
                logger.info(f"Found working fallback URL: {fallback_url}")
                return True, fallback_url

        return False, None

    def get_detailed_error_info(self, plex_url: str) -> PlexConnectionError:
        """
        Provide detailed error information and troubleshooting steps.
        """
        # Test if the URL is reachable by system tools
        parsed = urlparse(plex_url)
        host = parsed.hostname
        port = parsed.port or 32400

        # Check if system tools can reach it
        system_reachable = self._test_system_connectivity(host, port)

        if system_reachable:
            # macOS Python networking issue
            message = (
                f"macOS is blocking Python access to {plex_url}. "
                f"System tools can reach the server, but Python cannot."
            )
            troubleshooting_steps = [
                "Check macOS System Preferences > Security & Privacy > Firewall",
                "Allow Python network access in firewall settings",
                "Try running the application with elevated permissions temporarily",
                "Check if using a VPN that routes Python traffic differently",
                "Consider using a Plex hostname instead of IP address",
                "Update macOS network interface permissions",
                "Try using a different Python interpreter (system vs virtualenv)",
            ]
        else:
            # General connectivity issue
            message = f"Cannot reach Plex server at {plex_url}. Server may be down or unreachable."
            troubleshooting_steps = [
                "Verify the Plex server is running and accessible",
                "Check the PLEX_URL in your .env file",
                "Ensure you're on the same network as the Plex server",
                "Try accessing the Plex web interface in a browser",
                "Check firewall settings on both client and server",
                "Verify the port (usually 32400) is correct",
            ]

        return PlexConnectionError(message, troubleshooting_steps)

    def _test_socket_connection(self, host: str, port: int) -> bool:
        """Test raw socket connection"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _test_system_connectivity(self, host: str, port: int) -> bool:
        """Test if system tools can reach the host:port"""
        try:
            # Test with netcat
            result = subprocess.run(
                ['nc', '-z', '-v', host, str(port)],
                capture_output=True,
                timeout=self.timeout,
                text=True
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            try:
                # Fallback to ping for basic reachability
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '3000', host],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                return result.returncode == 0
            except:
                return False

    def _generate_fallback_hosts(self, original_host: str) -> List[str]:
        """Generate list of fallback hosts to try"""
        fallbacks = []

        # Always try localhost variants
        fallbacks.extend([
            "127.0.0.1",
            "localhost",
        ])

        # If original was an IP, try to find alternative IPs in same network
        if original_host and self._is_ip_address(original_host):
            network_prefix = '.'.join(original_host.split('.')[:-1])
            # Try common last octets in the same network
            for last_octet in [1, 2, 100, 101, 254]:
                candidate = f"{network_prefix}.{last_octet}"
                if candidate != original_host:
                    fallbacks.append(candidate)

        # Try to get local machine IPs
        try:
            local_ips = self._get_local_ips()
            fallbacks.extend(local_ips)
        except:
            pass

        return fallbacks

    def _is_ip_address(self, host: str) -> bool:
        """Check if host is an IP address"""
        try:
            socket.inet_aton(host)
            return True
        except socket.error:
            return False

    def _get_local_ips(self) -> List[str]:
        """Get local machine IP addresses"""
        ips = []
        try:
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            lines = result.stdout.split('\n')

            for line in lines:
                if 'inet ' in line and 'netmask' in line:
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == 'inet' and i + 1 < len(parts):
                            ip = parts[i + 1]
                            if not ip.startswith('127.') and '.' in ip:
                                ips.append(ip)
        except:
            pass

        return ips


def test_plex_connection(plex_url: str, plex_token: str = None) -> Tuple[bool, Optional[str], Optional[PlexConnectionError]]:
    """
    Convenience function to test Plex connection with full diagnostics.

    Returns:
        (success, working_url, error_info)
    """
    tester = PlexConnectionTester()

    # First try with fallbacks
    success, working_url = tester.test_with_fallbacks(plex_url)

    if success:
        return True, working_url, None
    else:
        error_info = tester.get_detailed_error_info(plex_url)
        return False, None, error_info