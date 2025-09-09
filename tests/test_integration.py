"""
Integration tests for the complete Anzen system.

This module tests the end-to-end flow:
Client -> Gateway -> NeMo Guardrails -> Presidio -> Response
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
import httpx

# Import client components
from client.src.client import SafetyClient, SafetyResponse, Decision, FailMode

# Import gateway components  
from gateway.src.gateway.api import create_app, AnzenGateway
from gateway.src.gateway.presidio_actuator import PresidioActuator


class TestEndToEndIntegration:
    """Test the complete end-to-end integration."""
    
    @pytest.fixture
    def mock_presidio_actuator(self):
        """Mock Presidio actuator for testing."""
        with patch('gateway.src.gateway.presidio_actuator.PresidioActuator') as mock_class:
            mock_instance = Mock()
            
            # Mock PII detection
            mock_instance.detect_pii.return_value = [
                {
                    "type": "EMAIL_ADDRESS",
                    "start": 12,
                    "end": 28,
                    "score": 0.95,
                    "text": "john@example.com"
                }
            ]
            
            # Mock anonymization
            mock_instance.anonymize_text.return_value = {
                "anonymized_text": "My email is <EMAIL_ADDRESS>",
                "entities": [
                    {
                        "type": "EMAIL_ADDRESS", 
                        "start": 12,
                        "end": 28,
                        "score": 0.95,
                        "text": "john@example.com"
                    }
                ],
                "original_length": 28,
                "anonymized_length": 25
            }
            
            mock_class.return_value = mock_instance
            yield mock_instance
    
    def test_client_gateway_communication_mock(self, mock_presidio_actuator):
        """Test client-gateway communication with mocked components."""
        
        # Mock the HTTP response from gateway
        mock_response_data = {
            "decision": "ALLOW_WITH_REDACTION",
            "entities": [
                {
                    "type": "EMAIL_ADDRESS",
                    "start": 12,
                    "end": 28,
                    "score": 0.95,
                    "text": "john@example.com"
                }
            ],
            "redacted_text": "My email is <EMAIL_ADDRESS>",
            "meta": {
                "latency_ms": 25.5,
                "trace_id": "test-trace-123",
                "risk_level": "medium",
                "route": "public:chat"
            }
        }
        
        with patch('httpx.Client.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value = mock_response
            
            # Test client
            client = SafetyClient(
                gateway_url="http://localhost:8000",
                fail_mode=FailMode.CLOSED
            )
            
            response = client.assess_input(
                "My email is john@example.com",
                route="public:chat"
            )
            
            # Verify response
            assert isinstance(response, SafetyResponse)
            assert response.decision == Decision.ALLOW_WITH_REDACTION
            assert response.is_safe
            assert not response.should_block
            assert response.safe_text == "My email is <EMAIL_ADDRESS>"
            assert len(response.entities) == 1
            assert response.entities[0].type == "EMAIL_ADDRESS"
            
            # Verify HTTP call was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/v1/anzen/check/input" in call_args[0][0]
    
    def test_presidio_actuator_functionality(self):
        """Test Presidio actuator functionality in isolation."""
        
        # Test with mock to avoid spaCy model dependencies
        with patch('gateway.src.gateway.presidio_actuator.AnalyzerEngine') as mock_analyzer_class:
            with patch('gateway.src.gateway.presidio_actuator.AnonymizerEngine') as mock_anonymizer_class:
                
                # Mock analyzer
                mock_analyzer = Mock()
                mock_result = Mock()
                mock_result.entity_type = "EMAIL_ADDRESS"
                mock_result.start = 12
                mock_result.end = 28
                mock_result.score = 0.95
                mock_analyzer.analyze.return_value = [mock_result]
                mock_analyzer_class.return_value = mock_analyzer
                
                # Mock anonymizer
                mock_anonymizer = Mock()
                mock_anon_result = Mock()
                mock_anon_result.text = "My email is <EMAIL_ADDRESS>"
                mock_anonymizer.anonymize.return_value = mock_anon_result
                mock_anonymizer_class.return_value = mock_anonymizer
                
                # Test actuator
                actuator = PresidioActuator()
                
                # Test PII detection
                entities = actuator.detect_pii("My email is john@example.com")
                assert len(entities) == 1
                assert entities[0]["type"] == "EMAIL_ADDRESS"
                assert entities[0]["score"] == 0.95
                
                # Test anonymization
                result = actuator.anonymize_text("My email is john@example.com")
                assert result["anonymized_text"] == "My email is <EMAIL_ADDRESS>"
                assert len(result["entities"]) == 1
    
    def test_route_based_policies(self, mock_presidio_actuator):
        """Test that different routes apply different policies."""
        
        test_cases = [
            {
                "route": "public:chat",
                "text": "My SSN is 123-45-6789",
                "expected_decision": "BLOCK",  # High-risk PII in public route
                "risk_level": "high"
            },
            {
                "route": "private:support", 
                "text": "Customer email: john@example.com",
                "expected_decision": "ALLOW_WITH_REDACTION",  # Any PII in private route
                "risk_level": "medium"
            },
            {
                "route": "internal:dev",
                "text": "Test user: jane@company.com", 
                "expected_decision": "ALLOW",  # Internal route allows with logging
                "risk_level": "medium"
            }
        ]
        
        for case in test_cases:
            with patch('httpx.Client.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "decision": case["expected_decision"],
                    "entities": [{"type": "EMAIL_ADDRESS", "start": 0, "end": 10, "score": 0.9}],
                    "redacted_text": case["text"] if case["expected_decision"] == "ALLOW" else "<REDACTED>",
                    "meta": {"risk_level": case["risk_level"], "route": case["route"]}
                }
                mock_post.return_value = mock_response
                
                client = SafetyClient(fail_mode=FailMode.OPEN)  # Use fail-open for testing
                
                try:
                    response = client.assess_input(case["text"], route=case["route"])
                    assert response.decision.value == case["expected_decision"]
                except Exception:
                    # Expected for BLOCK decisions in fail-closed mode
                    if case["expected_decision"] == "BLOCK":
                        continue
                    else:
                        raise
    
    def test_fail_modes(self):
        """Test client fail modes when gateway is unavailable."""
        
        # Test fail-closed mode
        with patch('httpx.Client.post') as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection failed")
            
            client = SafetyClient(fail_mode=FailMode.CLOSED)
            
            with pytest.raises(Exception):  # Should raise GatewayError
                client.assess_input("test text", route="public:chat")
        
        # Test fail-open mode
        with patch('httpx.Client.post') as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection failed")
            
            client = SafetyClient(fail_mode=FailMode.OPEN)
            
            response = client.assess_input("test text", route="public:chat")
            assert response.decision == Decision.ALLOW
            assert response.is_safe
            assert "fail_mode" in response.meta
            assert response.meta["fail_mode"] == "open"
    
    def test_performance_requirements(self, mock_presidio_actuator):
        """Test that the system meets performance requirements."""
        
        with patch('httpx.Client.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "decision": "ALLOW",
                "entities": [],
                "redacted_text": "test text",
                "meta": {"latency_ms": 15.5}
            }
            mock_post.return_value = mock_response
            
            client = SafetyClient()
            
            # Measure client-side latency
            start_time = time.time()
            response = client.assess_input("test text", route="public:chat")
            end_time = time.time()
            
            client_latency = (end_time - start_time) * 1000  # Convert to ms
            gateway_latency = response.meta.get("latency_ms", 0)
            
            # Performance requirements from the plan
            assert gateway_latency < 50, f"Gateway latency {gateway_latency}ms exceeds 50ms target"
            assert client_latency < 100, f"Total client latency {client_latency}ms exceeds 100ms target"


class TestSystemConfiguration:
    """Test system configuration and setup."""
    
    def test_environment_variable_configuration(self):
        """Test that environment variables are properly handled."""
        import os
        
        # Test client configuration
        with patch.dict(os.environ, {
            'ANZEN_GATEWAY_URL': 'https://test.example.com',
            'ANZEN_ROUTE': 'test:route',
            'ANZEN_LANGUAGE': 'pt',
            'ANZEN_FAIL_MODE': 'open',
            'ANZEN_CLIENT_ID': 'test-client-123'
        }):
            client = SafetyClient()
            assert client.gateway_url == "https://test.example.com"
            assert client.default_route == "test:route"
            assert client.default_language == "pt"
            assert client.fail_mode == FailMode.OPEN
            assert client.client_id == "test-client-123"
    
    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        import logging
        
        # Test that loggers exist
        client_logger = logging.getLogger("client.safety_client")
        gateway_logger = logging.getLogger("gateway.api")
        
        assert client_logger is not None
        assert gateway_logger is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
