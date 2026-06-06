"""
Railway Deployment Automation Script

This script automates the deployment of the Universal Translator to Railway.
It handles environment variable configuration, deployment triggering, and verification.

Usage:
    python scripts/deploy_railway.py --project-id <railway-project-id> --token <railway-token>

Requirements:
    - Railway CLI installed and authenticated
    - Railway project ID
    - Railway API token
"""

import subprocess
import json
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, Optional
import requests


class RailwayDeployer:
    """Automated Railway deployment manager."""
    
    def __init__(self, project_id: str, railway_token: str):
        self.project_id = project_id
        self.railway_token = railway_token
        self.api_base = "https://backboard.railway.app/graphql/v2"
        self.headers = {
            "Authorization": f"Bearer {railway_token}",
            "Content-Type": "application/json",
        }
    
    def execute_railway_command(self, command: str) -> tuple[bool, str]:
        """Execute a Railway CLI command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def get_project_info(self) -> Optional[Dict]:
        """Get project information from Railway API."""
        query = """
        query($projectId: String!) {
            project(id: $projectId) {
                id
                name
                url
                services {
                    id
                    name
                    status
                    url
                }
            }
        }
        """
        
        try:
            response = requests.post(
                self.api_base,
                json={"query": query, "variables": {"projectId": self.project_id}},
                headers=self.headers,
            )
            data = response.json()
            return data.get("data", {}).get("project")
        except Exception as e:
            print(f"Error getting project info: {e}")
            return None
    
    def set_environment_variable(self, service_id: str, key: str, value: str) -> bool:
        """Set an environment variable for a service."""
        mutation = """
        mutation($input: VariableInput!) {
            variableUpsert(input: $input) {
                id
                key
                value
            }
        }
        """
        
        input_data = {
            "serviceId": service_id,
            "key": key,
            "value": value,
        }
        
        try:
            response = requests.post(
                self.api_base,
                json={"query": mutation, "variables": {"input": input_data}},
                headers=self.headers,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error setting variable {key}: {e}")
            return False
    
    def configure_production_env(self, project_info: Dict, env_file: str = "railway-production-env.txt") -> bool:
        """Configure production environment variables."""
        env_path = Path(env_file)
        if not env_path.exists():
            print(f"Environment file not found: {env_file}")
            return False
        
        # Parse environment file
        env_vars = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        
        # Get service ID
        services = project_info.get("services", [])
        if not services:
            print("No services found in project")
            return False
        
        service_id = services[0]["id"]
        print(f"Configuring environment for service: {services[0]['name']}")
        
        # Set critical variables first
        critical_vars = ["JWT_SECRET", "USERS", "ALLOWED_ORIGINS", "ENVIRONMENT"]
        
        for var in critical_vars:
            if var in env_vars:
                value = env_vars[var]
                if value.startswith("<") or value == "":
                    print(f"⚠️  {var} needs manual configuration (placeholder detected)")
                    continue
                
                print(f"Setting {var}...")
                if not self.set_environment_variable(service_id, var, value):
                    print(f"✗ Failed to set {var}")
                    return False
                print(f"✓ Set {var}")
        
        # Set optional variables
        optional_vars = [k for k in env_vars.keys() if k not in critical_vars]
        for var in optional_vars:
            value = env_vars[var]
            if value.startswith("<") or value == "":
                continue  # Skip placeholders
            
            print(f"Setting {var}...")
            self.set_environment_variable(service_id, var, value)
        
        print("✓ Environment variables configured")
        return True
    
    def trigger_deployment(self, service_id: str) -> bool:
        """Trigger a new deployment."""
        mutation = """
        mutation($input: ServiceDeployInput!) {
            serviceDeploy(input: $input) {
                id
                status
            }
        }
        """
        
        input_data = {"serviceId": service_id}
        
        try:
            response = requests.post(
                self.api_base,
                json={"query": mutation, "variables": {"input": input_data}},
                headers=self.headers,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error triggering deployment: {e}")
            return False
    
    def wait_for_deployment(self, service_id: str, timeout: int = 600) -> bool:
        """Wait for deployment to complete."""
        print(f"Waiting for deployment (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            query = """
            query($serviceId: String!) {
                service(id: $serviceId) {
                    deployments {
                        edges {
                            node {
                                id
                                status
                                createdAt
                            }
                        }
                    }
                }
            }
            """
            
            try:
                response = requests.post(
                    self.api_base,
                    json={"query": query, "variables": {"serviceId": service_id}},
                    headers=self.headers,
                )
                data = response.json()
                deployments = data.get("data", {}).get("service", {}).get("deployments", {}).get("edges", [])
                
                if deployments:
                    latest = deployments[0]["node"]
                    status = latest["status"]
                    print(f"  Deployment status: {status}")
                    
                    if status in ["SUCCESS", "FAILED", "CRASHED"]:
                        return status == "SUCCESS"
                
                time.sleep(10)
            except Exception as e:
                print(f"Error checking deployment status: {e}")
                time.sleep(10)
        
        print("Deployment timeout")
        return False
    
    def verify_deployment(self, project_url: str) -> bool:
        """Verify the deployment is healthy."""
        print(f"Verifying deployment at {project_url}...")
        
        # Check health endpoint
        try:
            response = requests.get(f"{project_url}/health", timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("ready"):
                    print("✓ Health check passed")
                    return True
                else:
                    print("✗ Health check failed: not ready")
                    return False
            else:
                print(f"✗ Health check failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False
    
    def deploy(self, env_file: str = "railway-production-env.txt") -> bool:
        """Execute full deployment process."""
        print("=" * 70)
        print("RAILWAY DEPLOYMENT AUTOMATION")
        print("=" * 70)
        
        # Get project info
        print("\n1. Getting project information...")
        project_info = self.get_project_info()
        if not project_info:
            print("✗ Failed to get project info")
            return False
        
        print(f"✓ Project: {project_info['name']}")
        print(f"  URL: {project_info['url']}")
        
        # Configure environment
        print("\n2. Configuring environment variables...")
        if not self.configure_production_env(project_info, env_file):
            print("✗ Failed to configure environment")
            return False
        
        # Get service ID
        services = project_info.get("services", [])
        if not services:
            print("✗ No services found")
            return False
        
        service_id = services[0]["id"]
        
        # Trigger deployment
        print("\n3. Triggering deployment...")
        if not self.trigger_deployment(service_id):
            print("✗ Failed to trigger deployment")
            return False
        
        print("✓ Deployment triggered")
        
        # Wait for deployment
        print("\n4. Waiting for deployment to complete...")
        if not self.wait_for_deployment(service_id):
            print("✗ Deployment failed or timed out")
            return False
        
        print("✓ Deployment completed successfully")
        
        # Verify deployment
        print("\n5. Verifying deployment...")
        project_url = project_info["url"]
        if not self.verify_deployment(project_url):
            print("✗ Deployment verification failed")
            return False
        
        print("\n" + "=" * 70)
        print("DEPLOYMENT SUCCESSFUL")
        print("=" * 70)
        print(f"Backend URL: {project_url}")
        print(f"WebSocket URL: {project_url.replace('https://', 'wss://')}")
        print(f"Health Check: {project_url}/health")
        print(f"Diagnostics: {project_url}/diagnostics")
        print()
        print("Next steps:")
        print("1. Update translator-mobile/.env with EXPO_PUBLIC_API_URL=" + project_url)
        print("2. Rebuild the mobile app")
        print("3. Test the deployment")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="Deploy to Railway")
    parser.add_argument("--project-id", required=True, help="Railway project ID")
    parser.add_argument("--token", required=True, help="Railway API token")
    parser.add_argument("--env-file", default="railway-production-env.txt", help="Environment file")
    
    args = parser.parse_args()
    
    deployer = RailwayDeployer(
        project_id=args.project_id,
        railway_token=args.token,
    )
    
    success = deployer.deploy(env_file=args.env_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
