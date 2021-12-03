from os import path
from fastapi import APIRouter, Request, Depends
from sqlalchemy.sql.sqltypes import JSON
from ...database import *
from ...models import *
from ...schemas.auth_schema import *
from ...decorators import *
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
import time

router = APIRouter()

from .validators import *


@router.get("/get_details")
@is_authorized
def get_user_details(request: Request, db: Session = Depends(get_db)):
	user_details = db.query(
		User.id,
		User.email,
		UserDetail.first_name,
		UserDetail.last_name,
		UserDetail.contact_no,
		UserDetail.date_of_birth.label('dob'),
		UserDetail.image
	).join(UserDetail, UserDetail.user_id==User.id, isouter=True).filter( User.id==request.current_user.id ).first()

	user_details = jsonable_encoder(user_details)
	user_details["image"] = request.url_for('static', path="user_images/{}".format(user_details["image"]))
	user_details["followers_count"] = db.query(Followers).filter_by(following_id=user_details["id"]).count()
	user_details["following_count"] = db.query(Followers).filter_by(follower_id=user_details["id"]).count()
		
	return { "result": user_details }


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
			status_code=400
		)


@router.put("/")
@is_authorized
async def update_user(request: Request, db: Session = Depends(get_db)):
	data = await request.json()
	result = request.current_user.update(data, db)
	if result.status:
		return JSONResponse(
			content={"status": "success"},
			status_code=200
		)
	else:
		return JSONResponse(
			content={ "error_msg": result.error_msg }, 
			status_code=400
		)


@router.get("/follow/{user_id}")
@is_authorized
def follow_user(request: Request, user_id:int = None, db: Session = Depends(get_db)):
	following_user_obj = db.query(User).get(user_id)
	if not following_user_obj:
		return JSONResponse(
			content={"error_msg": "User with id {} not found".format(user_id)},
			status_code=404
		)
	result = request.current_user.follow(user_id, db)
	if result.status:
		return JSONResponse(
			content={"status": "success"},
			status_code=200
		)
	else:
		return JSONResponse(
			content={ "error_msg": result.error_msg }, 
			status_code=400
		)


@router.get("/unfollow/{user_id}")
@is_authorized
def unfollow_user(request: Request, user_id:int = None, db: Session = Depends(get_db)):
	following_user_obj = db.query(User).get(user_id)
	if not following_user_obj:
		return JSONResponse(
			content={"error_msg": "User with id {} not found".format(user_id)},
			status_code=404
		)
	result = request.current_user.unfollow(user_id, db)
	if result.status:
		return JSONResponse(
			content={"status": "success"},
			status_code=200
		)
	else:
		return JSONResponse(
			content={ "error_msg": result.error_msg }, 
			status_code=400
		)


@router.get("/followers")
@is_authorized
def get_followers(request: Request, page:int =1, page_size:int = 5, db: Session = Depends(get_db)):
	followers = db.query(Followers.follower_id).filter_by(
		following_id=request.current_user.id
	)
	total_followers = followers.count()
	followers = jsonable_encoder(followers.offset((page-1)*page_size).limit(page_size))
	final_followers = []
	for follower in followers:
		follower_obj = db.query(
			User.id,
			User.email,
			UserDetail.first_name,
			UserDetail.last_name,
			UserDetail.date_of_birth.label('dob'),
			UserDetail.image
		).join(UserDetail, UserDetail.user_id==User.id, isouter=True).filter( 
			User.id==follower[0] 
		).first()

		follower_obj = jsonable_encoder(follower_obj)
		follower_obj["image"] = request.url_for('static', path="user_images/{}".format(follower_obj["image"]))

		final_followers.append(follower_obj)

	return {
		"matadata": {
			"page": page,
			"page_size": page_size
		},
		"total_result": total_followers,
		"result": final_followers
	}


@router.get("/following")
@is_authorized
def get_following(request: Request, page:int =1, page_size:int = 5, db: Session = Depends(get_db)):
	followers = db.query(Followers.following_id).filter_by(
		follower_id=request.current_user.id
	)
	total_following = followers.count()
	following = jsonable_encoder(followers.offset((page-1)*page_size).limit(page_size))
	final_following = []
	for follower in following:
		follower_obj = db.query(
			User.id,
			User.email,
			UserDetail.first_name,
			UserDetail.last_name,
			UserDetail.date_of_birth.label('dob'),
			UserDetail.image
		).join(UserDetail, UserDetail.user_id==User.id, isouter=True).filter( 
			User.id==follower[0] 
		).first()

		follower_obj = jsonable_encoder(follower_obj)
		follower_obj["image"] = request.url_for('static', path="user_images/{}".format(follower_obj["image"]))

		final_following.append(follower_obj)

	return {
		"matadata": {
			"page": page,
			"page_size": page_size
		},
		"total_result": total_following,
		"result": final_following
	}