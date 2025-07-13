# Multi-Upstream Proxy Mode for mitmproxy

Multi-upstream proxy mode allows mitmproxy to route traffic to different upstream proxies based on configurable rules with weighted load balancing and session affinity support.

## Features

- 🔄 **Load Balancing**: Distribute traffic across multiple upstream proxies with weighted selection
- 🎯 **Rule-Based Routing**: Route traffic based on host patterns, ports, or default rules
- 🔗 **Session Affinity**: Keep WebSocket connections on the same proxy for consistent performance
- 🔐 **Authentication Support**: Support HTTP Basic authentication for upstream proxies
- 🧦 **SOCKS5 Support**: Full support for SOCKS5 upstream proxies with authentication
- 🌐 **WebSocket Support**: Proper WebSocket proxying through HTTP upgrade requests
- ⚖️ **Weighted Selection**: Configure proxy weights for load balancing

## Installation

Multi-upstream mode is integrated into mitmproxy core. No additional installation required.

## Configuration

### Basic Configuration

Create a YAML configuration file (e.g., `proxies.yaml`):

```yaml
proxies:
  - name: "proxy1"
    url: "http://proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.google.com"
      - type: "default"
  
  - name: "proxy2"
    url: "http://proxy2.example.com:8080"
    weight: 2
    rules:
      - type: "host_pattern"
        pattern: "*.baidu.com"
```

### Authentication Configuration

#### Method 1: URL-based Authentication (Recommended)

```yaml
proxies:
  - name: "proxy1"
    url: "http://username:password@proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "default"
  
  - name: "proxy2"
    url: "http://another_user:another_pass@proxy2.example.com:8080"
    weight: 1
    rules:
      - type: "default"
```

#### Method 2: Separate Authentication Fields

```yaml
proxies:
  - name: "proxy1"
    url: "http://proxy1.example.com:8080"
    username: "username"
    password: "password"
    weight: 1
    rules:
      - type: "default"
```

### SOCKS5 Configuration

```yaml
proxies:
  - name: "socks5-proxy"
    url: "socks5://username:password@proxy.example.com:1080"
    weight: 1
    rules:
      - type: "default"
  
  - name: "socks5-noauth"
    url: "socks5://proxy.example.com:1080"
    weight: 1
    rules:
      - type: "default"
```

## Usage

### Command Line

```bash
# Basic usage
mitmproxy --mode multiupstream:/path/to/config/directory

# With custom port
mitmproxy --mode multiupstream:/path/to/config/directory --listen-port 8080

# With verbose logging
mitmproxy --mode multiupstream:/path/to/config/directory --verbose
```

### Configuration Directory Structure

```
config/
├── proxies.yaml          # Main configuration (loaded first)
├── proxies_socks5.yaml   # SOCKS5 configuration
└── other_config.yaml     # Other configurations
```

## Configuration Options

### Proxy Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique proxy identifier |
| `url` | string | Yes | Proxy URL with scheme (http/https/socks5) |
| `weight` | integer | No | Load balancing weight (default: 1) |
| `username` | string | No | Authentication username |
| `password` | string | No | Authentication password |
| `rules` | array | Yes | Routing rules |

### Rule Types

#### Host Pattern Rule

Route traffic based on hostname patterns:

```yaml
rules:
  - type: "host_pattern"
    pattern: "*.example.com"  # Supports wildcards
```

#### Port Rule

Route traffic based on destination port:

```yaml
rules:
  - type: "port"
    port: 443
```

#### Default Rule

Use as fallback when no other rules match:

```yaml
rules:
  - type: "default"
```

## Load Balancing

### Weighted Selection

Proxies with higher weights receive more traffic:

```yaml
proxies:
  - name: "primary"
    url: "http://primary.example.com:8080"
    weight: 3  # Receives 75% of traffic
    rules:
      - type: "default"
  
  - name: "secondary"
    url: "http://secondary.example.com:8080"
    weight: 1  # Receives 25% of traffic
    rules:
      - type: "default"
```

### Session Affinity

WebSocket connections maintain session affinity to ensure consistent performance:

- Connections to the same host are routed to the same proxy
- Session affinity is maintained for the duration of the connection
- Automatic cleanup when connections close

## Authentication Support

### HTTP/HTTPS Proxies

- **Basic Authentication**: Username/password authentication
- **URL Encoding**: Special characters in credentials are automatically URL-encoded
- **Automatic Headers**: `Proxy-Authorization` headers are automatically added

### SOCKS5 Proxies

- **Username/Password Authentication**: Full SOCKS5 authentication support
- **No Authentication**: Support for SOCKS5 proxies without authentication
- **URL Parsing**: Credentials can be specified in the URL

## WebSocket Support

Multi-upstream mode fully supports WebSocket connections:

- **HTTP Upgrade**: WebSocket connections use HTTP upgrade requests
- **Session Affinity**: WebSocket connections maintain proxy affinity
- **SOCKS5 Tunneling**: WebSocket connections work through SOCKS5 proxies

## Examples

### Example 1: Simple Load Balancing

```yaml
proxies:
  - name: "proxy1"
    url: "http://proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "default"
  
  - name: "proxy2"
    url: "http://proxy2.example.com:8080"
    weight: 1
    rules:
      - type: "default"
```

### Example 2: Host-Based Routing

```yaml
proxies:
  - name: "google-proxy"
    url: "http://google-proxy.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.google.com"
  
  - name: "default-proxy"
    url: "http://default-proxy.example.com:8080"
    weight: 1
    rules:
      - type: "default"
```

### Example 3: Mixed HTTP and SOCKS5

```yaml
proxies:
  - name: "http-proxy"
    url: "http://user:pass@http-proxy.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.example.com"
  
  - name: "socks5-proxy"
    url: "socks5://user:pass@socks5-proxy.example.com:1080"
    weight: 1
    rules:
      - type: "default"
```

## Testing

### Integration Tests

Run the integration tests to verify functionality:

```bash
python test/integration/test_multiupstream_integration.py
```

### Manual Testing

1. Start mitmproxy with multiupstream mode:
   ```bash
   mitmproxy --mode multiupstream:test/integration/config --listen-port 8080
   ```

2. Test HTTP requests:
   ```bash
   curl -x http://127.0.0.1:8080 http://httpbin.org/ip
   ```

3. Test WebSocket connections:
   ```bash
   curl -x http://127.0.0.1:8080 -H "Connection: Upgrade" -H "Upgrade: websocket" http://echo.websocket.org
   ```

## Troubleshooting

### Common Issues

1. **Configuration Not Loaded**
   - Ensure configuration directory exists
   - Check file permissions
   - Verify YAML syntax

2. **Authentication Failures**
   - Verify credentials are correct
   - Check URL encoding for special characters
   - Ensure proxy supports Basic authentication

3. **WebSocket Issues**
   - WebSocket connections require HTTP upgrade requests
   - SOCKS5 proxies must support WebSocket tunneling
   - Check proxy server WebSocket support

### Debug Mode

Enable verbose logging for debugging:

```bash
mitmproxy --mode multiupstream:/path/to/config --verbose
```

## Architecture

### Components

1. **MultiUpstreamMode**: Proxy mode specification
2. **MultiUpstreamAddon**: Core addon for proxy selection and authentication
3. **Socks5UpstreamProxy**: SOCKS5 upstream proxy implementation
4. **HttpUpstreamProxy**: HTTP/HTTPS upstream proxy implementation

### Flow

1. **Configuration Loading**: Load proxy configurations from YAML/JSON files
2. **Rule Matching**: Match requests against proxy rules
3. **Proxy Selection**: Select appropriate proxy based on rules and weights
4. **Authentication**: Add authentication headers if required
5. **Session Affinity**: Maintain connection affinity for WebSocket

## Contributing

To contribute to multi-upstream mode:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This feature is part of mitmproxy and follows the same license terms. 