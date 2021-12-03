from fastapi import Request, Depends
from sqlalchemy.sql.sqltypes import JSON
from ...database import *
from ...models import *
from . import router
from .utilities import *
from ...schemas.auth_schema import *
from ...decorators import *
from pydantic import ValidationError
from ...utilities import get_error_messages
from ...email_service import send_password_reset_email


@router.post("/forget-password")
async def forget_passowrd(request: Request, db : Session = Depends(get_db) ):
	data = await request.json()
	try:
		data = ForgetPasswordSchema(**data)
		user_obj = db.query(User).filter_by(email=data.email).first()
		send_password_reset_email( user_obj ) # Send Email
		return {"message": "An OTP has been sent to your email. Please check your inbox."}
	except ValidationError as error:
		return JSONResponse(
			content={ "error_msg": get_error_messages(error) },
			status_code=400
		)


@router.post("/verify-otp")
async def user_verify_otp(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	try:
		data = VerifyOTPSchema(**data)
		user_obj = db.query(User).filter_by(email=data.email).first()
		return {"result": {"reset_password_token": get_reset_password_token(user_obj.email)}}
	except ValidationError as error:
		return JSONResponse(
			content={ "error_msg": get_error_messages(error) },
			status_code=400
		)


@router.post("/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	try:
		data = ResetPasswordSchema(**data)
		payload = verify_reset_password_token(data.reset_password_token)
		if payload:
			user_obj = db.query(User).filter_by(email=payload["email"]).first()
			user_obj.set_password(data.password, db)
			token_familys = db.query(TokenFamily).filter_by(user_id=user_obj.id).all()
			for token_family in token_familys:
				db.delete(token_family)
			
			db.commit()
			return { "status": "success" }
		return JSONResponse(
			content={ "error_msg": ["Invalid/Expired Reset Password Token"] },
			status_code=400
		)
	except ValidationError as error:
		return JSONResponse(
			content={ "error_msg": get_error_messages(error) },
			status_code=400
		)

