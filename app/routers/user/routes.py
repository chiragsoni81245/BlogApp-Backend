from fastapi import Request, Depends
from sqlalchemy.sql.sqltypes import JSON
from ...database import *
from ...models import *
from . import router
from ...schemas.auth_schema import *
from ...decorators import *
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
import time

@router.get("/get_details")
@is_authorized
def get_user_details(request: Request, db: Session = Depends(get_db)):
	user_details = db.query(
		User.email,
		UserDetail.first_name,
		UserDetail.last_name,
		UserDetail.contact_no,
		UserDetail.date_of_birth.label('dob'),
		Address.address_line_1,
		Address.address_line_2,
		Address.city,
		Address.state,
		Address.pincode
	).join(UserDetail, UserDetail.user_id==User.id, isouter=True).join(Address, Address.user_id==User.id, isouter=True).filter( User.id==request.current_user.id ).first()

	return { "result": jsonable_encoder(user_details) }


@router.post("/")
async def create_user(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	result = User.create(data, db)
	if result.status:
		return JSONResponse(
			content={"status": "success"},
			status_code=201
		)
	else:
		return JSONResponse(
			content={ "error_msg": result.error_msg }, 
			status_code=500
		)


@router.put("/")
@is_authorized
async def update_user(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	data["user_id"] = request.current_user.id
	
	result = User.update(data, db)
	if result.status:
		return JSONResponse(
			content={"status": "success"},
			status_code=200
		)
	else:
		return JSONResponse(
			content={ "error_msg": result.error_msg }, 
			status_code=500
		)


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
			status_code=500
		) 
