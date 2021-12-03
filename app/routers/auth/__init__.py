from fastapi import APIRouter, Request, Depends
from sqlalchemy.sql.sqltypes import JSON
from ...database import *
from ...models import *
from .utilities import *
from ...schemas.auth_schema import *
from ...decorators import *
from pydantic import ValidationError

router = APIRouter()

from .forgot_password import *


@router.get("/create_clients")
def create_clients(request: Request, db : Session = Depends(get_db) ):
	response = create_authorization_clients(db) 
	return response    


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	try:
		data = LoginDataSchema(**data)
		client = db.query(AuthorizationClient).filter_by(client_id=data.client_id).first()
		if client:
			user_obj = db.query(User).filter_by(email=data.email).first()
			if user_obj and user_obj.check_password(data.password) and user_obj.login_permit:
				token_family_obj = TokenFamily(user_id=user_obj.id)
				db.add(token_family_obj)
				db.commit()
				return { "result": { "code": get_token_code(client, token_family_obj.id, user_obj, db) } }
		return JSONResponse(
			content={ "error_msg": "Invalid Credentials" }, 
			status_code=401
		)
	except ValidationError:
		return JSONResponse(
			content={ 'error_msg' : "Invalid Data" }, 
			status_code=400
		)


@router.post("/tokens/get")
async def get_login_token(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	try:
		data = GetLoginTokenSchema(**data)
		payload = verify_token_code(data.code, db)
		if payload:
			token_code_obj = db.query(LoginToken).filter_by(token=data.code).first()
		if payload and token_code_obj.is_valid:
			client_secret = db.query(AuthorizationClient).filter_by(client_id = payload["client_id"]).first().client_secret
			if client_secret == data.client_secret:
				user_obj = db.query(User).filter_by(id = payload['user_id']).first()
				login_tokens = get_login_tokens(user_obj, token_code_obj.token_family_id, db)
				
				db.delete(token_code_obj)
				db.commit()

				return { "result" :
							{
								"access_token" : login_tokens['access_token'], 
								"refresh_token" : login_tokens['refresh_token'] 
							}
					}
			else:
				return JSONResponse(
					content={ "error_msg": "Invalid Client Secret" }, 
					status_code=400
				)
		else:
			return JSONResponse(
				content={ "error_msg": "Invalid/Expired Code. Please login again" } , 
				status_code=400
			)
	except ValidationError:
		return JSONResponse(
			content={ "error_msg": "Invalid Data" }, 
			status_code=400
		)


@router.post("/tokens/refresh")
async def refresh_login_tokens(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	if "refresh_token" in data:
		return verify_refresh_token(data["refresh_token"], db)
	else:
		return JSONResponse(
			content={ 'error_msg' : "Invalid Data" }, 
		 	status_code=400
		)


@router.post("/logout")
async def logout_user(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	try:
		data = LogoutDataSchema(**data)
		refresh_token_obj = db.query(LoginToken).filter(LoginToken.token_type == "refresh", LoginToken.token == data.refresh_token).first()
		if refresh_token_obj and refresh_token_obj.is_valid:
			token_family_obj = db.query(TokenFamily).get(refresh_token_obj.token_family_id) 
			db.delete(token_family_obj)
			db.commit()	
			return { "status": "success" }
		else:
			return JSONResponse(
				content={ 'error_msg' : "Invalid Tokens" }, 
				status_code=400
			)
	except ValidationError:
		return JSONResponse(
			content={ 'error_msg' : "Invalid Data" }, 
			status_code=400
		)
