#!/usr/bin/env python3
"""
Test script for the CrewAI Support Backend
"""

import requests
import json
import time

def test_backend():
    """Test the CrewAI support backend API"""

    base_url = "http://localhost:8000"

    # Test health endpoint
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Make sure it's running on port 8000")
        return

    # Test support endpoint with sample inquiries
    test_inquiries = [
        "My order hasn't arrived yet, I'm worried",
        "I was charged twice for my purchase",
        "I can't log into my account",
        "The website keeps crashing when I try to buy something",
        "How do I return an item?"
    ]

    print("\nTesting support endpoint with sample inquiries...")

    for i, inquiry in enumerate(test_inquiries, 1):
        print(f"\n--- Test {i}: {inquiry[:50]}... ---")

        payload = {"inquiry": inquiry}

        try:
            response = requests.post(
                f"{base_url}/api/support",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                print("✅ Support request processed successfully")
                print(f"   Category: {data['category']} (confidence: {data['category_confidence']}%)")
                print(f"   Sentiment: {data['sentiment']} (confidence: {data['sentiment_confidence']}%)")
                print(f"   Urgency: {data['urgency']}")
                print(f"   Escalation needed: {data['escalation_required']}")
                if data['escalation_required']:
                    print(f"   Reason: {data['escalation_reason']}")
                    print(f"   Reference ID: {data['reference_id']}")
                print(f"   Response preview: {data['response'][:100]}...")
                print(f"   Articles found: {len(data['articles'])}")
                print(f"   Processing steps: {len(data['steps'])}")
                
                # Show tool usage
                tool_events = [step for step in data['steps'] if 'tool_used' in step.get('details', {})]
                if tool_events:
                    print(f"   Tools used: {len(tool_events)}")
                    for event in tool_events[:3]:  # Show first 3
                        tool_name = event['details']['tool_used']
                        print(f"     - {event['agent']} used {tool_name}")
            else:
                print(f"❌ Support request failed: {response.status_code}")
                print(f"   Error: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")

        # Small delay between requests
        time.sleep(1)

    print("\n🎉 Backend testing completed!")

if __name__ == "__main__":
    test_backend()