# Azure VM IP Change API

A simple Azure Functions API that changes the public IP address of Azure VMs. Provide a current IP address, and the API will find the VM, create a new public IP, and update the VM.

## Features

- 🔒 **Secure**: Uses Azure Service Principal authentication
- 🔍 **Auto-discovery**: Finds VMs by their current public IP
- 🆕 **Automatic**: Creates new IP and cleans up the old one
- ✅ **Error handling**: Clear error messages

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure `local.settings.json`:**
   ```json
   {
     "Values": {
       "AZURE_SUBSCRIPTION_ID": "your-subscription-id",
       "AZURE_TENANT_ID": "your-tenant-id",
       "AZURE_CLIENT_ID": "your-client-id",
       "AZURE_CLIENT_SECRET": "your-client-secret"
     }
   }
   ```

3. **Run locally:**
   ```bash
   func start
   ```

## API Usage

### Change VM IP
**POST** `/api/change-vm-ip`

**Request:**
```json
{
  "current_ip": "20.123.45.67"
}
```

**Response:**
```json
{
  "success": true,
  "new_ip": "20.234.56.78",
  "vm_name": "my-vm",
  "resource_group": "my-rg"
}
```

## Using in Python Scripts

Here's how to use this API from another Python script:

### Quick & Simple (One-Liner Style)

```python
import requests

def change_ip(current_ip, api_url="http://localhost:7071", function_key=None):
    """Change VM IP with one simple function call"""
    url = f"{api_url}/api/change-vm-ip"
    params = {"code": function_key} if function_key else {}
    response = requests.post(url, params=params, json={"current_ip": current_ip})
    return response.json()

# Usage - Just one line!
result = change_ip("20.123.45.67")
print(f"New IP: {result.get('new_ip')}" if result.get('success') else f"Error: {result.get('error')}")
```

**For production (with function key):**
```python
# Change IP on deployed Azure Function
result = change_ip(
    current_ip="20.123.45.67",
    api_url="https://your-function-app.azurewebsites.net",
    function_key="your-function-key"
)
```

### Simple Example

```python
import requests
import json
import time

class VMIPChanger:
    def __init__(self, api_url, function_key):
        self.api_url = api_url.rstrip('/')
        self.function_key = function_key
    
    def change_vm_ip(self, current_ip):
        """Change the IP of a VM and return the new IP"""
        url = f"{self.api_url}/api/change-vm-ip"
        params = {"code": self.function_key} if self.function_key else {}
        data = {"current_ip": current_ip}
        
        try:
            response = requests.post(url, params=params, json=data, timeout=300)
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                return result.get("new_ip")
            else:
                raise Exception(f"API Error: {result.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Request failed: {e}")
    
    def health_check(self):
        """Check if the API is healthy"""
        url = f"{self.api_url}/api/health"
        params = {"code": self.function_key} if self.function_key else {}
        
        try:
            response = requests.get(url, params=params, timeout=30)
            return response.status_code == 200
        except:
            return False

# Usage example
def main():
    # Configuration
    API_URL = "https://your-function-app.azurewebsites.net"
    FUNCTION_KEY = "your-function-key"  # or None for local development
    
    # Initialize the IP changer
    ip_changer = VMIPChanger(API_URL, FUNCTION_KEY)
    
    # Check if API is healthy
    if not ip_changer.health_check():
        print("❌ API is not responding")
        return
    
    # Change VM IP
    current_ip = "20.123.45.67"
    print(f"🔄 Changing IP for VM with current IP: {current_ip}")
    
    try:
        new_ip = ip_changer.change_vm_ip(current_ip)
        print(f"✅ Success! New IP: {new_ip}")
        
        # Wait a bit for the change to propagate
        print("⏳ Waiting for IP change to propagate...")
        time.sleep(30)
        
        print(f"🎉 VM IP successfully changed from {current_ip} to {new_ip}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
```

### Advanced Example with Retry Logic

```python
import requests
import json
import time
import logging
from typing import Optional, Dict, Any

class VMIPChanger:
    def __init__(self, api_url: str, function_key: Optional[str] = None, max_retries: int = 3):
        self.api_url = api_url.rstrip('/')
        self.function_key = function_key
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.api_url}{endpoint}"
        params = kwargs.get('params', {})
        
        if self.function_key:
            params['code'] = self.function_key
            kwargs['params'] = params
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}: {method} {url}")
                response = self.session.request(method, url, timeout=300, **kwargs)
                response.raise_for_status()
                return response.json()
                
            except requests.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"All {self.max_retries} attempts failed. Last error: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def change_vm_ip(self, current_ip: str) -> Dict[str, Any]:
        """Change VM IP and return full response"""
        self.logger.info(f"Changing IP for VM: {current_ip}")
        
        result = self._make_request(
            'POST', 
            '/api/change-vm-ip',
            json={"current_ip": current_ip}
        )
        
        if not result.get("success"):
            raise Exception(f"IP change failed: {result.get('error', 'Unknown error')}")
        
        self.logger.info(f"IP changed successfully: {current_ip} -> {result.get('new_ip')}")
        return result
    
    def health_check(self) -> bool:
        """Check API health"""
        try:
            result = self._make_request('GET', '/api/health')
            return result.get('status') == 'healthy'
        except:
            return False

# Example usage in a larger application
def rotate_vm_ips(vm_ips: list, api_url: str, function_key: str):
    """Rotate IPs for multiple VMs"""
    ip_changer = VMIPChanger(api_url, function_key)
    results = []
    
    if not ip_changer.health_check():
        raise Exception("API health check failed")
    
    for current_ip in vm_ips:
        try:
            result = ip_changer.change_vm_ip(current_ip)
            results.append({
                'old_ip': current_ip,
                'new_ip': result.get('new_ip'),
                'vm_name': result.get('vm_name'),
                'status': 'success'
            })
            
            # Wait between requests to avoid rate limiting
            time.sleep(5)
            
        except Exception as e:
            results.append({
                'old_ip': current_ip,
                'error': str(e),
                'status': 'failed'
            })
    
    return results

# Example usage
if __name__ == "__main__":
    vm_ips = ["20.123.45.67", "20.123.45.68", "20.123.45.69"]
    
    results = rotate_vm_ips(
        vm_ips=vm_ips,
        api_url="https://your-function-app.azurewebsites.net",
        function_key="your-function-key"
    )
    
    # Print results
    for result in results:
        if result['status'] == 'success':
            print(f"✅ {result['vm_name']}: {result['old_ip']} -> {result['new_ip']}")
        else:
            print(f"❌ {result['old_ip']}: {result['error']}")
```

## Deploy to Azure

```bash
# Deploy to Azure Functions
func azure functionapp publish YOUR_FUNCTION_APP_NAME
```

## Testing

Tests are located in the `test/` folder:

```bash
# Run tests
cd test
python test_api.py http://localhost:7071 20.123.45.67
```
