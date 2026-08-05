"""Firebase-authenticated current-user endpoint."""

from fastapi import APIRouter, Depends

from backend.app.auth import CurrentUser, viewer_or_operator


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _serialize_user(user: CurrentUser) -> dict:
    return {
        "objectId": user.object_id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "roles": sorted(user.roles),
        "isOperator": "Operator" in user.roles,
    }


@router.get("/me")
def get_authenticated_user(
    user: CurrentUser = Depends(viewer_or_operator),
) -> dict:
    """Return the verified Firebase identity and trusted custom-claim role."""
    return _serialize_user(user)
