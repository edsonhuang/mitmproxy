"""
Test cases for the MultiUpstreamAddon.
"""

import json
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mitmproxy.addons import multi_upstream
from mitmproxy.proxy.mode_specs import MultiUpstreamMode, ProxyMode
from mitmproxy.test import taddons
from mitmproxy.test import tflow


class TestMultiUpstreamAddon:
    """Test cases for MultiUpstreamAddon."""

    def test_proxy_rule_creation(self):
        """Test ProxyRule creation."""
        rule = multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")
        assert rule.type == "host_pattern"
        assert rule.pattern == "*.example.com"

    def test_proxy_config_creation(self):
        """Test ProxyConfig creation."""
        rules = [multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")]
        config = multi_upstream.ProxyConfig(
            name="test_proxy",
            url="http://proxy.example.com:8080",
            weight=2,
            rules=rules
        )
        assert config.name == "test_proxy"
        assert config.url == "http://proxy.example.com:8080"
        assert config.weight == 2
        assert len(config.rules) == 1

    def test_load_yaml_config(self):
        """Test loading YAML configuration."""
        yaml_config = """
        proxies:
          - name: "test_proxy"
            url: "http://proxy.example.com:8080"
            weight: 1
            rules:
              - type: "host_pattern"
                pattern: "*.example.com"
          - name: "default"
            url: "http://default-proxy.example.com:8080"
            weight: 1
            rules:
              - type: "default"
                value: true
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "proxies.yaml"
            with open(config_file, 'w') as f:
                f.write(yaml_config)

            addon = multi_upstream.MultiUpstreamAddon()
            addon._load_configuration_from_dir(temp_dir)
            
            assert len(addon.proxy_configs) == 1
            assert addon.default_proxy is not None
            
            proxy = addon.proxy_configs[0]
            assert proxy.name == "test_proxy"
            assert proxy.url == "http://proxy.example.com:8080"
            assert len(proxy.rules) == 1
            assert proxy.rules[0].type == "host_pattern"
            assert proxy.rules[0].pattern == "*.example.com"
            
            default = addon.default_proxy
            assert default.name == "default"
            assert default.url == "http://default-proxy.example.com:8080"

    def test_load_json_config(self):
        """Test loading JSON configuration."""
        json_config = {
            "proxies": [
                {
                    "name": "test_proxy",
                    "url": "http://proxy.example.com:8080",
                    "weight": 1,
                    "rules": [
                        {
                            "type": "host_pattern",
                            "pattern": "*.example.com"
                        }
                    ]
                }
            ]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "proxies.json"
            with open(config_file, 'w') as f:
                json.dump(json_config, f)

            addon = multi_upstream.MultiUpstreamAddon()
            addon._load_configuration_from_dir(temp_dir)
            
            assert len(addon.proxy_configs) == 1
            proxy = addon.proxy_configs[0]
            assert proxy.name == "test_proxy"

    def test_host_pattern_matching(self):
        """Test host pattern matching."""
        rule = multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")
        
        # Create mock flow
        flow = Mock()
        flow.request.host = "www.example.com"
        flow.request.pretty_host = flow.request.host
        
        addon = multi_upstream.MultiUpstreamAddon()
        assert addon._matches_rule(flow, rule)
        
        flow.request.host = "api.example.com"
        flow.request.pretty_host = flow.request.host
        assert addon._matches_rule(flow, rule)
        
        flow.request.host = "other.com"
        flow.request.pretty_host = flow.request.host
        assert not addon._matches_rule(flow, rule)

    def test_port_matching(self):
        """Test port matching."""
        rule = multi_upstream.ProxyRule(type="port", port=443)
        
        flow = Mock()
        flow.request.port = 443
        
        addon = multi_upstream.MultiUpstreamAddon()
        assert addon._matches_rule(flow, rule)
        
        flow.request.port = 80
        assert not addon._matches_rule(flow, rule)

    def test_default_rule_matching(self):
        """Test default rule matching."""
        rule = multi_upstream.ProxyRule(type="default", value=True)
        
        flow = Mock()
        
        addon = multi_upstream.MultiUpstreamAddon()
        assert addon._matches_rule(flow, rule)

    def test_proxy_selection(self):
        """Test proxy selection logic."""
        # Set up test configuration
        proxy1 = multi_upstream.ProxyConfig(
            name="proxy1",
            url="http://proxy1.example.com:8080",
            weight=1,
            rules=[multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")]
        )
        proxy2 = multi_upstream.ProxyConfig(
            name="proxy2",
            url="http://proxy2.example.com:8080",
            weight=2,
            rules=[multi_upstream.ProxyRule(type="host_pattern", pattern="*.google.com")]
        )
        default = multi_upstream.ProxyConfig(
            name="default",
            url="http://default-proxy.example.com:8080",
            weight=1,
            rules=[multi_upstream.ProxyRule(type="default", value=True)]
        )
        
        addon = multi_upstream.MultiUpstreamAddon()
        addon.proxy_configs = [proxy1, proxy2]
        addon.default_proxy = default
        addon.config_loaded = True
        
        # Test matching proxy1
        flow = Mock()
        flow.request.host = "www.example.com"
        flow.request.pretty_host = flow.request.host
        
        selected = addon._select_proxy(flow)
        assert selected.name == "proxy1"
        
        # Test matching proxy2
        flow.request.host = "www.google.com"
        flow.request.pretty_host = flow.request.host
        
        selected = addon._select_proxy(flow)
        assert selected.name == "proxy2"
        
        # Test default proxy
        flow.request.host = "unknown.com"
        flow.request.pretty_host = flow.request.host
        
        selected = addon._select_proxy(flow)
        assert selected.name == "default"

    def test_weighted_selection(self):
        """Test weighted proxy selection."""
        proxy1 = multi_upstream.ProxyConfig(
            name="proxy1",
            url="http://proxy1.example.com:8080",
            weight=1,
            rules=[multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")]
        )
        proxy2 = multi_upstream.ProxyConfig(
            name="proxy2",
            url="http://proxy2.example.com:8080",
            weight=2,
            rules=[multi_upstream.ProxyRule(type="host_pattern", pattern="*.example.com")]
        )
        
        addon = multi_upstream.MultiUpstreamAddon()
        addon.proxy_configs = [proxy1, proxy2]
        addon.config_loaded = True
        
        flow = Mock()
        flow.request.host = "www.example.com"
        flow.request.pretty_host = flow.request.host
        
        # Test multiple selections to verify weighted distribution
        selections = []
        for _ in range(100):
            selected = addon._select_proxy(flow)
            selections.append(selected.name)
        
        # Should have both proxies selected, with proxy2 more frequently
        assert "proxy1" in selections
        assert "proxy2" in selections
        
        proxy2_count = selections.count("proxy2")
        proxy1_count = selections.count("proxy1")
        
        # proxy2 should be selected roughly twice as often as proxy1
        assert proxy2_count > proxy1_count

    def test_proxy_address_parsing(self):
        """Test proxy address parsing."""
        proxy = multi_upstream.ProxyConfig(
            name="test_proxy",
            url="http://proxy.example.com:8080",
            weight=1,
            rules=[multi_upstream.ProxyRule(type="default", value=True)]
        )
        
        addon = multi_upstream.MultiUpstreamAddon()
        addon.default_proxy = proxy
        addon.config_loaded = True
        
        flow = Mock()
        flow.request.host = "example.com"
        
        address = addon.proxy_address(flow)
        
        assert address is not None
        assert address[0] == "http"
        assert address[1][0] == "proxy.example.com"
        assert address[1][1] == 8080

    def test_invalid_proxy_url(self):
        """Test handling of invalid proxy URLs."""
        proxy = multi_upstream.ProxyConfig(
            name="test_proxy",
            url="invalid-url",
            weight=1,
            rules=[multi_upstream.ProxyRule(type="default", value=True)]
        )
        
        addon = multi_upstream.MultiUpstreamAddon()
        addon.default_proxy = proxy
        addon.config_loaded = True
        
        flow = Mock()
        flow.request.host = "example.com"
        flow.request.pretty_host = flow.request.host
        
        address = addon.proxy_address(flow)
        
        assert address is None

    def test_no_matching_proxy(self):
        """Test behavior when no proxy matches."""
        flow = Mock()
        flow.request.host = "example.com"
        
        # No proxies configured
        addon = multi_upstream.MultiUpstreamAddon()
        addon.proxy_configs = []
        addon.default_proxy = None
        addon.config_loaded = True
        
        selected = addon._select_proxy(flow)
        assert selected is None

    def test_request_handler_not_multi_upstream_mode(self):
        """Test that request handler doesn't process non-multi_upstream modes."""
        addon = multi_upstream.MultiUpstreamAddon()
        
        with taddons.context(addon) as tctx:
            # Set up a regular flow (not multi_upstream mode)
            f = tflow.tflow()
            f.client_conn.proxy_mode = ProxyMode.parse("regular")
            
            # Mock the proxy_address method to verify it's not called
            with patch.object(addon, 'proxy_address') as mock_proxy_address:
                addon.request(f)
                mock_proxy_address.assert_not_called()

    def test_request_handler_multi_upstream_mode(self):
        """Test that request handler processes multi_upstream mode correctly."""
        addon = multi_upstream.MultiUpstreamAddon()
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up a multi_upstream flow
            f = tflow.tflow()
            f.client_conn.proxy_mode = MultiUpstreamMode(
                full_spec=f"multi_upstream:{temp_dir}",
                data=temp_dir,
                custom_listen_host=None,
                custom_listen_port=None
            )
            # Mock the proxy_address method to return a valid address
            mock_address = ("http", ("proxy.example.com", 8080))
            with patch.object(addon, 'proxy_address', return_value=mock_address):
                addon.request(f)
                assert f.server_conn.via == mock_address

    def test_config_directory_not_exists(self):
        """Test handling of non-existent configuration directory."""
        addon = multi_upstream.MultiUpstreamAddon()
        addon._load_configuration_from_dir("/non/existent/path")
        
        assert not addon.config_loaded
        assert len(addon.proxy_configs) == 0
        assert addon.default_proxy is None

    def test_config_directory_no_files(self):
        """Test handling of empty configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            addon = multi_upstream.MultiUpstreamAddon()
            addon._load_configuration_from_dir(temp_dir)
            
            assert not addon.config_loaded
            assert len(addon.proxy_configs) == 0
            assert addon.default_proxy is None

    def test_invalid_config_file_format(self):
        """Test handling of invalid configuration file format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "proxies.yaml"
            with open(config_file, 'w') as f:
                f.write("invalid: yaml: content: [")
            
            addon = multi_upstream.MultiUpstreamAddon()
            addon._load_configuration_from_dir(temp_dir)
            
            assert not addon.config_loaded

    def test_config_file_no_proxies_section(self):
        """Test handling of configuration file without proxies section."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "proxies.yaml"
            with open(config_file, 'w') as f:
                yaml.dump({"other_section": []}, f)
            
            addon = multi_upstream.MultiUpstreamAddon()
            addon._load_configuration_from_dir(temp_dir)
            
            assert not addon.config_loaded 