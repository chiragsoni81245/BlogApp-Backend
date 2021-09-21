from fastapi import APIRouter


router = APIRouter()


from .routes import *
from .forgot_password import *