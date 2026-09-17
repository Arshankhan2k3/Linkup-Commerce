from fastapi import APIRouter

router = APIRouter()

@router.get("/stores")
def get_stores():
    return {"message": "Stores"}