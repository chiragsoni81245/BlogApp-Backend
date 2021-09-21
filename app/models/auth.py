from logging import error
from fastapi.param_functions import Depends
from sqlalchemy import Boolean, Column, Integer, String, DateTime, text, ForeignKey, Date, Text
from sqlalchemy.sql.functions import user
from sqlalchemy.sql.sqltypes import BigInteger
from app.database import Base, SessionLocal, engine, get_db
from passlib.context import CryptContext
from sqlalchemy.orm import Session, relationship
import jwt
from time import time
from datetime import datetime
from ..models import *
from ..schemas.auth_schema import *
from ..schemas import Result
from ..utilities import get_error_messages
from pydantic import ValidationError
import base64, os
from pyotp import TOTP


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthorizationClient(Base):
	__tablename__ = "authorization_client"

	id = Column( Integer, primary_key = True, index = True )
	client_name =  Column( String, unique = True )
	client_id = Column( String, unique = True )
	client_secret = Column( Text, unique = True )


	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )
	

class User(Base):
	__tablename__ = "user"

	def __init__(self,**kwargs):
		super(User, self).__init__(**kwargs)		
		if self.otp_secret is None:
			self.otp_secret = base64.b32encode(os.urandom(10)).decode("utf-8")

	otp_secret = Column(String)
	id = Column( Integer, primary_key = True, index = True )
	email = Column( String, unique = True )
	password_hash = Column( String )
	login_permit = Column( Boolean, default=True, nullable=False )
	status = Column( Boolean, default=True, nullable=False )
	email_verified = Column( Boolean, default=False )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )

	@staticmethod
	def create(data, db) -> Result:
		try:
			data = UserCreateSchema(**data)
			user_obj = User(email=data.email)
			db.add(user_obj)
			if data.password:
				user_obj.set_password(data.password, db)
			db.commit()
			db.refresh(user_obj)
			return Result(status=True, data=user_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	@staticmethod
	def update(data, db) -> Result:
		try:
			data = UserUpdateSchema(**data)
			user_obj = db.query(User).get(data.user_id)
			user_detail_obj = db.query(UserDetail).filter_by(user_id=data.user_id).first()
			if not user_detail_obj:
				user_detail_obj = UserDetail(user_id=user_obj.id)
				db.add(user_detail_obj)
				db.commit()
			user_address_obj = db.query(Address).filter_by(user_id=data.user_id).first()
			if not user_address_obj:
				user_address_obj = Address(user_id=user_obj.id)
				db.add(user_address_obj)
				db.commit()
			if data.email and data.email!=user_obj.email:
				user_obj.email = data.email
				user_obj.email_verified = False
			if data.password:
				user_obj.set_password(data.password, db)
				#Revoke all the tokens of this User
				token_families = db.query(TokenFamily).filter_by(user_id=user_obj.id).all()
				for token_family in token_families:
					db.delete(token_family)

			check_list = [ 
				(data, "first_name", user_detail_obj, "first_name"),
				(data, "last_name", user_detail_obj, "last_name"),
				(data, "contact_no", user_detail_obj, "contact_no"),
				(data, "dob", user_detail_obj, "date_of_birth"),
				(data, "address_line_1", user_address_obj, "address_line_1"),
				(data, "address_line_2", user_address_obj, "address_line_2"),
				(data, "city", user_address_obj, "city"),
				(data, "state", user_address_obj, "state"),
				(data, "pincode", user_address_obj, "pincode"),
			]
			for arg in check_list:
				if arg[0].__getattribute__(arg[1]) and arg[0].__getattribute__(arg[1])!=arg[2].__getattribute__(arg[3]):
					arg[2].__setattr__(arg[3], arg[0].__getattribute__(arg[1]))
			db.commit()
			return Result(status=True, data=user_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	def grant_role(self, role, db) -> Result:
		role_obj = db.query(Role).filter_by(name=role).first()
		if role_obj:
			user_role = db.query(UserRole).filter_by(user_id=self.id, role_id=role_obj.id).first()
			if user_role:
				return Result(status=False, error_msg=["User already have this role"])
			else:
				user_role = UserRole(user_id=self.id, role_id=role_obj.id)
				db.add(user_role)
				db.commit()
				return Result(status=True)
		return Result(status=False, error_msg=["Invalid Role"])

	def revoke_role(self, role, db) -> Result:
		role_obj = db.query(Role).filter_by(name=role).first()
		if role_obj:
			user_role = db.query(UserRole).filter_by(user_id=self.id, role_id=role_obj.id).first()
			if user_role:
				db.delete(user_role)
				db.commit()
				return Result(status=True)
			else:
				return Result(status=False, error_msg=["User don't have this role"])
		return Result(status=False, error_msg=["Invalid Role"])

	def get_roles(self, db) -> set:
		roles = db.query(Role.name).join(
											UserRole, UserRole.role_id==Role.id
										).filter(
											UserRole.user_id==self.id
										).all()

		return { i[0] for i in roles }

	def set_password(self, plain_text_password, db: Session):
		self.password_hash = pwd_context.hash(plain_text_password)
		db.commit()
		db.refresh(self)

	def check_password(self, plain_text_password):
		return pwd_context.verify(plain_text_password, self.password_hash)

	def get_otp(self):
		return TOTP(self.otp_secret,interval=1200).now()
	
	def verify_otp(self,otp):
		return TOTP(self.otp_secret,interval=1200).verify(otp)


class UserDetail(Base):
	__tablename__ = "user_detail"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id"), unique=True )
	first_name = Column( String )
	last_name = Column( String )
	contact_no = Column( BigInteger, unique=True )
	date_of_birth = Column( Date )
	image = Column( String )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class Address(Base):
	__tablename__ = "address"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id"), unique=True )
	address_line_1 = Column( String )
	address_line_2 = Column( String )
	city = Column( String, index=True )
	state = Column( String, index=True )
	pincode = Column( Integer, index=True )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class TokenFamily(Base):
	__tablename__ = "token_family"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id") )

	refresh_tokens = relationship("LoginToken", cascade="all,delete", backref="token_family")

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class LoginToken(Base):
	__tablename__ = "login_token"

	id = Column( Integer, primary_key = True, index = True )
	token_type = Column( String )
	token_family_id = Column( Integer, ForeignKey("token_family.id") )
	token = Column( String , unique = True, index = True)
	is_valid = Column( Boolean, default = True )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )

	def __repr__(self) -> str:
		return "Token Type: {}, Token: {}, Family: {}".format(self.token_type, self.token, self.token_family_id)


class Role(Base):
	__tablename__ = "role"

	id = Column( Integer, primary_key = True, index = True )
	name = Column( String, nullable=False )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )

	def __repr__(self) -> str:
		return "{} Role".format(self.name)


class UserRole(Base):
	__tablename__ = "user_role"

	id = Column( Integer, primary_key = True, index = True )
	role_id = Column( Integer, ForeignKey("role.id") )
	user_id = Column( Integer, ForeignKey("user.id") )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )

