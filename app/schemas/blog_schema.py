from typing_extensions import TypedDict
from fastapi.datastructures import UploadFile
from pydantic import BaseModel
from typing import Optional
from pydantic import validator
from sqlalchemy.sql import base
from sqlalchemy.sql.sqltypes import Enum
from typing import List
from .. import models
from ..database import SessionLocal
import re
from datetime import date
from ..routers.auth.utilities import verify_reset_password_token


class BlogCategoryCreateSchema(BaseModel):

	name: str

	@validator('name')
	def validate_name(cls, value):
		db = SessionLocal()
		blog_category_obj = db.query(models.BlogCategory).filter_by(name=value).first()
		if blog_category_obj:
			raise ValueError('This category name is already exists')
		return value


class BlogCreateSchema(BaseModel):

	title: str
	user_id: int
	content: str
	categories: List[int]

	@validator('user_id')
	def valid_user_id(cls, value):
		db = SessionLocal()
		user_obj = db.query(models.User).get(value)
		if not user_obj:
			raise ValueError('Invalid user')
		return value

	@validator('categories')
	def valid_categories(cls, value):
		db = SessionLocal()
		for category_id in value:
			category_obj = db.query(models.BlogCategory).get(category_id)
			if not category_obj:
				raise ValueError('Invalid category_id {}'.format(category_id))
		return value



class CategoryAction(Enum, str):
	delete = "remove"
	add = "add"

class CategoryUpdate(TypedDict):
	id : int
	action: CategoryAction 


class BlogUpdateSchema(BaseModel):

	user_id: int
	blog_id: int
	title: Optional[str]
	content: Optional[str]
	categories: Optional[List[CategoryUpdate]] = []

	@validator('user_id')
	def valid_user_id(cls, value):
		db = SessionLocal()
		user_obj = db.query(models.User).get(value)
		if not user_obj:
			raise ValueError('Invalid user')
		return value

	@validator('blog_id')
	def valid_blog_id(cls, value, values):
		db = SessionLocal()
		blog_obj = db.query(models.Blog).get(value)
		if not blog_obj:
			raise ValueError('blog does not exists')
		if blog_obj.author_id!=values["user_id"]:
			raise ValueError("You don't have permission to edit this blog")
		return value

	@validator('categories')
	def valid_categories(cls, value):
		db = SessionLocal()
		for data in value:
			category_id, action = data["id"], data["action"]
			category_obj = db.query(models.BlogCategory).get(category_id)
			if not category_obj:
				raise ValueError('Invalid category_id {}'.format(category_id))
		return value


class BlogDeleteSchema(BaseModel):

	user_id: int
	blog_id: int

	@validator('user_id')
	def valid_user_id(cls, value):
		db = SessionLocal()
		user_obj = db.query(models.User).get(value)
		if not user_obj:
			raise ValueError('Invalid user')
		return value

	@validator('blog_id')
	def valid_blog_id(cls, value, values):
		db = SessionLocal()
		blog_obj = db.query(models.Blog).get(value)
		if not blog_obj:
			raise ValueError('blog does not exists')
		if blog_obj.author_id!=values["user_id"]:
			raise ValueError("You don't have permission to delete this blog")
		return value


class BlogSearchSchema(BaseModel):

	text: Optional[str]
	categories: Optional[List[int]] = []
	page: int
	page_size: int

	@validator('page')
	def validate_page(cls, value):
		if value<=0:
			raise ValueError('Invalid page number')

	@validator('page_size')
	def validate_page_size(cls, value):
		if value<=0:
			raise ValueError('Invalid page size')

	@validator('categories')
	def validate_categories(cls, value):
		db = SessionLocal()
		for category_id in value:
			category_obj = db.query(models.BlogCategory).get(category_id)
			if not category_obj:
				raise ValueError('Invalid category_id {}'.format(category_id))
		return value