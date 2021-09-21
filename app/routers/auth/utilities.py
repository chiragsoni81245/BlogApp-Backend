import secrets

from starlette.responses import JSONResponse
from ...config import app_config
from ... import models
from sqlalchemy.orm import Session
import jwt
from time import time


def create_authorization_clients(db):
	for client in app_config.CLIENTS:
		client_id = secrets.token_hex(32)  
		client_secret = secrets.token_hex(256) 
		client_obj = models.AuthorizationClient(
			client_name = client,
			client_id =  client_id,
			client_secret = client_secret
		)
		db.add(client_obj)
		db.commit()
		db.refresh(client_obj)
	return {"status":200 }


def get_token_code(client, token_family_id, user_obj, db):
	token_code = jwt.encode(
		{
			"client_id" : client.client_id,
			"user_id": user_obj.id, 
			'exp': time() + app_config.TOKEN_CODE_EXPIRY_TIME
		}, 
		app_config.TOKEN_CODE_SECRET_KEY, 
		algorithm="HS256"
	)

	# Store Token Code it in Database
	token_obj = models.LoginToken( token_type="code", token=token_code, token_family_id=token_family_id )
	db.add(token_obj)
	db.commit()

	return token_code


def get_login_tokens(user_obj, token_family_id, db: Session) -> dict:
	access_token = jwt.encode({"user_id": user_obj.id, "token_family": token_family_id, 'exp': time() + app_config.ACCESS_TOKEN_EXPIRY_TIME }, app_config.ACCESS_TOKEN_SECRET_KEY, algorithm="HS256")
	refresh_token = jwt.encode({"user_id": user_obj.id, "token_family": token_family_id, 'exp': time() + app_config.REFRESH_TOKEN_EXPIRY_TIME }, app_config.REFRESH_TOKEN_SECRET_KEY, algorithm="HS256")

	# Store refresh_tokens it in Database
	refresh_token_obj = models.LoginToken( token_type="refresh", token=refresh_token, token_family_id=token_family_id )
	db.add(refresh_token_obj)
	db.commit()

	return { "access_token" : access_token, "refresh_token" : refresh_token } 


def verify_token_code(token_code, db: Session):
	token_obj = db.query(models.LoginToken).filter_by(token_type="code", token=token_code).first()
	if token_obj:
		try: 
			payload = jwt.decode(token_obj.token, app_config.TOKEN_CODE_SECRET_KEY, algorithms=["HS256"])
			return payload
		except (jwt.ExpiredSignatureError, jwt.DecodeError):
			db.delete(token_obj)
			db.commit()
	return False


def verify_access_token(access_token, db : Session):
	try:
		payload = jwt.decode(access_token, app_config.ACCESS_TOKEN_SECRET_KEY, algorithms=["HS256"])
		return payload
	except (jwt.ExpiredSignatureError, jwt.DecodeError):
		return False


def verify_refresh_token(refresh_token, db : Session):
	token_obj = db.query(models.LoginToken).filter(models.LoginToken.token_type == "refresh", models.LoginToken.token == refresh_token).first()
	try:
		if token_obj:
			payload = jwt.decode(token_obj.token, app_config.REFRESH_TOKEN_SECRET_KEY, algorithms=["HS256"])
		if token_obj and payload:
			if token_obj.is_valid:
				user_obj = db.query(models.User).filter( models.User.id == payload["user_id"]).first()
				if user_obj:
					response = get_login_tokens(user_obj, payload["token_family"], db)

					token_obj.is_valid = False
					db.commit()
					return { 'result': { 'access_token' : response['access_token'], 'refresh_token' : response['refresh_token'] } }
			else:
				# Reduse Token
				token_family_obj = db.query(models.TokenFamily).get(payload["token_family"])
				db.delete(token_family_obj)
				db.commit()

				return JSONResponse(
					content={ "error_msg": "Token Reuse Detected, Please login again" }, 
					status_code=401
				)
	except (jwt.ExpiredSignatureError, jwt.DecodeError):
		db.delete(token_obj)
		db.commit()
	return JSONResponse(
		content={ "error_msg": "Invalid/Expired Token" }, 
		status_code=401
	)


def get_reset_password_token(email):
	token = jwt.encode({"email": email, 'exp': time() + app_config.REST_PASSWORD_TOKEN_EXPIRY_TIME }, app_config.REST_PASSWORD_TOKEN_SECRET_KEY, algorithm="HS256")
	return token


def verify_reset_password_token(token):
	try: 
		payload = jwt.decode(token, app_config.REST_PASSWORD_TOKEN_SECRET_KEY, algorithms=["HS256"])
		return payload
	except (jwt.ExpiredSignatureError, jwt.DecodeError):
		return False