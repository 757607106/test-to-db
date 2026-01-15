import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def print_step(step):
    print(f"\n{'='*20} {step} {'='*20}")

import uuid

def test_llm_config_lifecycle():
    print_step("Testing LLM Config Lifecycle")
    
    unique_id = str(uuid.uuid4())[:8]
    model_name = f"test-model-{unique_id}"
    
    # 1. Create
    payload = {
        "provider": "TestProvider",
        "model_name": model_name,
        "model_type": "chat",
        "api_key": "test-key-placeholder",
        "base_url": "https://api.test.com",
        "is_active": True
    }
    
    print(f"Creating LLM Config: {payload['model_name']}")
    response = requests.post(f"{BASE_URL}/llm-configs/", json=payload)
    if response.status_code != 200:
        print(f"Failed to create LLM config: {response.text}")
        return False
    
    config_data = response.json()
    config_id = config_data['id']
    print(f"Created LLM Config ID: {config_id}")
    
    # 2. List
    print("Listing LLM Configs...")
    response = requests.get(f"{BASE_URL}/llm-configs/")
    configs = response.json()
    found = any(c['id'] == config_id for c in configs)
    if not found:
        print("Error: Created config not found in list")
        return False
    print("Verified config exists in list")

    # 3. Update
    update_payload = {
        "model_name": "test-model-v2-updated"
    }
    print(f"Updating LLM Config {config_id}...")
    response = requests.put(f"{BASE_URL}/llm-configs/{config_id}", json=update_payload)
    if response.status_code != 200:
        print(f"Failed to update: {response.text}")
        return False
    
    updated_data = response.json()
    if updated_data['model_name'] != "test-model-v2-updated":
        print("Error: Update verification failed")
        return False
    print("Update verified")

    # 4. Test Connection (Mock test expected to fail or return mock success depending on implementation)
    # Based on code, 'chat' type tries to connect to real API, which will fail with fake key
    # But let's check the response structure
    print("Testing connection...")
    test_payload = {
        "provider": "TestProvider",
        "model_name": "test-model-v1",
        "model_type": "chat",
        "api_key": "test-key-placeholder",
        "base_url": "https://api.test.com"
    }
    response = requests.post(f"{BASE_URL}/llm-configs/test", json=test_payload)
    print(f"Connection test response: {response.json()}")
    # We don't fail the test here because connection failure is expected with fake creds

    # 5. Delete
    print(f"Deleting LLM Config {config_id}...")
    response = requests.delete(f"{BASE_URL}/llm-configs/{config_id}")
    if response.status_code != 200:
        print(f"Failed to delete: {response.text}")
        return False
    
    # Verify deletion
    response = requests.get(f"{BASE_URL}/llm-configs/")
    configs = response.json()
    if any(c['id'] == config_id for c in configs):
        print("Error: Config still exists after deletion")
        return False
    print("Deletion verified")
    
    return True

def test_agent_profile_lifecycle():
    print_step("Testing Agent Profile Lifecycle")
    
    unique_id = str(uuid.uuid4())[:8]
    agent_name = f"Test Agent {unique_id}"
    
    # 1. Create
    payload = {
        "name": agent_name,
        "role_description": "A test agent for integration testing",
        "system_prompt": "You are a test agent.",
        "tools": ["tool1", "tool2"],
        "is_active": True
    }
    
    print(f"Creating Agent Profile: {payload['name']}")
    response = requests.post(f"{BASE_URL}/agent-profiles/", json=payload)
    if response.status_code != 200:
        print(f"Failed to create Agent Profile: {response.text}")
        return False
    
    agent_data = response.json()
    agent_id = agent_data['id']
    print(f"Created Agent Profile ID: {agent_id}")
    
    # 2. List
    print("Listing Agent Profiles...")
    response = requests.get(f"{BASE_URL}/agent-profiles/")
    agents = response.json()
    found = any(a['id'] == agent_id for a in agents)
    if not found:
        print("Error: Created agent not found in list")
        return False
    print("Verified agent exists in list")

    # 3. Update
    update_payload = {
        "role_description": "Updated description"
    }
    print(f"Updating Agent Profile {agent_id}...")
    response = requests.put(f"{BASE_URL}/agent-profiles/{agent_id}", json=update_payload)
    if response.status_code != 200:
        print(f"Failed to update: {response.text}")
        return False
    
    updated_data = response.json()
    if updated_data['role_description'] != "Updated description":
        print("Error: Update verification failed")
        return False
    print("Update verified")

    # 4. Delete
    print(f"Deleting Agent Profile {agent_id}...")
    response = requests.delete(f"{BASE_URL}/agent-profiles/{agent_id}")
    if response.status_code != 200:
        print(f"Failed to delete: {response.text}")
        return False
    
    # Verify deletion
    response = requests.get(f"{BASE_URL}/agent-profiles/")
    agents = response.json()
    if any(a['id'] == agent_id for a in agents):
        print("Error: Agent still exists after deletion")
        return False
    print("Deletion verified")
    
    return True

if __name__ == "__main__":
    try:
        # Check if server is running
        requests.get(f"{BASE_URL}/connections/")
    except requests.exceptions.ConnectionError:
        print("Error: Backend server is not running at http://localhost:8000")
        sys.exit(1)

    llm_success = test_llm_config_lifecycle()
    agent_success = test_agent_profile_lifecycle()
    
    if llm_success and agent_success:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
