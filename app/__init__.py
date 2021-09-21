from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key='-R5Sy4SY1nRpLoHOHCDDVobz')

from .routers.auth import router as auth_router
from .routers.user import router as user_router

app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/user")