from . import router
from ...decorators import is_authorized
from fastapi import Request, Depends
from ...models import UserDetail, Session, get_db
from fastapi.responses import JSONResponse

@router.post("/validate/contact_no")
@is_authorized
async def validate_user_contact_no(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	if "contact_no" in data:
		user_detail_obj = db.query(UserDetail).filter_by(contact_no=data["contact_no"]).first()
		if not user_detail_obj or request.current_user.id==user_detail_obj.user_id:
			return { "result": True }
		return { "result": False }
	else:
		return JSONResponse(
			content={ "error_msg": "Contact Number is required" },
			status_code=400
		) 
