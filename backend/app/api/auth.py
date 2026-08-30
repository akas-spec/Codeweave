import httpx
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserResponse, GitHubCallbackRequest

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to extract user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


@router.get("/github/login")
async def github_login():
    """Redirect URL for GitHub OAuth login."""
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "scope": "read:user user:email repo",
        "redirect_uri": "http://localhost:3000/auth/callback",
    }
    auth_url = f"{GITHUB_AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"auth_url": auth_url}


@router.post("/github/callback", response_model=Token)
async def github_callback(request: GitHubCallbackRequest, db: AsyncSession = Depends(get_db)):
    """Handle GitHub OAuth callback - exchange code for token, create/update user."""
    # Exchange code for access token with robust retries for unstable network
    max_retries = 3
    token_data = None
    access_token = None
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_retries):
            try:
                token_response = await client.post(
                    GITHUB_TOKEN_URL,
                    json={
                        "client_id": settings.GITHUB_CLIENT_ID,
                        "client_secret": settings.GITHUB_CLIENT_SECRET,
                        "code": request.code,
                    },
                    headers={"Accept": "application/json"},
                )
                
                if token_response.status_code != 200:
                    raise HTTPException(status_code=400, detail="Failed to exchange code for token")
                    
                token_data = token_response.json()
                logger.error(f"GitHub token exchange response: {token_data}")
                access_token = token_data.get("access_token")
                
                if not access_token:
                    raise HTTPException(
                        status_code=400,
                        detail=f"GitHub OAuth error: {token_data.get('error_description', 'Unknown error')}"
                    )
                break # Success
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=504, detail=f"GitHub connection failed after {max_retries} attempts: {str(e)}")
                await asyncio.sleep(1) # Backoff before retry

        # Fetch user info from GitHub
        github_user = None
        for attempt in range(max_retries):
            try:
                user_response = await client.get(
                    GITHUB_USER_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )

                if user_response.status_code != 200:
                    raise HTTPException(status_code=400, detail="Failed to fetch GitHub user info")

                github_user = user_response.json()
                break # Success
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=504, detail=f"GitHub user info connection failed: {str(e)}")
                await asyncio.sleep(1) # Backoff

    # Create or update user in database
    result = await db.execute(
        select(User).where(User.github_id == github_user["id"])
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
            github_access_token=access_token,
        )
        db.add(user)
    else:
        user.username = github_user["login"]
        user.email = github_user.get("email")
        user.avatar_url = github_user.get("avatar_url")
        user.github_access_token = access_token
        user.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(user)

    # Create JWT token
    jwt_token = create_access_token({"sub": str(user.id), "username": user.username})
    return Token(access_token=jwt_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user
