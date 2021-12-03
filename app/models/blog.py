from logging import error
from fastapi.param_functions import Depends
from sqlalchemy import Boolean, Column, TEXT, Integer, String, DateTime, text, ForeignKey, Date, Text
from sqlalchemy.sql.functions import user
from sqlalchemy.sql.sqltypes import BigInteger
from app.database import Base, SessionLocal, engine, get_db
from passlib.context import CryptContext
from sqlalchemy.orm import Session, relationship
import jwt
from time import time
from datetime import datetime
from ..models import *
from ..schemas.blog_schema import *
from ..schemas import Result
from ..utilities import get_error_messages
from pydantic import ValidationError
import base64, os
from pyotp import TOTP
import aiofiles


class BlogCategory(Base):
	__tablename__ = "blog_category"

	id = Column( Integer, primary_key = True, index = True )
	name = Column( String, unique=True, nullable=False )

	blogs = relationship( "BlogMapCategory", back_populates = "category" )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )

	@staticmethod
	def create(data, db):
		try:
			data = BlogCategoryCreateSchema(**data)
			blog_category_obj = BlogCategory(name=data.name)
			db.add(blog_category_obj)
			db.commit()
			db.refresh(blog_category_obj)
			return Result(status=True, data=blog_category_obj)
		except ValidationError as error:
			return Result(status=False, error_msg=get_error_messages(error))


class Blog(Base):
	__tablename__ = "blog"

	id = Column( Integer, primary_key = True, index = True )
	author_id = Column( Integer, ForeignKey("user.id") )
	title = Column( String, index=True )
	content = Column( TEXT )

	author = relationship( "User" )
	categories = relationship( "BlogMapCategory", back_populates = "blog", cascade="all,delete" )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class BlogMapCategory(Base):
	__tablename__ = "blog_map_category"

	id = Column( Integer, primary_key = True, index = True )
	blog_id = Column( Integer, ForeignKey("blog.id") )
	category_id = Column( Integer, ForeignKey("blog_category.id") )

	blog = relationship( "Blog" )
	category = relationship( "BlogCategory" )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class BlogLike(Base):
	__tablename__ = "blog_like"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id") )
	blog_id = Column( Integer, ForeignKey("blog.id") )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )


class BlogComment(Base):
	__tablename__ = "blog_comment"

	id = Column( Integer, primary_key = True, index = True )
	user_id = Column( Integer, ForeignKey("user.id") )
	blog_id = Column( Integer, ForeignKey("blog.id") )
	comment = Column( String, nullable=False )

	created_on = Column( DateTime, default = datetime.now )
	updated_on = Column( DateTime, onupdate = datetime.now )