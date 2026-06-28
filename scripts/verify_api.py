import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=== STARTING AUTHENTICATION AND API VERIFICATION ===")

    # 1. Health check verification
    print("\n[Test 1] Checking /health endpoint...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, "Health check failed"
    health_data = resp.json()
    assert health_data.get("status") == "healthy", "Status should be healthy"
    print("[OK] /health works and reports status = healthy")

    # 2. Register first administrator
    print("\n[Test 2] Registering first administrator...")
    admin_payload = {
        "email": "admin@enterprise.com",
        "password": "SecurePassword123",
        "first_name": "System",
        "last_name": "Admin",
        "role": "Administrator"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=admin_payload)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 201, "First administrator registration failed"
    user_data = resp.json()
    assert user_data.get("email") == admin_payload["email"], "Email mismatch"
    assert user_data.get("role") == "Administrator", "Role mismatch"
    print("[OK] First administrator registered successfully")

    # 3. Login with registered credentials
    print("\n[Test 3] Logging in with correct credentials...")
    login_data = {
        "username": admin_payload["email"],
        "password": admin_payload["password"]
    }
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, "Login failed"
    token_data = resp.json()
    access_token = token_data.get("access_token")
    assert access_token is not None, "Access token not generated"
    assert token_data.get("token_type") == "bearer", "Token type mismatch"
    print("[OK] Login succeeded, JWT token generated successfully")

    # 4. Access secure endpoint GET /api/v1/auth/me
    print("\n[Test 4] Querying GET /api/v1/auth/me with JWT token...")
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, "Accessing /me failed"
    profile_data = resp.json()
    assert profile_data.get("email") == admin_payload["email"], "Profile email mismatch"
    assert profile_data.get("role") == "Administrator", "Profile role mismatch"
    print("[OK] GET /api/v1/auth/me works and returns correct profile details")

    # 5. Login with invalid password
    print("\n[Test 5] Attempting login with incorrect password...")
    invalid_login_data = {
        "username": admin_payload["email"],
        "password": "WrongPassword123"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=invalid_login_data)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
    assert resp.status_code == 401, "Invalid login did not return 401"
    print("[OK] Invalid login correctly returns 401 Unauthorized")

    # 6. Handle duplicate email registration
    print("\n[Test 6] Registering user with duplicate email...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=admin_payload, headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
    assert resp.status_code == 409, "Duplicate registration did not return 409 Conflict"
    print("[OK] Duplicate registration handled correctly and returns 409 Conflict")

    print("\n=== ALL AUTHENTICATION AND API VERIFICATION PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] VERIFICATION TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)
