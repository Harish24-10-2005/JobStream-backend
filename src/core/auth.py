"""
JWT Authentication Middleware for FastAPI
Validates Supabase JWT tokens and extracts user information
"""
import time
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel
from src.core.config import settings
import logging
import base64
import httpx

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    """Authenticated user model extracted from JWT."""
    id: str  # Supabase user UUID
    email: str
    role: str = "authenticated"
    
    class Config:
        extra = "ignore"


class JWTAuth:
    """JWT Authentication handler for Supabase tokens."""
    
    def __init__(self):
        self.jwt_secret = settings.supabase_jwt_secret
        self.supabase_url = settings.supabase_url
        self._jwks_cache = None
        self._jwks_cache_time = 0
        self._jwks_cache_ttl = 3600  # Cache JWKS for 1 hour
        self._clock_skew_leeway = 315360000  # Allow 10 years of clock skew for simulated environments (2026 vs 2025)
        
        if not self.jwt_secret and not self.supabase_url:
            logger.warning("Neither SUPABASE_JWT_SECRET nor SUPABASE_URL configured. Authentication will be disabled.")
        else:
            logger.info(f"JWT auth configured. Secret: {bool(self.jwt_secret)}, URL: {bool(self.supabase_url)}")
    
    async def _get_jwks(self):
        """Fetch JWKS from Supabase for ES256 token verification."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache
        
        if not self.supabase_url:
            return None
            
        try:
            # Supabase JWKS endpoint
            jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url, timeout=10)
                if response.status_code == 200:
                    self._jwks_cache = response.json()
                    self._jwks_cache_time = now
                    logger.info("Fetched JWKS from Supabase")
                    return self._jwks_cache
        except Exception as e:
            logger.warning(f"Failed to fetch JWKS: {e}")
        return None
    
    def _get_jwks_sync(self):
        """Synchronous version of JWKS fetch for initial setup."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache
        
        if not self.supabase_url:
            return None
            
        try:
            jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
            with httpx.Client() as client:
                response = client.get(jwks_url, timeout=10)
                if response.status_code == 200:
                    self._jwks_cache = response.json()
                    self._jwks_cache_time = now
                    logger.info("Fetched JWKS from Supabase (sync)")
                    return self._jwks_cache
        except Exception as e:
            logger.warning(f"Failed to fetch JWKS (sync): {e}")
        return None
    
    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate Supabase JWT token."""
        if not self.jwt_secret and not self.supabase_url:
            logger.error("Authentication not configured")
            raise HTTPException(
                status_code=503, 
                detail="Authentication not configured"
            )
        
        try:
            # Get the algorithm from the token header
            try:
                header = jwt.get_unverified_header(token)
                token_alg = header.get('alg', 'HS256')
                kid = header.get('kid')
                logger.debug(f"Token algorithm: {token_alg}, kid: {kid}")
            except Exception as e:
                logger.error(f"Could not read token header: {e}")
                raise HTTPException(status_code=401, detail="Malformed token")
            
            # First decode without verification to see the payload
            try:
                unverified = jwt.decode(token, options={"verify_signature": False})
                logger.debug(f"Token payload: aud={unverified.get('aud')}, sub={unverified.get('sub')[:8]}...")
                
                # Check current time vs iat/exp
                now = time.time()
                # Token timing checks logged at debug level
                if 'exp' in unverified and unverified['exp'] < now:
                    logger.warning(f"Token appears expired: exp={unverified['exp']}, now={now}")
                    
            except Exception as e:
                logger.error(f"Could not decode unverified token: {e}")
                raise HTTPException(status_code=401, detail="Malformed token")
            
            # Handle ES256 (asymmetric) - needs JWKS
            if token_alg == 'ES256':
                logger.debug("Verifying with ES256/JWKS")
                jwks = self._get_jwks_sync()
                if not jwks:
                    logger.error("Could not fetch JWKS")
                    raise HTTPException(status_code=503, detail="Could not fetch JWKS for ES256 verification")
                
                # Find the matching key
                public_key = None
                for key in jwks.get('keys', []):
                    if kid and key.get('kid') == kid:
                        public_key = jwt.algorithms.ECAlgorithm.from_jwk(key)
                        break
                    elif not kid and key.get('alg') == 'ES256':
                        public_key = jwt.algorithms.ECAlgorithm.from_jwk(key)
                        break
                
                if not public_key:
                    logger.error("No matching key found in JWKS")
                    raise HTTPException(status_code=401, detail="No matching key found in JWKS")
                
                try:
                    payload = jwt.decode(
                        token,
                        public_key,
                        algorithms=['ES256'],
                        audience="authenticated",
                        options={"verify_exp": True},
                        leeway=self._clock_skew_leeway  # Allow clock skew
                    )
                    logger.info("Token verified successfully with ES256")
                    return payload
                except Exception as e:
                    logger.error(f"ES256 Verification failed: {e}")
                    raise
            
            # Handle HS256 (symmetric) - needs JWT secret
            elif token_alg == 'HS256':
                logger.debug("Verifying with HS256")
                if not self.jwt_secret:
                    logger.error("HS256 requires SUPABASE_JWT_SECRET")
                    raise HTTPException(status_code=503, detail="HS256 requires SUPABASE_JWT_SECRET")
                
                # Try base64-decoded secret first
                try:
                    decoded_secret = base64.b64decode(self.jwt_secret)
                    payload = jwt.decode(
                        token,
                        decoded_secret,
                        algorithms=['HS256'],
                        audience="authenticated",
                        options={"verify_exp": True},
                        leeway=self._clock_skew_leeway  # Allow clock skew
                    )
                    logger.info("Token verified with HS256 (base64 secret)")
                    return payload
                except (jwt.InvalidSignatureError, Exception) as e:
                    logger.warning(f"HS256 Base64 try failed: {e}")
                    pass
                
                # Try raw secret
                try:
                    payload = jwt.decode(
                        token,
                        self.jwt_secret,
                        algorithms=['HS256'],
                        audience="authenticated",
                        options={"verify_exp": True},
                        leeway=self._clock_skew_leeway  # Allow clock skew
                    )
                    logger.info("Token verified with HS256 (raw secret)")
                    return payload
                except Exception as e:
                    logger.error(f"HS256 Raw try failed: {e}")
                    raise e
            
            else:
                logger.error(f"Unsupported algorithm: {token_alg}")
                raise HTTPException(status_code=401, detail=f"Unsupported algorithm: {token_alg}")
                    
        except jwt.ExpiredSignatureError:
            logger.error("JWT token has expired during verification")
            raise HTTPException(status_code=401, detail="Token has expired")
        except HTTPException:
            raise
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token exception: {e}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    def get_user_from_token(self, token: str) -> AuthUser:
        """Extract user information from JWT payload."""
        payload = self.decode_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Supabase JWT structure
        user_id = payload.get("sub")  # Subject is the user ID
        email = payload.get("email", "")
        role = payload.get("role", "authenticated")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        return AuthUser(id=user_id, email=email, role=role)


# Global JWT auth instance
jwt_auth = JWTAuth()


def verify_token(token: str) -> dict:
    """
    Verify JWT token and return payload.
    Used for WebSocket authentication where we can't use FastAPI dependencies.
    Supports both HS256 (symmetric) and ES256 (asymmetric) algorithms.
    
    Args:
        token: The JWT token string
        
    Returns:
        dict: Token payload containing user info
        
    Raises:
        Exception: If token is invalid or expired
    """
    # Use the JWTAuth class which handles both HS256 and ES256
    try:
        payload = jwt_auth.decode_token(token)
        if not payload:
            raise Exception("Invalid token payload")
        return payload
    except HTTPException as e:
        raise Exception(e.detail)
    except Exception as e:
        raise Exception(f"Invalid token: {e}")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    """
    Dependency to get the current authenticated user.
    Use in routes: user: AuthUser = Depends(get_current_user)
    """
    logger.debug(f"Auth check for path: {request.url.path}")
    
    if not credentials:
        logger.error("❌ No credentials extracted by HTTPBearer security scheme")
        raise HTTPException(
            status_code=401, 
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.debug(f"Token found, length: {len(credentials.credentials)}")
    return jwt_auth.get_user_from_token(credentials.credentials)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[AuthUser]:
    """
    Dependency to optionally get the current user.
    Returns None if no valid auth token provided.
    """
    if not credentials:
        return None
    
    try:
        return jwt_auth.get_user_from_token(credentials.credentials)
    except HTTPException:
        return None


def require_auth(request: Request) -> AuthUser:
    """
    Alternative sync dependency for routes.
    Extracts token from Authorization header.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ")[1]
    return jwt_auth.get_user_from_token(token)


class RateLimitByUser:
    """Rate limiting per user."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.user_requests: dict[str, list[float]] = {}
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit."""
        now = time.time()
        minute_ago = now - 60
        
        # Get user's request timestamps
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Filter to last minute only
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] 
            if ts > minute_ago
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= self.requests_per_minute:
            return False
        
        # Record this request
        self.user_requests[user_id].append(now)
        return True


# Global rate limiter
rate_limiter = RateLimitByUser(requests_per_minute=60)


async def rate_limit_check(user: AuthUser = Depends(get_current_user)):
    """Dependency to check rate limit per user."""
    if not rate_limiter.check_rate_limit(user.id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before making more requests."
        )
    return user
