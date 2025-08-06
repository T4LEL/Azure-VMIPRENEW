import azure.functions as func
import logging
import json
import os
from typing import Dict, Any, Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import ResourceNotFoundError, AzureError
import uuid

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

class IPChangeManager:
    def __init__(self):
        self.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.tenant_id = os.environ.get('AZURE_TENANT_ID')
        self.client_id = os.environ.get('AZURE_CLIENT_ID')
        self.client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        self.allowed_resource_groups = set(
            rg.strip() for rg in os.environ.get('ALLOWED_RESOURCE_GROUPS', '').split(',') if rg.strip()
        )
        
        if not self.subscription_id:
            raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
        
        # Initialize Azure credentials
        if self.client_id and self.client_secret and self.tenant_id:
            self.credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        else:
            self.credential = DefaultAzureCredential()
        
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
    
    def validate_resource_group(self, resource_group: str) -> bool:
        """Validate if the resource group is allowed"""
        if not self.allowed_resource_groups:
            return True  # If no restrictions, allow all
        return resource_group in self.allowed_resource_groups
    
    def find_vm_by_ip(self, target_ip: str) -> Optional[Dict[str, Any]]:
        """Find VM and its network interface by IP address"""
        try:
            # Get all network interfaces
            for nic in self.network_client.network_interfaces.list_all():
                if nic.ip_configurations:
                    for ip_config in nic.ip_configurations:
                        if ip_config.public_ip_address:
                            try:
                                # Get the actual public IP details
                                public_ip_resource_id = ip_config.public_ip_address.id
                                public_ip_parts = public_ip_resource_id.split('/')
                                public_ip_rg = public_ip_parts[4]
                                public_ip_name = public_ip_parts[-1]
                                
                                # Fetch the actual public IP resource to get the IP address
                                public_ip_resource = self.network_client.public_ip_addresses.get(
                                    public_ip_rg, public_ip_name
                                )
                                actual_ip_address = public_ip_resource.ip_address
                                
                                if actual_ip_address == target_ip:
                                    # Extract resource group from NIC ID
                                    nic_parts = nic.id.split('/')
                                    resource_group = nic_parts[4]
                                    
                                    # Validate resource group access
                                    if not self.validate_resource_group(resource_group):
                                        logging.warning(f"Access denied to resource group: {resource_group}")
                                        return None
                                    
                                    # Find associated VM
                                    if nic.virtual_machine:
                                        vm_parts = nic.virtual_machine.id.split('/')
                                        vm_name = vm_parts[-1]
                                        vm_resource_group = vm_parts[4]
                                        
                                        return {
                                            'vm_name': vm_name,
                                            'vm_resource_group': vm_resource_group,
                                            'nic_name': nic.name,
                                            'nic_resource_group': resource_group,
                                            'public_ip_name': public_ip_name,
                                            'public_ip_resource_group': public_ip_rg,
                                            'ip_config_name': ip_config.name
                                        }
                                        
                            except Exception as e:
                                logging.warning(f"Could not fetch public IP details for {ip_config.public_ip_address.id}: {str(e)}")
                                continue
            
            return None
        except Exception as e:
            logging.error(f"Error finding VM by IP: {str(e)}")
            return None
    
    def create_new_public_ip(self, resource_group: str, location: str) -> str:
        """Create a new public IP address"""
        try:
            new_ip_name = f"ip-{str(uuid.uuid4())[:8]}"
            
            public_ip_params = {
                'location': location,
                'public_ip_allocation_method': 'Static',
                'sku': {'name': 'Standard'},
                'tags': {
                    'CreatedBy': 'IPChangeAPI',
                    'Purpose': 'VM-IP-Replacement'
                }
            }
            
            # Create the public IP
            operation = self.network_client.public_ip_addresses.begin_create_or_update(
                resource_group, new_ip_name, public_ip_params
            )
            
            new_public_ip = operation.result()
            return new_ip_name, new_public_ip.ip_address
            
        except Exception as e:
            logging.error(f"Error creating new public IP: {str(e)}")
            raise
    
    def update_vm_ip(self, vm_info: Dict[str, Any], new_ip_name: str) -> str:
        """Update VM's network interface with new IP and delete old IP"""
        try:
            # Get the network interface
            nic = self.network_client.network_interfaces.get(
                vm_info['nic_resource_group'], 
                vm_info['nic_name']
            )
            
            # Get the new public IP resource
            new_public_ip = self.network_client.public_ip_addresses.get(
                vm_info['public_ip_resource_group'], 
                new_ip_name
            )
            
            # Update the IP configuration
            for ip_config in nic.ip_configurations:
                if ip_config.name == vm_info['ip_config_name']:
                    old_ip_name = vm_info['public_ip_name']
                    ip_config.public_ip_address = new_public_ip
                    break
            
            # Update the network interface
            update_operation = self.network_client.network_interfaces.begin_create_or_update(
                vm_info['nic_resource_group'], 
                vm_info['nic_name'], 
                nic
            )
            update_operation.result()
            
            # Delete the old public IP
            try:
                delete_operation = self.network_client.public_ip_addresses.begin_delete(
                    vm_info['public_ip_resource_group'], 
                    old_ip_name
                )
                delete_operation.result()
                logging.info(f"Successfully deleted old public IP: {old_ip_name}")
            except Exception as e:
                logging.warning(f"Could not delete old public IP {old_ip_name}: {str(e)}")
            
            return new_public_ip.ip_address
            
        except Exception as e:
            logging.error(f"Error updating VM IP: {str(e)}")
            raise

@app.route(route="change-vm-ip", methods=["POST"])
def change_vm_ip(req: func.HttpRequest) -> func.HttpResponse:
    """
    API endpoint to change a VM's public IP address
    
    Expected JSON payload:
    {
        "current_ip": "1.2.3.4"
    }
    
    Returns:
    {
        "success": true,
        "new_ip": "5.6.7.8",
        "vm_name": "my-vm",
        "message": "IP successfully changed"
    }
    """
    logging.info('IP change request received')
    
    try:
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON in request body"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not req_body or 'current_ip' not in req_body:
            return func.HttpResponse(
                json.dumps({"error": "Missing required field: current_ip"}),
                status_code=400,
                mimetype="application/json"
            )
        
        current_ip = req_body['current_ip']
        
        # Validate IP format (basic validation)
        if not current_ip or not isinstance(current_ip, str):
            return func.HttpResponse(
                json.dumps({"error": "Invalid IP address format"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Initialize IP change manager
        try:
            ip_manager = IPChangeManager()
        except ValueError as e:
            logging.error(f"Configuration error: {str(e)}")
            return func.HttpResponse(
                json.dumps({"error": "Service configuration error"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Find VM by current IP
        logging.info(f"Searching for VM with IP: {current_ip}")
        vm_info = ip_manager.find_vm_by_ip(current_ip)
        
        if not vm_info:
            return func.HttpResponse(
                json.dumps({"error": f"No VM found with IP address {current_ip} or access denied"}),
                status_code=404,
                mimetype="application/json"
            )
        
        logging.info(f"Found VM: {vm_info['vm_name']} in resource group: {vm_info['vm_resource_group']}")
        
        # Get VM location for new IP
        vm = ip_manager.compute_client.virtual_machines.get(
            vm_info['vm_resource_group'], 
            vm_info['vm_name']
        )
        
        # Create new public IP
        logging.info("Creating new public IP address")
        new_ip_name, new_ip_address = ip_manager.create_new_public_ip(
            vm_info['public_ip_resource_group'], 
            vm.location
        )
        
        logging.info(f"Created new public IP: {new_ip_name} with address: {new_ip_address}")
        
        # Update VM with new IP and delete old IP
        logging.info("Updating VM network interface")
        final_ip = ip_manager.update_vm_ip(vm_info, new_ip_name)
        
        response = {
            "success": True,
            "new_ip": final_ip,
            "vm_name": vm_info['vm_name'],
            "resource_group": vm_info['vm_resource_group'],
            "message": f"IP successfully changed from {current_ip} to {final_ip}"
        }
        
        logging.info(f"IP change completed successfully: {current_ip} -> {final_ip}")
        
        return func.HttpResponse(
            json.dumps(response),
            status_code=200,
            mimetype="application/json"
        )
        
    except AzureError as e:
        logging.error(f"Azure API error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Azure service error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="diagnose-vm", methods=["POST"])
def diagnose_vm(req: func.HttpRequest) -> func.HttpResponse:
    """
    Diagnostic endpoint to help troubleshoot VM discovery issues
    
    Expected JSON payload:
    {
        "current_ip": "1.2.3.4",
        "debug": true
    }
    """
    logging.info('VM diagnosis request received')
    
    try:
        # Parse request
        req_body = req.get_json()
        if not req_body or 'current_ip' not in req_body:
            return func.HttpResponse(
                json.dumps({"error": "Missing required field: current_ip"}),
                status_code=400,
                mimetype="application/json"
            )
        
        current_ip = req_body['current_ip']
        
        # Initialize manager
        try:
            ip_manager = IPChangeManager()
        except ValueError as e:
            return func.HttpResponse(
                json.dumps({"error": f"Configuration error: {str(e)}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Diagnostic information
        diagnostic_info = {
            "target_ip": current_ip,
            "subscription_id": ip_manager.subscription_id,
            "allowed_resource_groups": list(ip_manager.allowed_resource_groups) if ip_manager.allowed_resource_groups else "All resource groups allowed",
            "credential_type": type(ip_manager.credential).__name__,
            "network_interfaces_found": [],
            "vms_with_public_ips": [],
            "errors": []
        }
        
        try:
            # List all network interfaces with public IPs
            logging.info("Scanning network interfaces...")
            nic_count = 0
            
            for nic in ip_manager.network_client.network_interfaces.list_all():
                nic_count += 1
                if nic.ip_configurations:
                    for ip_config in nic.ip_configurations:
                        if ip_config.public_ip_address:
                            # Get the actual public IP details
                            try:
                                public_ip_resource_id = ip_config.public_ip_address.id
                                public_ip_parts = public_ip_resource_id.split('/')
                                public_ip_rg = public_ip_parts[4]
                                public_ip_name = public_ip_parts[-1]
                                
                                # Fetch the actual public IP resource to get the IP address
                                public_ip_resource = ip_manager.network_client.public_ip_addresses.get(
                                    public_ip_rg, public_ip_name
                                )
                                actual_ip_address = public_ip_resource.ip_address
                                
                            except Exception as e:
                                logging.warning(f"Could not fetch public IP details for {ip_config.public_ip_address.id}: {str(e)}")
                                actual_ip_address = None
                            
                            nic_info = {
                                "nic_name": nic.name,
                                "resource_group": nic.id.split('/')[4],
                                "public_ip": actual_ip_address,
                                "public_ip_resource_id": ip_config.public_ip_address.id,
                                "vm_attached": bool(nic.virtual_machine),
                                "vm_id": nic.virtual_machine.id if nic.virtual_machine else None
                            }
                            
                            diagnostic_info["vms_with_public_ips"].append(nic_info)
                            
                            # Check if this matches our target
                            if actual_ip_address == current_ip:
                                diagnostic_info["target_match"] = nic_info
                                
                                # Check resource group access
                                rg = nic.id.split('/')[4]
                                if ip_manager.allowed_resource_groups and rg not in ip_manager.allowed_resource_groups:
                                    diagnostic_info["errors"].append(f"Resource group '{rg}' not in allowed list")
            
            diagnostic_info["total_nics_scanned"] = nic_count
            
        except Exception as e:
            diagnostic_info["errors"].append(f"Error scanning network interfaces: {str(e)}")
            logging.error(f"Error in diagnostic scan: {str(e)}")
            
            # Try alternative approach if the main scan fails
            try:
                logging.info("Trying alternative approach - scanning all public IPs...")
                diagnostic_info["alternative_scan"] = []
                
                for public_ip in ip_manager.network_client.public_ip_addresses.list_all():
                    if public_ip.ip_address:
                        ip_info = {
                            "name": public_ip.name,
                            "resource_group": public_ip.id.split('/')[4],
                            "ip_address": public_ip.ip_address,
                            "associated_resource": public_ip.ip_configuration.id if public_ip.ip_configuration else None
                        }
                        diagnostic_info["alternative_scan"].append(ip_info)
                        
                        # Check if this matches our target
                        if public_ip.ip_address == current_ip:
                            diagnostic_info["target_match_alternative"] = ip_info
                            
            except Exception as alt_e:
                diagnostic_info["errors"].append(f"Alternative scan also failed: {str(alt_e)}")
        
        # Check if target IP was found
        if "target_match" not in diagnostic_info:
            diagnostic_info["errors"].append(f"No network interface found with public IP {current_ip}")
        
        return func.HttpResponse(
            json.dumps(diagnostic_info, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Diagnostic error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Diagnostic failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "VM IP Change API"}),
        status_code=200,
        mimetype="application/json"
    )