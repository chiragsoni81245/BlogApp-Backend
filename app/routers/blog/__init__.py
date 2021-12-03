from os import path
from re import search
from fastapi import APIRouter, Request, Depends
from sqlalchemy.sql.functions import current_user
from sqlalchemy.sql.sqltypes import JSON

from app.schemas.blog_schema import BlogCategoryCreateSchema
from ...database import *
from ...models import *
from ...schemas.blog_schema import *
from ...decorators import *
from ...utilities import get_error_messages
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
import time
from elasticsearch_client import es_search_blogs

router = APIRouter()

@router.get('/categories')
@is_authorized
def get_all_blog_categories(request: Request, db:Session = Depends(get_db)):
	categories = db.query(BlogCategory.id, BlogCategory.name).order_by( BlogCategory.name.asc() ).all()
	return { "result": jsonable_encoder(categories) }


@router.post('/categories')
@user_have_roles(['Admin'])
async def create_blog_categories(request: Request, db:Session = Depends(get_db)):
	data = await request.json()
	result = BlogCategory.create(data, db)
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


@router.get('/')
@is_authorized
def get_all_blogs(request: Request, page:int =1, page_size:int = 5, db:Session = Depends(get_db)):
	blogs = db.query(Blog).order_by( 
				Blog.created_on.desc() 
			)
	total_blogs = blogs.count()
	blogs = blog.offset((page-1)*page_size).limit(page_size)
			
	return { 
		"metadata":{
			"page": page,
			"page_size": page_size
		},
		"total_results": total_blogs,
		"result": jsonable_encoder(blogs)
	}


@router.get('/my_feed')
@is_authorized
def get_my_feed(request: Request, page:int =1, page_size:int = 5, db:Session = Depends(get_db)):
	followings = db.query(Followers.following_id).filter_by(follower_id=request.current_user.id).all()
	followings = list(map(lambda x: x[0], followings))

	blogs = db.query(Blog).filter(
		Blog.author_id.in_(followings)
	).order_by( Blog.created_on.desc() )
	total_blogs = blogs.count()
	blogs = blogs.offset((page-1)*page_size).limit(page_size)
	
	return { 
		"metadata":{
			"page": page,
			"page_size": page_size
		},
		"total_results": total_blogs,
		"result": jsonable_encoder(blogs)
	}


@router.post('/search')
@is_authorized
async def search(request: Request, page:int =1, page_size:int = 10, db:Session = Depends(get_db)):
	data = await request.json()
	try:
		data = BlogSearchSchema(**data, page=page, page_size=page_size)
		# Implement Elastic Search
		categories = []
		for categorie in db.query(models.BlogCategory).filter( models.BlogCategory.id.in_(data.categories) ).all():
			categories.append(categorie.name)

		should_search = []
		if data.text:
			should_search.append({
				"match": {
					"title": {
						"query": data.text,
						"boost": 3
					}
				},
			})
			should_search.append({
				"match": {
					"content": {
						"query": data.text,
						"boost": 2
					}
				},
			})
		if data.categories:
			for i in categories:
				should_search.append(
					{ 
						"match": { 
							"categories": {
								"query": i,
								"boost": 6
							}, 
						}, 
					}
				)

		response = await es_search_blogs({
			"from": str((page-1)*page_size),
			"size": str(page_size),
			"query":{
				"bool":{
					"should": should_search
				}
			},
		})
		return {
			"metadata": {
				"page": page,
				"page_size": page_size
			},
			"total_results": response["total_results"],
			"result": response["results"]
		}
	except ValidationError as error:
		return JSONResponse(
			content={ "error_msg": get_error_messages(error) }, 
			status_code=400
		)
	


@router.post('/')
@is_authorized
async def create_blog(request: Request, db:Session = Depends(get_db)):
	data = await request.json()
	user = request.current_user
	result = await user.create_blog(data, db)
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


@router.put('/{blog_id}')
@is_authorized
async def update_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	data = await request.json()
	data.update({"blog_id": blog_id})
	user = request.current_user
	result = await user.update_blog(data, db)
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


@router.delete('/{blog_id}')
@is_authorized
async def delete_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	data = {"blog_id": blog_id}
	user = request.current_user
	result = await user.delete_blog(data, db)
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


