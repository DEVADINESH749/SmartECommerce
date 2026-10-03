from datetime import datetime, timedelta, timezone

from jose import jwt as jose_jwt, JWTError


SECRET_KEY = "smart-ecommerce-secret-key-change-later"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jose_jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_access_token(token: str):
    try:
        payload = jose_jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            return None

        return payload

    except JWTError:
        return None
    
    
    
    
from jwt import PyJWKClient
import jwt as pyjwt

AUTH0_DOMAIN = "dev-ay3oucvrj1zve1ph.us.auth0.com"
AUTH0_AUDIENCE = "https://smart-ecommerce-api"
AUTH0_CLIENT_ID = "SGEhMn053XGgGwCD9Gt85XIL7VQR8o4R"
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

jwks_client = PyJWKClient(
    f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
)

def verify_auth0_token(token: str):
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER
        )

        return payload

    except Exception:
        return None


def verify_auth0_id_token(token: str):
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUTH0_CLIENT_ID,
            issuer=AUTH0_ISSUER
        )
    except Exception:
        return None