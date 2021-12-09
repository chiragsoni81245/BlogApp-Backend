from fastapi.datastructures import UploadFile
from pydantic import BaseModel
from typing import Optional
from pydantic import validator
from sqlalchemy.sql import base
from sqlalchemy.sql.sqltypes import Enum
from .. import models
from ..database import SessionLocal
import re
from datetime import date
from ..routers.auth.utilities import verify_reset_password_token


class LoginDataSchema(BaseModel):

	email: str
	client_id: str
	password: str


class GetLoginTokenSchema(BaseModel):

	code: str
	client_secret: str


class LogoutDataSchema(BaseModel):

	refresh_token: str


class UserCreateSchema(BaseModel):

	email: str
	password: Optional[str] = None

	@validator('email')
	def email_shoud_be_unique(cls, value):
		if not re.fullmatch("[\w_]+@\w+\.(com|in|org)", value):
			raise ValueError('Invalid email format')
		db = SessionLocal()
		user_obj = db.query(models.User.id).filter_by(email=value).first()
		if user_obj:
			raise ValueError('This email is already exists')
		return value

	@validator('password')
	def validate_password(cls, value):
		if value and not re.fullmatch("^(?=.*[A-Z])(?=.*[!@#$&*])(?=.*[0-9])(?=.*[a-z].).{8,}$", value):
			raise ValueError('Password must have 1 uppercase letter, 1 lowercase letter, 1 digit, 1 special character, and length must be grater then 8')
		return value


class UserUpdateSchema(BaseModel):

	user_id: int
	email: Optional[str]
	password: Optional[str]
	first_name: Optional[str]
	last_name: Optional[str]
	contact_no: Optional[str]
	dob: Optional[date]
	image : Optional[str] = None

	@validator('user_id')
	def valid_user_id(cls, value):
		db = SessionLocal()
		user_obj = db.query(models.User).get(value)
		if not user_obj:
			raise ValueError('Invalid user')
		return value

	@validator('email')
	def email_shoud_be_unique(cls, value, values):
		if not re.fullmatch("[\w_]+@\w+\.(com|in|org)", value['email']):
			raise ValueError('Invalid email format')
		db = SessionLocal()
		email_user = db.query(models.User).filter_by(email=value["email"]).first()
		if email_user:
			if email_user.id!=values["user_id"]:
				raise ValueError('This email is already exists')
		return value

	@validator('password')
	def validate_password(cls, value, values):
		db = SessionLocal()
		user_obj = db.query(models.User).get(values["user_id"])
		if user_obj.check_password(value):
			raise ValueError('Password should not be same as current password')
		if value and not re.fullmatch("^(?=.*[A-Z])(?=.*[!@#$&*])(?=.*[0-9])(?=.*[a-z].).{8,}$", value):
			raise ValueError('Password must have 1 uppercase letter, 1 lowercase letter, 1 digit, 1 special character, and length must be grater then 8')
		return value

	@validator('contact_no')
	def validate_contact_no(cls, value, values):
		if not re.fullmatch("\d{10}", value):
			raise ValueError('Invalid contact number format')
		db = SessionLocal()
		user_detail_obj = db.query(models.UserDetail).filter_by(contact_no=value).first()
		if user_detail_obj:
			if user_detail_obj.user_id!=values["user_id"]:
				raise ValueError('This contact number is already exists')
		return value

class ForgetPasswordSchema(BaseModel):

	email: str
	client_id : str

	@validator('email')
	def email_should_exists(cls, value):
		if not re.fullmatch("[\w_]+@\w+\.(com|in|org)", value):
			raise ValueError('Invalid email format')
		db = SessionLocal()
		user_obj = db.query(models.User.id).filter_by(email=value).first()
		if not user_obj:
			raise ValueError('This email does not exists')
		return value

	@validator('client_id')
	def validate_client_id(cls, value):
		db = SessionLocal()
		client_obj = db.query(models.AuthorizationClient).filter_by(client_id=value).first()
		if not client_obj:
			raise ValueError('Invalid Client ID')
		return value


class VerifyOTPSchema(BaseModel):

	email: str
	otp: int

	@validator('email')
	def email_should_exists(cls, value):
		if not re.fullmatch("[\w_]+@\w+\.(com|in|org)", value):
			raise ValueError('Invalid email format')
		db = SessionLocal()
		user_obj = db.query(models.User.id).filter_by(email=value).first()
		if not user_obj:
			raise ValueError('This email does not exists')
		return value

	@validator('otp')
	def validate_otp(cls, value, values):
		db = SessionLocal()
		user_obj = db.query(models.User).filter_by(email=values["email"]).first()
		if not user_obj.verify_otp(value):
			raise ValueError('Invalid OTP')
		return value


class ResetPasswordSchema(BaseModel):

	reset_password_token: str
	password: str

	@validator('password')
	def validate_password(cls, value):
		if value and not re.fullmatch("^(?=.*[A-Z])(?=.*[!@#$&*])(?=.*[0-9])(?=.*[a-z].).{8,}$", value):
			raise ValueError('Password must have 1 uppercase letter, 1 lowercase letter, 1 digit, 1 special character, and length must be grater then 8')
		return value


