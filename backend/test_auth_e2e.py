import asyncio
import httpx
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

async def test_auth_flow():
    from app.main import app

    with patch("app.api.auth.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "mock_github_token"}
        
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 123456,
            "login": "testuser",
            "email": "test@example.com",
            "avatar_url": "https://example.com/avatar.png"
        }
        
        # Async methods
        from unittest.mock import AsyncMock
        mock_instance.post = AsyncMock(return_value=token_response)
        mock_instance.get = AsyncMock(return_value=user_response)

        with TestClient(app) as client:
            response = client.post("/api/auth/github/callback", json={"code": "dummy_code"})
            assert response.status_code == 200
            data = response.json()
            jwt_token = data["access_token"]
            
            me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
            assert me_response.status_code == 200
            print("E2E Auth Test Passed!")
            print("User profile:", me_response.json())

if __name__ == "__main__":
    asyncio.run(test_auth_flow())
