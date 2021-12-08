from logging import error
from fastapi.param_functions import Depends
from sqlalchemy import Boolean, Column, Integer, String, DateTime, sql, text, ForeignKey, Date, Text
import sqlalchemy
from sqlalchemy.sql.functions import user
from sqlalchemy.sql.schema import UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger
from app.config import app_config
from app.database import Base, SessionLocal, engine, get_db
from passlib.context import CryptContext
from sqlalchemy.orm import Session, relationship
import jwt
from time import time
from datetime import datetime
from ..schemas.auth_schema import *
from ..schemas.blog_schema import *
from .blog import *
from ..schemas import Result
from ..utilities import countWords, get_error_messages
from pydantic import ValidationError
import base64, os
from pyotp import TOTP
import aiofiles
from elasticsearch_client import es_submit_blog_data, es_update_blog_data, es_delete_blog_data
import math

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

	blogs = relationship( "Blog", back_populates = "author", cascade="all,delete" )

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

	def update(self, data, db) -> Result:
		try:
			data = UserUpdateSchema(**data, user_id=self.id)
			user_obj = db.query(User).get(data.user_id)
			user_detail_obj = db.query(UserDetail).filter_by(user_id=data.user_id).first()
			if not user_detail_obj:
				user_detail_obj = UserDetail(user_id=user_obj.id)
				db.add(user_detail_obj)
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
			if data.image:
				if not os.path.isdir(os.getcwd()+"/user_images"):
					os.mkdir(os.getcwd()+"/user_images")
				with open(os.getcwd()+"/user_images/{}.jpg".format(user_obj.id), "w") as f:
					f.write(data.image.read())
				user_detail_obj.image = "{}.jpg".format(user_obj.id)

			check_list = [ 
				(data, "first_name", user_detail_obj, "first_name"),
				(data, "last_name", user_detail_obj, "last_name"),
				(data, "contact_no", user_detail_obj, "contact_no"),
				(data, "dob", user_detail_obj, "date_of_birth"),
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

	def follow(self, user_id, db):
		try:
			follower_obj = Followers(follower_id=self.id, following_id=user_id)
			db.add(follower_obj)
			db.commit()
			return Result(status=True)
		except sqlalchemy.exc.IntegrityError:
			return Result(status=False, error_msg="You already follow this user")

	def unfollow(self, user_id, db):
		follower_obj = db.query(Followers).filter_by(follower_id=self.id, following_id=user_id).first()
		if follower_obj:
			db.delete(follower_obj)
			db.commit()
			return Result(status=True)
		else:
			return Result(status=False, error_msg="You don't follow this user")

	async def create_blog(self, data:dict, db):
		data.update({"user_id": self.id})
		try:
			data = BlogCreateSchema(**data)
			read_time = math.ceil(countWords(data.content)/app_config.AVG_WPM)
			blog_obj = Blog(title=data.title, content=data.content, author_id=data.user_id, read_time=read_time)
			db.add(blog_obj)
			db.flush()
			categories = []
			for category_id in data.categories:
				category_name = db.query(BlogCategory).get(category_id).name
				categories.append({
					"id": category_id,
					"name": category_name
				})
				blog_map_category_obj = BlogMapCategory(blog_id=blog_obj.id, category_id=category_id)
				db.add(blog_map_category_obj)
			db.flush()
			
			# Submit Data to Elastic Search
			data = {
				"id": blog_obj.id,
				"title": blog_obj.title,
				"content": blog_obj.content,
				"read_time": blog_obj.read_time,
				"categories": categories,
				"createdOn": blog_obj.created_on,
				"author_id": blog_obj.author_id
			}
			await es_submit_blog_data(data)
			# End

			db.commit()
			db.refresh(blog_obj)
			return Result(status=True, data=blog_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	async def update_blog(self, data:dict, db):
		data.update({"user_id": self.id})
		try:
			data = BlogUpdateSchema(**data)
			blog_obj = db.query(Blog).get(data.blog_id)
			if data.title and blog_obj.title!=data.title:
				blog_obj.title = data.title
			if data.content and blog_obj.content!=data.content:
				new_read_time = math.ceil(countWords(data.content)/app_config.AVG_WPM)
				blog_obj.content = data.content
				blog_obj.read_time = new_read_time
			for category_data in data.categories:
				category_id, action = category_data["id"], category_data["action"]
				if action==CategoryAction.add and not(db.query(BlogMapCategory).filter_by(blog_id=blog_obj.id, category_id=category_id).first()):
					blog_map_category_obj = BlogMapCategory(blog_id=blog_obj.id, category_id=category_id)
					db.add(blog_map_category_obj)
				elif action==CategoryAction.delete:
					blog_map_category_obj = db.query(BlogMapCategory).filter_by(blog_id=blog_obj.id, category_id=category_id).first()
					if blog_map_category_obj:
						db.delete(blog_map_category_obj)
			db.flush()

			categories = []
			blog_map_category_objs = db.query(BlogMapCategory).filter_by(blog_id=blog_obj.id).all()
			for blog_map_category_obj in blog_map_category_objs:
				category_id = blog_map_category_obj.category_id
				category_name = db.query(BlogCategory).get(category_id).name
				categories.append({
					"id": category_id,
					"name": category_name
				})

			# Submit Data to Elastic Search
			data = {
				"id": blog_obj.id,
				"title": blog_obj.title,
				"content": blog_obj.content,
				"read_time": blog_obj.read_time,
				"categories": categories,
				"createdOn": blog_obj.created_on,
				"author_id": blog_obj.author_id
			}
			await es_update_blog_data(data)
			# End

			db.commit()
			db.refresh(blog_obj)
			return Result(status=True, data=blog_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	async def delete_blog(self, data:dict, db):
		data.update({"user_id": self.id})
		try:
			data = BlogDeleteSchema(**data)
			blog_obj = db.query(Blog).get(data.blog_id)
			db.delete(blog_obj)
			# Submit Data to Elastic Search
			data = {
				"id": blog_obj.id,
				"title": blog_obj.title,
				"content": blog_obj.content,
				"createdOn": blog_obj.created_on,
			}
			await es_delete_blog_data(blog_obj.id)
			# End
			db.commit()
			return Result(status=True)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	def like_blog(self, data:dict, db):
		try:
			data = BlogLikeUnlikeSchema(**data)
			bloge_like_obj = BlogLike(user_id=self.id, blog_id=data.blog_id)
			db.add(bloge_like_obj)
			db.commit()
			db.refresh(bloge_like_obj)
			return Result(status=True, data=bloge_like_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))
	
	def unlike_blog(self, data:dict, db):
		try:
			data = BlogLikeUnlikeSchema(**data)
			bloge_like_obj = db.query(BlogLike).filter_by(user_id=self.id, blog_id=data.blog_id).first()
			if bloge_like_obj:
				db.delete(bloge_like_obj)
				db.commit()
			return Result(status=True)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	def create_blog_comment(self, data:dict, db):
		try:
			data = CreateBlogCommentSchema(**data)
			blog_comment_obj = BlogComment(user_id=self.id, blog_id=data.blog_id, comment=data.comment)
			db.add(blog_comment_obj)
			db.commit()
			db.refresh(blog_comment_obj)
			return Result(status=True, data=blog_comment_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	def update_blog_comment(self, data:dict, db):
		data.update({"user_id": self.id})
		try:
			data = UpdateBlogCommentSchema(**data)
			blog_comment_obj = db.query(BlogComment).get(data.comment_id)
			blog_comment_obj.comment = data.comment
			db.commit()
			db.refresh(blog_comment_obj)
			return Result(status=True, data=blog_comment_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))

	def delete_blog_comment(self, data:dict, db):
		data.update({"user_id": self.id})
		try:
			data = DeleteBlogCommentSchema(**data)
			blog_comment_obj = db.query(BlogComment).get(data.comment_id)
			db.delete(blog_comment_obj)
			db.commit()
			return Result(status=True)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))


class UserDetail(Base):
	__tablename__ = "user_detail"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id"), unique=True )
	first_name = Column( String )
	last_name = Column( String )
	contact_no = Column( BigInteger, unique=True )
	date_of_birth = Column( Date )
	image = Column( String, default="default_user.png" )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class Followers(Base):
	__tablename__ = "followers"
	__table_args__ = (UniqueConstraint('follower_id', 'following_id', name='no_duplicate_entry'),)
	
	id = Column( Integer, primary_key = True, index = True )
	follower_id = Column( Integer, ForeignKey("user.id") )
	following_id = Column( Integer, ForeignKey("user.id") )

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

