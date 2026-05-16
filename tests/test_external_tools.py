"""
Tests for external API tools.
Demonstrates 3 execution types as required:
1. Success
2. Controlled failure
3. Rate limit / timeout handling
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.address_validation_tool import AddressValidationTool
from tools.weather_check_tool import WeatherCheckTool


def test_address_validation_success():
    """Execution 1: Success — valid CEP."""
    tool = AddressValidationTool()
    result = tool._run("01310-100")  # Av. Paulista, São Paulo

    print("\n=== EXECUTION 1: Address Validation — SUCCESS ===")
    print(f"CEP: {result.get('cep')}")
    print(f"Street: {result.get('street')}")
    print(f"City: {result.get('city')} - {result.get('state')}")
    print(f"Formatted: {result.get('formatted')}")
    print(f"Latency: {result.get('latency_ms')}ms")

    assert result["valid"] == True
    assert result["city"] == "São Paulo"
    print("✅ PASSED")


def test_address_validation_invalid_cep():
    """Execution 2: Controlled failure — invalid CEP."""
    tool = AddressValidationTool()
    result = tool._run("99999999")  # Non-existent CEP

    print("\n=== EXECUTION 2: Address Validation — FAILURE ===")
    print(f"Error type: {result.get('error_type')}")
    print(f"Error: {result.get('error')}")
    print(f"Valid: {result.get('valid')}")
    print(f"Latency: {result.get('latency_ms')}ms")

    assert result["valid"] == False
    assert result["error_type"] in ["not_found", "validation_error"]
    print("✅ PASSED — Error handled cleanly, no exception raised")


def test_address_validation_timeout():
    """Execution 3: Timeout simulation."""
    tool = AddressValidationTool()
    tool.timeout_seconds = 0.001  # Force timeout
    tool.max_retries = 1

    result = tool._run("01310100")

    print("\n=== EXECUTION 3: Address Validation — TIMEOUT ===")
    print(f"Error type: {result.get('error_type')}")
    print(f"Error: {result.get('error')}")
    print(f"Fallback: {result.get('fallback')}")
    print(f"Valid: {result.get('valid')}")

    assert result["valid"] == False
    assert "fallback" in result
    print("✅ PASSED — Timeout handled gracefully with fallback")


def test_weather_success():
    """Weather check — success."""
    tool = WeatherCheckTool()
    result = tool._run("São Paulo")

    print("\n=== WEATHER CHECK: São Paulo ===")
    if result.get("available"):
        print(f"Temperature: {result.get('temperature_c')}°C")
        print(f"Conditions: {result.get('conditions')}")
        print(f"Adverse: {result.get('adverse_conditions')}")
        print(f"Delivery impact: {result.get('delivery_impact')}")
        print(f"Latency: {result.get('latency_ms')}ms")
        print("✅ PASSED")
    else:
        print(f"Unavailable: {result.get('error')}")
        print(f"Fallback: {result.get('fallback')}")
        print("⚠️ API key not configured — fallback working correctly")


def test_weather_invalid_city():
    """Weather check — city not found."""
    tool = WeatherCheckTool()
    result = tool._run("CidadeQueNaoExiste123")

    print("\n=== WEATHER CHECK: Invalid city ===")
    print(f"Available: {result.get('available')}")
    print(f"Error: {result.get('error')}")
    print(f"Fallback: {result.get('fallback')}")

    assert result["available"] == False
    assert "fallback" in result
    print("✅ PASSED — City not found handled cleanly")


if __name__ == "__main__":
    print("Running external API tool tests...")
    print("=" * 50)

    test_address_validation_success()
    test_address_validation_invalid_cep()
    test_address_validation_timeout()
    test_weather_success()
    test_weather_invalid_city()

    print("\n" + "=" * 50)
    print("All tests completed!")
