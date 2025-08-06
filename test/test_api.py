"""
Test script for the VM IP Change API
"""
import requests
import json
import sys
import os

def test_api(base_url: str, function_key: str, current_ip: str):
    """Test the VM IP Change API"""
    
    # Test health endpoint
    print("Testing health endpoint...")
    health_url = f"{base_url}/api/health"
    params = {"code": function_key} if function_key else {}
    
    try:
        response = requests.get(health_url, params=params)
        print(f"Health check status: {response.status_code}")
        print(f"Health check response: {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False
    
    # Test IP change endpoint
    print(f"\nTesting IP change for: {current_ip}")
    change_url = f"{base_url}/api/change-vm-ip"
    data = {"current_ip": current_ip}
    
    try:
        response = requests.post(change_url, params=params, json=data)
        print(f"IP change status: {response.status_code}")
        print(f"IP change response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✅ Success! New IP: {result.get('new_ip')}")
                return True
            else:
                print("❌ Request succeeded but operation failed")
                return False
        else:
            print("❌ Request failed")
            return False
            
    except Exception as e:
        print(f"IP change test failed: {e}")
        return False

def main():
    """Main test function"""
    if len(sys.argv) < 3:
        print("Usage: python test_api.py <BASE_URL> <CURRENT_IP> [FUNCTION_KEY]")
        print("Example: python test_api.py http://localhost:7071 20.123.45.67")
        print("Example: python test_api.py https://myapp.azurewebsites.net 20.123.45.67 your-function-key")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    current_ip = sys.argv[2]
    function_key = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Testing VM IP Change API")
    print(f"Base URL: {base_url}")
    print(f"Current IP: {current_ip}")
    print(f"Function Key: {'provided' if function_key else 'not provided'}")
    print("-" * 50)
    
    success = test_api(base_url, function_key, current_ip)
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
