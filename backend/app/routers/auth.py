from fastapi import APIRouter, Depends

from backend.app.auth import CurrentUser, viewer_or_operator


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.get("/me")
def get_authenticated_user(
    user: CurrentUser = Depends(viewer_or_operator),
) -> dict:
    return {
        "objectId": user.object_id,
        "name": user.name,
        "username": user.username,
        "roles": sorted(user.roles),
        "isOperator": "Operator" in user.roles,
    }
