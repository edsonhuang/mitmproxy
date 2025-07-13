import socket
import struct
import time
from logging import DEBUG

from mitmproxy import connection
from mitmproxy import http
from mitmproxy.proxy import commands
from mitmproxy.proxy import context
from mitmproxy.proxy import layer
from mitmproxy.proxy import tunnel
from mitmproxy.proxy.layers import tls
from mitmproxy.utils import human


# SOCKS5 constants
SOCKS5_VERSION = 0x05
SOCKS5_METHOD_NO_AUTHENTICATION_REQUIRED = 0x00
SOCKS5_METHOD_USER_PASSWORD_AUTHENTICATION = 0x02
SOCKS5_METHOD_NO_ACCEPTABLE_METHODS = 0xFF

SOCKS5_CMD_CONNECT = 0x01
SOCKS5_ATYP_IPV4_ADDRESS = 0x01
SOCKS5_ATYP_DOMAINNAME = 0x03
SOCKS5_ATYP_IPV6_ADDRESS = 0x04

SOCKS5_REP_SUCCEEDED = 0x00
SOCKS5_REP_GENERAL_FAILURE = 0x01
SOCKS5_REP_CONNECTION_NOT_ALLOWED = 0x02
SOCKS5_REP_NETWORK_UNREACHABLE = 0x03
SOCKS5_REP_HOST_UNREACHABLE = 0x04
SOCKS5_REP_CONNECTION_REFUSED = 0x05
SOCKS5_REP_TTL_EXPIRED = 0x06
SOCKS5_REP_COMMAND_NOT_SUPPORTED = 0x07
SOCKS5_REP_ADDRESS_TYPE_NOT_SUPPORTED = 0x08


class Socks5UpstreamProxy(tunnel.TunnelLayer):
    """SOCKS5 upstream proxy layer that implements SOCKS5 client protocol."""
    
    buf: bytes
    state: str
    conn: connection.Server
    tunnel_connection: connection.Server
    username: str | None
    password: str | None

    def __init__(
        self, ctx: context.Context, tunnel_conn: connection.Server, username: str | None = None, password: str | None = None
    ):
        super().__init__(ctx, tunnel_connection=tunnel_conn, conn=ctx.server)
        self.buf = b""
        self.state = "greet"
        self.username = username
        self.password = password

    @classmethod
    def make(cls, ctx: context.Context, username: str | None = None, password: str | None = None) -> tunnel.LayerStack:
        assert ctx.server.via
        scheme, address = ctx.server.via
        assert scheme == "socks5"

        socks5_proxy = connection.Server(address=address)

        stack = tunnel.LayerStack()
        # Note: SOCKS5 typically doesn't use TLS, but if needed, we could add it here
        stack /= cls(ctx, socks5_proxy, username, password)

        return stack

    def start_handshake(self) -> layer.CommandGenerator[None]:
        """Start SOCKS5 handshake by sending greeting."""
        # Determine authentication method
        if self.username and self.password:
            # Send greeting with username/password authentication
            greeting = bytes([
                SOCKS5_VERSION,  # SOCKS version 5
                2,               # Number of methods
                SOCKS5_METHOD_NO_AUTHENTICATION_REQUIRED,  # No authentication required
                SOCKS5_METHOD_USER_PASSWORD_AUTHENTICATION  # Username/password authentication
            ])
        else:
            # Send greeting with no authentication only
            greeting = bytes([
                SOCKS5_VERSION,  # SOCKS version 5
                1,               # Number of methods
                SOCKS5_METHOD_NO_AUTHENTICATION_REQUIRED  # No authentication required
            ])
        yield commands.SendData(self.tunnel_connection, greeting)

    def receive_handshake_data(
        self, data: bytes
    ) -> layer.CommandGenerator[tuple[bool, str | None]]:
        """Handle SOCKS5 handshake data."""
        self.buf += data
        
        if self.state == "greet":
            return (yield from self._handle_greeting())
        elif self.state == "auth":
            return (yield from self._handle_authentication())
        elif self.state == "connect":
            return (yield from self._handle_connect_response())
        else:
            return False, f"Unknown SOCKS5 state: {self.state}"

    def _handle_greeting(self) -> layer.CommandGenerator[tuple[bool, str | None]]:
        """Handle SOCKS5 greeting response."""
        if len(self.buf) < 2:
            return False, None

        if self.buf[0] != SOCKS5_VERSION:
            return False, f"Invalid SOCKS version. Expected {SOCKS5_VERSION}, got {self.buf[0]}"

        method = self.buf[1]
        
        if method == SOCKS5_METHOD_NO_ACCEPTABLE_METHODS:
            return False, "SOCKS5 server requires authentication, but we don't support it"

        if method == SOCKS5_METHOD_USER_PASSWORD_AUTHENTICATION:
            if not self.username or not self.password:
                return False, "SOCKS5 server requires authentication, but no credentials provided"
            
            # Remove greeting response and send authentication
            self.buf = self.buf[2:]
            yield from self._send_authentication()
            self.state = "auth"
            return False, None
        elif method == SOCKS5_METHOD_NO_AUTHENTICATION_REQUIRED:
            # Greeting successful, send connect request
            self.buf = self.buf[2:]  # Remove greeting response
            yield from self._send_connect_request()
            self.state = "connect"
            return False, None
        else:
            return False, f"Unsupported SOCKS5 authentication method: {method}"

    def _send_authentication(self) -> layer.CommandGenerator[None]:
        """Send SOCKS5 username/password authentication."""
        assert self.username and self.password
        
        # Build authentication request: version(1) + username_len(1) + username + password_len(1) + password
        username_bytes = self.username.encode('utf-8')
        password_bytes = self.password.encode('utf-8')
        
        auth_request = bytearray([
            0x01,  # Authentication subnegotiation version
            len(username_bytes),  # Username length
        ])
        auth_request.extend(username_bytes)  # Username
        auth_request.extend([
            len(password_bytes),  # Password length
        ])
        auth_request.extend(password_bytes)  # Password
        
        yield commands.SendData(self.tunnel_connection, bytes(auth_request))

    def _handle_authentication(self) -> layer.CommandGenerator[tuple[bool, str | None]]:
        """Handle SOCKS5 authentication response."""
        if len(self.buf) < 2:
            return False, None

        if self.buf[0] != 0x01:
            return False, f"Invalid authentication subnegotiation version. Expected 0x01, got {self.buf[0]}"

        status = self.buf[1]
        if status != 0x00:
            return False, f"SOCKS5 authentication failed with status: {status}"

        # Authentication successful, send connect request
        self.buf = self.buf[2:]  # Remove authentication response
        yield from self._send_connect_request()
        self.state = "connect"
        return False, None

    def _send_connect_request(self) -> layer.CommandGenerator[None]:
        """Send SOCKS5 CONNECT request."""
        assert self.conn.address
        host, port = self.conn.address
        
        # Build SOCKS5 CONNECT request
        request = bytearray([
            SOCKS5_VERSION,      # SOCKS version 5
            SOCKS5_CMD_CONNECT,  # CONNECT command
            0x00,                # Reserved
        ])
        
        # Add address
        try:
            # Try to parse as IP address first
            ip = socket.inet_pton(socket.AF_INET, host)
            request.extend([
                SOCKS5_ATYP_IPV4_ADDRESS,  # IPv4 address type
                *ip,                       # 4 bytes IPv4 address
            ])
        except OSError:
            try:
                # Try IPv6
                ip = socket.inet_pton(socket.AF_INET6, host)
                request.extend([
                    SOCKS5_ATYP_IPV6_ADDRESS,  # IPv6 address type
                    *ip,                        # 16 bytes IPv6 address
                ])
            except OSError:
                # Treat as domain name
                host_bytes = host.encode('ascii')
                request.extend([
                    SOCKS5_ATYP_DOMAINNAME,  # Domain name address type
                    len(host_bytes),         # Domain name length
                    *host_bytes,             # Domain name
                ])
        
        # Add port (big-endian)
        request.extend(struct.pack('!H', port))
        
        yield commands.SendData(self.tunnel_connection, bytes(request))

    def _handle_connect_response(self) -> layer.CommandGenerator[tuple[bool, str | None]]:
        """Handle SOCKS5 CONNECT response."""
        if len(self.buf) < 4:
            return False, None

        if self.buf[0] != SOCKS5_VERSION:
            return False, f"Invalid SOCKS version in response. Expected {SOCKS5_VERSION}, got {self.buf[0]}"

        if self.buf[1] != SOCKS5_CMD_CONNECT:
            return False, f"Unexpected SOCKS5 command in response. Expected {SOCKS5_CMD_CONNECT}, got {self.buf[1]}"

        if self.buf[2] != 0x00:
            return False, f"Invalid reserved byte in SOCKS5 response: {self.buf[2]}"

        reply_code = self.buf[3]
        if reply_code != SOCKS5_REP_SUCCEEDED:
            error_msg = self._get_socks5_error_message(reply_code)
            proxyaddr = human.format_address(self.tunnel_connection.address)
            return False, f"SOCKS5 proxy {proxyaddr} refused connection: {error_msg}"

        # Parse address and port from response (we need to skip them)
        atyp = self.buf[4]
        addr_len = 0
        
        if atyp == SOCKS5_ATYP_IPV4_ADDRESS:
            addr_len = 4
        elif atyp == SOCKS5_ATYP_IPV6_ADDRESS:
            addr_len = 16
        elif atyp == SOCKS5_ATYP_DOMAINNAME:
            if len(self.buf) < 5:
                return False, None
            addr_len = self.buf[5]
        else:
            return False, f"Unsupported address type in SOCKS5 response: {atyp}"

        # Total response length: version(1) + reply(1) + reserved(1) + atyp(1) + addr_len + port(2)
        total_len = 4 + 1 + addr_len + 2
        if atyp == SOCKS5_ATYP_DOMAINNAME:
            total_len += 1  # Add domain name length byte

        if len(self.buf) < total_len:
            return False, None

        # Remove the response from buffer and forward any remaining data
        self.buf = self.buf[total_len:]
        if self.buf:
            yield from self.receive_data(self.buf)
            self.buf = b""

        return True, None

    def _get_socks5_error_message(self, reply_code: int) -> str:
        """Get human-readable error message for SOCKS5 reply code."""
        error_messages = {
            SOCKS5_REP_SUCCEEDED: "Succeeded",
            SOCKS5_REP_GENERAL_FAILURE: "General failure",
            SOCKS5_REP_CONNECTION_NOT_ALLOWED: "Connection not allowed",
            SOCKS5_REP_NETWORK_UNREACHABLE: "Network unreachable",
            SOCKS5_REP_HOST_UNREACHABLE: "Host unreachable",
            SOCKS5_REP_CONNECTION_REFUSED: "Connection refused",
            SOCKS5_REP_TTL_EXPIRED: "TTL expired",
            SOCKS5_REP_COMMAND_NOT_SUPPORTED: "Command not supported",
            SOCKS5_REP_ADDRESS_TYPE_NOT_SUPPORTED: "Address type not supported",
        }
        return error_messages.get(reply_code, f"Unknown error code: {reply_code}") 