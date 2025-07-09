# Proxy Modes

mitmproxy supports several different proxy modes, each designed for specific use cases.

## Regular Mode

The default mode. mitmproxy acts as a standard HTTP(S) proxy that clients connect to using the HTTP CONNECT method.

```bash
mitmproxy --mode regular
```

## Transparent Mode

A transparent proxy that intercepts traffic at the network level without requiring client configuration.

```bash
mitmproxy --mode transparent
```

See [Transparent Mode](modes/transparent.md) for detailed setup instructions.

## Upstream Mode

Routes all traffic through a single upstream proxy.

```bash
mitmproxy --mode upstream:http://proxy.example.com:8080
```

## Multi-Upstream Mode

Routes traffic to different upstream proxies based on configurable rules. Supports load balancing and service-specific routing.

```bash
mitmproxy --mode multiupstream:config_dir
```

See [Multi-Upstream Mode](multiupstream-mode.md) for detailed configuration and examples.

## Reverse Mode

Acts as a reverse proxy, forwarding requests to a fixed upstream server.

```bash
mitmproxy --mode reverse:http://backend.example.com:8080
```

## SOCKS5 Mode

Acts as a SOCKS5 proxy.

```bash
mitmproxy --mode socks5
```

## DNS Mode

Acts as a DNS server.

```bash
mitmproxy --mode dns
```

## WireGuard Mode

Acts as a WireGuard server.

```bash
mitmproxy --mode wireguard
```

## Local Mode

OS-level transparent proxy for local traffic redirection.

```bash
mitmproxy --mode local
```

## TUN Mode

Creates a TUN interface for intercepting traffic.

```bash
mitmproxy --mode tun:utun0
```

## Mode Comparison

| Mode | Use Case | Client Config Required | Network Config Required |
|------|----------|----------------------|------------------------|
| Regular | Standard proxy | Yes | No |
| Transparent | Network interception | No | Yes |
| Upstream | Single upstream proxy | Yes | No |
| Multi-Upstream | Multiple upstream proxies | Yes | No |
| Reverse | Backend proxy | No | Yes |
| SOCKS5 | SOCKS5 proxy | Yes | No |
| DNS | DNS server | Yes | No |
| WireGuard | VPN server | Yes | No |
| Local | Local traffic | No | Yes |
| TUN | Network interface | No | Yes |

## Choosing the Right Mode

- **Regular**: Most common use case, standard proxy setup
- **Transparent**: When you can't configure clients but control the network
- **Upstream**: When you need to route through another proxy
- **Multi-Upstream**: When you need load balancing or service-specific routing
- **Reverse**: When proxying a specific backend service
- **SOCKS5**: When clients only support SOCKS5
- **DNS**: When you need DNS-level interception
- **WireGuard**: When you need VPN functionality
- **Local**: When you need OS-level traffic redirection
- **TUN**: When you need low-level network interface access 