from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.merchant import Merchant
from app.schemas import MerchantLogin, MerchantRegister, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: MerchantRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Merchant).where(Merchant.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    merchant = Merchant(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
    )
    db.add(merchant)
    await db.flush()

    token = create_access_token({"sub": str(merchant.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: MerchantLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Merchant).where(Merchant.email == data.email))
    merchant = result.scalar_one_or_none()

    if not merchant or not verify_password(data.password, merchant.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(merchant.id)})
    return TokenResponse(access_token=token)


