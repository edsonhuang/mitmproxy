# Multi-Upstream Proxy Mode

The `multiupstream` mode allows mitmproxy to route traffic to different upstream proxies based on configurable rules. This is useful for load balancing, geographic routing, or service-specific proxy selection.

## Usage

```bash
mitmproxy --mode multiupstream:config_dir
mitmdump --mode multiupstream:config_dir
mitmweb --mode multiupstream:config_dir
```

Where `config_dir` is the path to a directory containing proxy configuration files.

## Configuration

The configuration directory should contain one of the following files:
- `proxies.yaml` (recommended)
- `proxies.yml`
- `proxies.json`

### YAML Configuration Format

```yaml
proxies:
  - name: "proxy1"
    url: "http://proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.google.com"
      - type: "port"
        port: 443
      - type: "default"
  
  - name: "proxy2"
    url: "http://proxy2.example.com:8080"
    weight: 2
    rules:
      - type: "host_pattern"
        pattern: "*.github.com"
```

### JSON Configuration Format

```json
{
  "proxies": [
    {
      "name": "proxy1",
      "url": "http://proxy1.example.com:8080",
      "weight": 1,
      "rules": [
        {
          "type": "host_pattern",
          "pattern": "*.google.com"
        },
        {
          "type": "default"
        }
      ]
    }
  ]
}
```

## Configuration Options

### Proxy Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique name for the proxy |
| `url` | string | Yes | Proxy URL (http://host:port or https://host:port) |
| `weight` | integer | No | Weight for load balancing (default: 1) |
| `rules` | array | Yes | Array of routing rules |

### Rule Types

#### Host Pattern Rule
Routes traffic based on hostname patterns.

```yaml
- type: "host_pattern"
  pattern: "*.example.com"
```

**Pattern Syntax:**
- `*` matches any sequence of characters
- `*.example.com` matches `www.example.com`, `api.example.com`, etc.
- `example.com` matches only `example.com`

#### Port Rule
Routes traffic based on destination port.

```yaml
- type: "port"
  port: 443
```

#### Default Rule
Acts as a fallback when no other rules match.

```yaml
- type: "default"
```

## Load Balancing

When multiple proxies match the same request, the system uses weighted random selection:

```yaml
proxies:
  - name: "proxy1"
    url: "http://proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.example.com"
  
  - name: "proxy2"
    url: "http://proxy2.example.com:8080"
    weight: 2
    rules:
      - type: "host_pattern"
        pattern: "*.example.com"
```

In this example, `proxy2` will be selected twice as often as `proxy1` for matching requests.

## Examples

### Basic Configuration

```yaml
proxies:
  - name: "google_proxy"
    url: "http://proxy1.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.google.com"
      - type: "host_pattern"
        pattern: "*.googleapis.com"
  
  - name: "github_proxy"
    url: "http://proxy2.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.github.com"
  
  - name: "default_proxy"
    url: "http://proxy3.example.com:8080"
    weight: 1
    rules:
      - type: "default"
```

### Load Balanced Configuration

```yaml
proxies:
  - name: "primary_proxy"
    url: "http://primary.example.com:8080"
    weight: 3
    rules:
      - type: "host_pattern"
        pattern: "*.example.com"
  
  - name: "backup_proxy"
    url: "http://backup.example.com:8080"
    weight: 1
    rules:
      - type: "host_pattern"
        pattern: "*.example.com"
  
  - name: "fallback_proxy"
    url: "http://fallback.example.com:8080"
    weight: 1
    rules:
      - type: "default"
```

## Error Handling

- **Invalid configuration directory**: mitmproxy will start but not load any proxy configurations
- **Invalid configuration file**: mitmproxy will start but not load any proxy configurations
- **Invalid proxy URL**: Requests matching that proxy will fail
- **No matching proxy**: Requests will be processed without an upstream proxy

## Troubleshooting

### Check Configuration Loading

Start mitmproxy with verbose logging to see configuration loading messages:

```bash
mitmdump --mode multiupstream:config_dir --set console_eventlog_verbosity=info
```

### Verify Proxy Connectivity

Test your upstream proxies directly:

```bash
curl -x http://proxy.example.com:8080 http://httpbin.org/ip
```

### Common Issues

1. **502 Bad Gateway**: Upstream proxy is not accessible
2. **Configuration not loaded**: Check file format and directory path
3. **No traffic routing**: Verify rule patterns match your target hosts

## Integration with Other mitmproxy Features

The multiupstream mode works with all standard mitmproxy features:
- Scripts and addons
- Certificate handling
- Request/response modification
- Flow export
- Web interface

## Performance Considerations

- Rule matching is performed for each request
- Host pattern matching uses regex compilation
- Weighted selection uses random number generation
- Configuration is loaded once at startup 