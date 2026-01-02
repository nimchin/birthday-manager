#!/usr/bin/env python3
"""
Backend API Testing for Birthday Organizer Bot
Tests all API endpoints and functionality
"""
import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any

class BirthdayBotAPITester:
    def __init__(self, base_url="https://birthdayhelper.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.passed_tests = []

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            self.passed_tests.append(name)
            print(f"✅ {name}: PASSED {details}")
        else:
            self.failed_tests.append({"test": name, "details": details})
            print(f"❌ {name}: FAILED {details}")

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["status", "bot_active", "timestamp"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Health Endpoint - Fields", False, f"Missing fields: {missing_fields}")
                else:
                    self.log_test("Health Endpoint - Fields", True, "All required fields present")
                
                # Check bot_active is boolean
                if isinstance(data.get("bot_active"), bool):
                    self.log_test("Health Endpoint - Bot Active Type", True, f"bot_active: {data['bot_active']}")
                else:
                    self.log_test("Health Endpoint - Bot Active Type", False, f"bot_active should be boolean, got: {type(data.get('bot_active'))}")
                
                # Check status
                if data.get("status") == "healthy":
                    self.log_test("Health Endpoint - Status", True, "Status is healthy")
                else:
                    self.log_test("Health Endpoint - Status", False, f"Expected 'healthy', got: {data.get('status')}")
                    
            else:
                self.log_test("Health Endpoint - HTTP Status", False, f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Health Endpoint - Connection", False, f"Error: {str(e)}")

    def test_stats_endpoint(self):
        """Test /api/stats endpoint"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["total_users", "total_teams", "active_events", "completed_events"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Stats Endpoint - Fields", False, f"Missing fields: {missing_fields}")
                else:
                    self.log_test("Stats Endpoint - Fields", True, "All required fields present")
                
                # Check all values are integers
                all_integers = all(isinstance(data.get(field), int) for field in required_fields)
                if all_integers:
                    self.log_test("Stats Endpoint - Data Types", True, "All stats are integers")
                else:
                    self.log_test("Stats Endpoint - Data Types", False, "Some stats are not integers")
                
                # Check non-negative values
                all_non_negative = all(data.get(field, -1) >= 0 for field in required_fields)
                if all_non_negative:
                    self.log_test("Stats Endpoint - Values", True, "All stats are non-negative")
                else:
                    self.log_test("Stats Endpoint - Values", False, "Some stats are negative")
                    
            else:
                self.log_test("Stats Endpoint - HTTP Status", False, f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Stats Endpoint - Connection", False, f"Error: {str(e)}")

    def test_webhook_info_endpoint(self):
        """Test /api/telegram/webhook-info endpoint"""
        try:
            response = requests.get(f"{self.api_url}/telegram/webhook-info", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if webhook URL is set
                webhook_url = data.get("url")
                if webhook_url:
                    expected_webhook = f"{self.base_url}/api/telegram/webhook"
                    if webhook_url == expected_webhook:
                        self.log_test("Webhook Info - URL", True, f"Webhook URL correctly set: {webhook_url}")
                    else:
                        self.log_test("Webhook Info - URL", False, f"Expected {expected_webhook}, got {webhook_url}")
                else:
                    self.log_test("Webhook Info - URL", False, "Webhook URL not set")
                
                # Check other fields exist
                expected_fields = ["has_custom_certificate", "pending_update_count", "max_connections"]
                for field in expected_fields:
                    if field in data:
                        self.log_test(f"Webhook Info - {field}", True, f"{field}: {data[field]}")
                    else:
                        self.log_test(f"Webhook Info - {field}", False, f"Missing field: {field}")
                        
            else:
                self.log_test("Webhook Info - HTTP Status", False, f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Webhook Info - Connection", False, f"Error: {str(e)}")

    def test_webhook_post_endpoint(self):
        """Test /api/telegram/webhook POST endpoint"""
        try:
            # Test with minimal valid Telegram update structure
            test_update = {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "date": int(datetime.now().timestamp()),
                    "chat": {
                        "id": -1001234567890,
                        "type": "group",
                        "title": "Test Group"
                    },
                    "from": {
                        "id": 123456789,
                        "is_bot": False,
                        "first_name": "Test",
                        "username": "testuser"
                    },
                    "text": "/start"
                }
            }
            
            response = requests.post(
                f"{self.api_url}/telegram/webhook",
                json=test_update,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log_test("Webhook POST - Valid Update", True, "Webhook accepts valid updates")
                else:
                    self.log_test("Webhook POST - Valid Update", False, f"Unexpected response: {data}")
            else:
                self.log_test("Webhook POST - HTTP Status", False, f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Webhook POST - Connection", False, f"Error: {str(e)}")

    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check basic fields
                if "message" in data and "version" in data:
                    self.log_test("Root Endpoint - Fields", True, "Basic fields present")
                else:
                    self.log_test("Root Endpoint - Fields", False, "Missing basic fields")
                    
            else:
                self.log_test("Root Endpoint - HTTP Status", False, f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Root Endpoint - Connection", False, f"Error: {str(e)}")

    def test_invalid_endpoints(self):
        """Test invalid endpoints return proper errors"""
        try:
            response = requests.get(f"{self.api_url}/nonexistent", timeout=10)
            
            if response.status_code == 404:
                self.log_test("Invalid Endpoint - 404", True, "Returns 404 for invalid endpoints")
            else:
                self.log_test("Invalid Endpoint - 404", False, f"Expected 404, got {response.status_code}")
                
        except Exception as e:
            self.log_test("Invalid Endpoint - Connection", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all API tests"""
        print("🎂 Starting Birthday Organizer Bot API Tests...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test all endpoints
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_stats_endpoint()
        self.test_webhook_info_endpoint()
        self.test_webhook_post_endpoint()
        self.test_invalid_endpoints()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {self.tests_run}")
        print(f"   Passed: {self.tests_passed}")
        print(f"   Failed: {len(self.failed_tests)}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   • {test['test']}: {test['details']}")
        
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": len(self.failed_tests),
            "success_rate": self.tests_passed/self.tests_run*100 if self.tests_run > 0 else 0,
            "failed_details": self.failed_tests,
            "passed_test_names": self.passed_tests
        }

def main():
    """Main test runner"""
    tester = BirthdayBotAPITester()
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    if results["failed_tests"] == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {results['failed_tests']} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())