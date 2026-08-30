import requests
print("Testing GitHub Login Flow via Backend API...")

# Step 1: Get OAuth URL
res1 = requests.get("http://localhost:8000/api/auth/github/login")
print("Login Endpoint:", res1.status_code, res1.json())

# Step 2: Attempt token exchange with a dummy code
try:
    res2 = requests.post("http://localhost:8000/api/auth/github/callback", json={"code": "invalid_code"})
    print("Callback Endpoint:", res2.status_code, res2.json())
except requests.exceptions.Timeout:
    print("Callback Endpoint TIMED OUT!")
