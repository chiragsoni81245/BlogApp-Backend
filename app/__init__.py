from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from blog_recommendation_system import PopularityBaseRecommander
from blog_recommendation_system import ContentBaseRecommender
app = FastAPI()
popularity_base_recommander = PopularityBaseRecommander()
content_base_recommander = ContentBaseRecommender()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key='-R5Sy4SY1nRpLoHOHCDDVobz')

from .routers.auth import router as auth_router
from .routers.user import router as user_router
from .routers.blog import router as blog_router

app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/user")
app.include_router(blog_router, prefix="/api/blogs")