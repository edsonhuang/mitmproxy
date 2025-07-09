"""
Multi Upstream Proxy Addon

This addon handles the multi_upstream mode by loading proxy configurations
from a directory and dynamically selecting the appropriate upstream proxy
based on rules defined in configuration files.
"""

import json
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import urllib.parse

from mitmproxy import ctx
from mitmproxy import http
from mitmproxy.net import server_spec
from mitmproxy.proxy.mode_specs import MultiUpstreamMode


@dataclass
class ProxyRule:
    """Represents a rule for proxy selection."""
    type: str
    pattern: Optional[str] = None
    port: Optional[int] = None
    value: Optional[Any] = None


@dataclass
class ProxyConfig:
    """Represents a proxy configuration."""
    name: str
    url: str
    weight: int = 1
    rules: List[ProxyRule] = None

    def __post_init__(self):
        if self.rules is None:
            self.rules = []


class MultiUpstreamAddon:
    """Addon for managing multiple upstream proxies in multi_upstream mode."""

    def __init__(self):
        self.proxy_configs: List[ProxyConfig] = []
        self.default_proxy: Optional[ProxyConfig] = None
        self.config_loaded = False

    def load(self, loader):
        pass

    def configure(self, updated):
        if "mode" in updated:
            try:
                config_dir = ctx.options.mode[0].split(":", 1)[1]
                self._load_configuration_from_dir(config_dir)
            except Exception as e:
                logging.error(f"Error in configure: {e}")
                raise

    def _load_configuration_from_dir(self, config_dir: str) -> None:
        try:
            logging.info(f"Loading configuration from directory: {config_dir}")
            config_path = Path(config_dir)
            if not config_path.exists():
                logging.warning(f"Configuration directory {config_dir} does not exist")
                return

            if not config_path.is_dir():
                logging.error(f"{config_dir} is not a directory")
                return

            self.proxy_configs = []
            self.default_proxy = None

            # Look for configuration files
            config_files = []
            for ext in ['*.yaml', '*.yml', '*.json']:
                config_files.extend(config_path.glob(ext))

            if not config_files:
                logging.warning(f"No configuration files found in {config_dir}")
                return

            # Load the first configuration file found
            config_file = config_files[0]
            logging.info(f"Loading configuration from {config_file}")

            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    if config_file.suffix == '.json':
                        config = json.load(f)
                    else:
                        config = yaml.safe_load(f)

                if 'proxies' not in config:
                    logging.error("No 'proxies' section found in configuration file")
                    return

                for proxy_data in config['proxies']:
                    rules = []
                    for rule_data in proxy_data.get('rules', []):
                        rule = ProxyRule(
                            type=rule_data['type'],
                            pattern=rule_data.get('pattern'),
                            port=rule_data.get('port'),
                            value=rule_data.get('value')
                        )
                        rules.append(rule)

                    proxy_config = ProxyConfig(
                        name=proxy_data['name'],
                        url=proxy_data['url'],
                        weight=proxy_data.get('weight', 1),
                        rules=rules
                    )

                    # Check if this is the default proxy
                    if any(rule.type == 'default' for rule in rules):
                        self.default_proxy = proxy_config
                    else:
                        self.proxy_configs.append(proxy_config)

                logging.info(f"Loaded {len(self.proxy_configs)} proxy configurations from {config_file}")
                if self.default_proxy:
                    logging.info(f"Default proxy: {self.default_proxy.name}")

                self.config_loaded = True

            except Exception as e:
                logging.error(f"Error loading configuration from {config_file}: {e}")
        except Exception as e:
            logging.error(f"Error in _load_configuration_from_dir: {e}")
            raise

    def _matches_rule(self, flow: http.HTTPFlow, rule: ProxyRule) -> bool:
        """Check if a flow matches a specific rule."""
        if rule.type == 'host_pattern':
            if rule.pattern:
                # 支持通配符 *，自动转为正则 .*
                pattern = re.escape(rule.pattern).replace(r'\*', '.*')
                host = getattr(flow.request, 'pretty_host', None) or getattr(flow.request, 'host', None)
                if not isinstance(host, str):
                    return False
                return re.search(pattern, host) is not None
        elif rule.type == 'port':
            if rule.port and getattr(flow.request, 'port', None) == rule.port:
                return True
        elif rule.type == 'default':
            return True
        return False

    def _select_proxy(self, flow: http.HTTPFlow) -> Optional[ProxyConfig]:
        """Select the appropriate proxy based on rules."""
        if not self.config_loaded:
            return None

        matching_proxies = []

        # Check all proxy configurations
        for proxy_config in self.proxy_configs:
            for rule in proxy_config.rules:
                if self._matches_rule(flow, rule):
                    matching_proxies.append(proxy_config)
                    break

        if not matching_proxies:
            # Use default proxy if no rules match
            if self.default_proxy:
                return self.default_proxy
            return None

        # If multiple proxies match, use weighted random selection
        if len(matching_proxies) > 1:
            total_weight = sum(proxy.weight for proxy in matching_proxies)
            weights = [proxy.weight / total_weight for proxy in matching_proxies]
            return random.choices(matching_proxies, weights=weights)[0]
        
        return matching_proxies[0]

    def proxy_address(self, flow: http.HTTPFlow) -> Optional[Tuple[str, Tuple[str, int]]]:
        """Set the upstream proxy for the flow."""
        if not self.config_loaded:
            return None

        selected_proxy = self._select_proxy(flow)
        if selected_proxy:
            try:
                parsed_url = urllib.parse.urlparse(selected_proxy.url)
                host = parsed_url.hostname
                port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
                scheme = parsed_url.scheme
                address = (host, port)
                if not scheme or not host or not port:
                    return None
                # Set the current upstream proxy information for compatibility
                if hasattr(flow.server_conn, 'proxy_mode') and hasattr(flow.server_conn.proxy_mode, 'set_current_upstream'):
                    flow.server_conn.proxy_mode.set_current_upstream(scheme, address)
                return (scheme, address)
            except Exception as e:
                logging.error(f"Error parsing proxy URL {selected_proxy.url}: {e}")
                return None
        return None

    def request(self, flow: http.HTTPFlow):
        """Handle HTTP request and set upstream proxy."""
        # Only process if we're in multiupstream mode
        if not isinstance(flow.client_conn.proxy_mode, MultiUpstreamMode):
            return
        
        proxy = self.proxy_address(flow)
        if proxy and len(proxy) == 2:
            scheme, address = proxy
            flow.server_conn.via = (scheme, address)


addons = [MultiUpstreamAddon()] 