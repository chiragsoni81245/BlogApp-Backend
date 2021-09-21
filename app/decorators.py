from app.models import *
from functools import wraps
from fastapi.responses import JSONResponse, RedirectResponse
from app.routers.auth.utilities import *


def is_authorized(func): 
	@wraps(func) 
	async def validate_access_token(*args, **kwargs): 
		request = kwargs["request"] 
		db = kwargs["db"]
		if "Authorization" in request.headers :
			access_token = request.headers['Authorization']
			payload = verify_access_token(access_token, db)
			if payload:
				user_obj = db.query(User).get(payload['user_id'])
				setattr(request, "current_user", user_obj) 
				if request.method == "GET":
					return func(*args, **kwargs)
				else:
					return await func(*args, **kwargs)
			else:
				return JSONResponse(
					content={ "error_msg": "Invalid/Expired Token" }, 
					status_code=401
				)
		else:
			return JSONResponse(
				content={ "error_msg": "Token not found" }, 
				status_code=401
			)
	return validate_access_token 


def user_have_roles(roles: list, any: bool = False): 
	def is_user_have_role(func): 
		@wraps(func) 
		async def validate_roles(*args, **kwargs): 
			request = kwargs["request"] 
			db = kwargs["db"]
			if "Authorization" in request.headers :
				access_token = request.headers['Authorization']
				payload = verify_access_token(access_token, db)
				if payload:
					user_obj = db.query(User).get(payload['user_id'])
					setattr(request, "current_user", user_obj) 
					user_roles = user_obj.get_roles(db)
					if any:
						is_permitted = False
						for role in roles:
							if role in user_roles:
								is_permitted = True
								break
					else:
						is_permitted = True
						for role in roles:
							if role not in user_roles:
								is_permitted = False
								break
					if is_permitted:
						if request.method =="GET":
							return func(*args, **kwargs)
						else:
							return await func(*args, **kwargs)
					else:
						return JSONResponse(
							content={ "error_msg": "You don't have permission for this" },
							status_code=403
						)
				else:
					return JSONResponse(
						content={ "error_msg": "Invalid/Expired Token" }, 
						status_code=401
					)
			else:
				return JSONResponse(
					content={ "error_msg": "Token not found" }, 
					status_code=401
				)
		return validate_roles 
	return is_user_have_role
