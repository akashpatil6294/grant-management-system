from uuid import UUID
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import settings
from .database import connection

bearer = HTTPBearer(auto_error=False)


def current_staff(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, 'Sign in to continue.', headers={'WWW-Authenticate': 'Bearer'})
    cfg = settings()
    if not cfg.supabase_url or not cfg.supabase_publishable_key:
        raise HTTPException(503, 'Authentication is not configured.')
    try:
        response = httpx.get(
            f'{cfg.supabase_url.rstrip("/")}/auth/v1/user',
            headers={'apikey': cfg.supabase_publishable_key, 'Authorization': f'Bearer {credentials.credentials}'},
            timeout=10,
        )
    except httpx.RequestError:
        raise HTTPException(503, 'Authentication service is unavailable.')
    if response.status_code in (401, 403):
        raise HTTPException(401, 'Your session is invalid or expired.')
    if response.status_code != 200:
        raise HTTPException(503, 'Authentication service is unavailable.')
    try:
        user_id = UUID(response.json()['id'])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Invalid authentication response.')
    with connection() as conn:
        staff = conn.execute('SELECT * FROM staff_members WHERE user_id=%s AND is_active', (user_id,)).fetchone()
    if not staff:
        raise HTTPException(403, 'An administrator must activate your staff membership.')
    return staff
