"""
Diagnostic script to troubleshoot VM IP discovery issues
This script will help identify why the API can't find your VM
"""
import requests
import json
import sys

def test_permissions_and_discovery(base_url: str, function_key: str, target_ip: str):
    """Test the API with detailed error reporting"""
    
    print(f"🔍 Diagnosing VM discovery for IP: {target_ip}")
    print("=" * 60)
    
    # Test with diagnostic endpoint (we'll create this)
    diagnostic_url = f"{base_url}/api/diagnose-vm"
    params = {"code": function_key} if function_key else {}
    data = {"current_ip": target_ip, "debug": True}
    
    print("1. Testing diagnostic endpoint...")
    try:
        response = requests.post(diagnostic_url, params=params, json=data)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Diagnostic endpoint not available: {e}")
    
    # Test the main endpoint with more details
    print("\n2. Testing main endpoint...")
    change_url = f"{base_url}/api/change-vm-ip"
    
    try:
        response = requests.post(change_url, params=params, json={"current_ip": target_ip})
        print(f"   Status: {response.status_code}")
        result = response.json()
        print(f"   Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 404:
            print("\n🚨 VM Not Found - Possible Causes:")
            print("   1. Service Principal lacks 'Network Contributor' role")
            print("   2. Service Principal lacks 'Virtual Machine Contributor' role") 
            print("   3. VM is in a different subscription")
            print("   4. VM's public IP is not directly attached (load balancer, etc.)")
            print("   5. Resource group access restrictions")
            
        return result
        
    except Exception as e:
        print(f"   Request failed: {e}")
        return None

def suggest_fixes():
    """Provide step-by-step troubleshooting guide"""
    print("\n🔧 TROUBLESHOOTING STEPS:")
    print("=" * 60)
    
    print("\n1. VERIFY SERVICE PRINCIPAL PERMISSIONS:")
    print("   Go to: Azure Portal → Subscriptions → Your Subscription → Access control (IAM)")
    print("   Check if Service Principal 'add98b78-b333-46bb-ade6-452ec0e7b8de' has:")
    print("   ✓ Network Contributor role")
    print("   ✓ Virtual Machine Contributor role")
    
    print("\n2. VERIFY VM CONFIGURATION:")
    print("   Go to: Azure Portal → Virtual Machines → Your VM")
    print("   Check:")
    print("   ✓ VM has a public IP directly attached (not through load balancer)")
    print("   ✓ Public IP address matches exactly: 74.225.218.206")
    print("   ✓ Note the Resource Group name")
    
    print("\n3. TEST WITH RESOURCE GROUP RESTRICTION:")
    print("   If your VM is in a specific resource group, update ALLOWED_RESOURCE_GROUPS")
    print("   Example: Set to 'your-vm-resource-group-name'")
    
    print("\n4. CHECK SUBSCRIPTION:")
    print("   Verify the VM is in subscription: b35f2a47-09e2-477e-8227-e18db38f8770")

def main():
    if len(sys.argv) < 3:
        print("Usage: python diagnose_vm.py <BASE_URL> <TARGET_IP> [FUNCTION_KEY]")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    target_ip = sys.argv[2]
    function_key = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = test_permissions_and_discovery(base_url, function_key, target_ip)
    suggest_fixes()
    
    print(f"\n📋 CONFIGURATION SUMMARY:")
    print(f"   Subscription ID: b35f2a47-09e2-477e-8227-e18db38f8770")
    print(f"   Service Principal: add98b78-b333-46bb-ade6-452ec0e7b8de")
    print(f"   Target IP: {target_ip}")
    print(f"   Function App: {base_url}")

if __name__ == "__main__":
    main()
