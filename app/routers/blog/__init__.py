from os import path
from re import search
from fastapi import APIRouter, Request, Depends
from sqlalchemy.sql.functions import func
import sqlalchemy
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
from app import popularity_base_recommander, content_base_recommander

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


@router.get('/recommended')
@is_authorized
def get_recommended_blogs(request: Request, page:int =1, page_size:int = 5, db:Session = Depends(get_db)):
	total_likes_by_this_user = db.query(BlogLike.id).filter_by(user_id=request.current_user.id).count()
	if total_likes_by_this_user>1:
		response = content_base_recommander.recommend(db, request.current_user, page, page_size)
	else:
		response = popularity_base_recommander.recommend(db, page, page_size)
	
	total_blogs = response["total_results"]
	blogs = response["results"]
			
	return { 
		"metadata":{
			"page": page,
			"page_size": page_size
		},
		"total_results": total_blogs,
		"result": jsonable_encoder(blogs)
	}


@router.get('/{blog_id}')
@is_authorized
def get_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	blog_like = db.query( 
			models.BlogLike.blog_id.label('blog_id'),  func.count(models.BlogLike.user_id).label('like_count')
	).group_by( models.BlogLike.blog_id ).subquery()
	blog_comment = db.query( 
			models.BlogComment.blog_id.label('blog_id'),  func.count(models.BlogComment.user_id).label('comment_count')
	).group_by( models.BlogComment.blog_id ).subquery()
	blog_view = db.query( 
			models.BlogView.blog_id.label('blog_id'),  func.count(models.BlogView.user_id).label('view_count')
	).group_by( models.BlogView.blog_id ).subquery()

	blog = db.query(
		models.Blog.id, models.Blog.title, models.Blog.content, models.Blog.author_id, models.Blog.read_time,
		blog_like.columns.get("like_count"), 
		blog_comment.columns.get("comment_count"),
		blog_view.columns.get("view_count")
	).join(
		blog_like, blog_like.columns.get("blog_id")==models.Blog.id, isouter=True
	).join(
		blog_comment, blog_comment.columns.get("blog_id")==models.Blog.id, isouter=True
	).join(
		blog_view, blog_view.columns.get("blog_id")==models.Blog.id, isouter=True
	).filter(models.Blog.id==blog_id).first()	

	if blog:
		blog = jsonable_encoder(blog)
		blog["like_count"] = blog["like_count"] or 0
		blog["view_count"] = blog["view_count"] or 0
		blog["comment_count"] = blog["comment_count"] or 0
		author_id = blog.pop("author_id")
		blog["author"] = jsonable_encoder(
			db.query(
				models.User.id, models.User.email, 
				models.UserDetail.contact_no,
				models.UserDetail.first_name,
				models.UserDetail.last_name,
				models.UserDetail.image,
			).join(
				models.UserDetail, models.UserDetail.user_id==models.User.id
			).filter(models.User.id==author_id).first()
		)

		first_name, last_name = blog["author"].pop("first_name"), blog["author"].pop("last_name")
		if last_name:
			name = "{} {}".format(first_name, last_name)
		else:
			name = first_name
		
		blog["author"]["name"] = name
		blog["author"]["image"] = request.url_for('static', path="user_images/{}".format(blog["author"]["image"]))

		# Add a view entry in BlogView Table
		try:
			blog_view_obj = models.BlogView(user_id=request.current_user.id, blog_id=blog["id"])
			db.add(blog_view_obj)
			db.commit()
		except sqlalchemy.exc.IntegrityError:
			pass
		# End

		return { 
			"result": blog
		}
	else:
		return JSONResponse(
			content={"error_msg": "Blog not found"},
			status_code=404
		)


@router.get('/my_feed')
@is_authorized
def get_my_feed(request: Request, page:int =1, page_size:int = 5, db:Session = Depends(get_db)):
	followings = db.query(models.Followers.following_id).filter_by(follower_id=request.current_user.id).all()
	followings = list(map(lambda x: x[0], followings))

	blogs = db.query(models.Blog).filter(
		models.Blog.author_id.in_(followings)
	).order_by( models.Blog.created_on.desc() )
	total_blogs = blogs.count()
	blogs = jsonable_encoder(blogs.offset((page-1)*page_size).limit(page_size))

	for i in range(len(blogs)):
		author_id = blogs[i].pop("author_id")
		blogs[i]["author"] = jsonable_encoder(
			db.query(
				models.User.id, models.User.email, 
				models.UserDetail.contact_no,
				models.UserDetail.first_name,
				models.UserDetail.last_name,
				models.UserDetail.image,
			).join(
				models.UserDetail, models.UserDetail.user_id==models.User.id
			).filter(models.User.id==author_id).first()
		)

		first_name, last_name = blogs[i]["author"].pop("first_name"), blogs[i]["author"].pop("last_name")
		if last_name:
			name = "{} {}".format(first_name, last_name)
		else:
			name = first_name

		blogs[i]["author"]["name"] = name
		blogs[i]["author"]["image"] = request.url_for('static', path="user_images/{}".format(blogs[i]["author"]["image"]))


	return { 
		"metadata":{
			"page": page,
			"page_size": page_size
		},
		"total_results": total_blogs,
		"result": blogs
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
							"categories.name": {
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

		for i in range(len(response["results"])):
			author_id = response["results"][i]["source"].pop("author_id")
			response["results"][i]["source"]["author"] = jsonable_encoder(
				db.query(
					models.User.id, models.User.email, 
					models.UserDetail.contact_no,
					models.UserDetail.first_name,
					models.UserDetail.last_name,
					models.UserDetail.image,
				).join(
					models.UserDetail, models.UserDetail.user_id==models.User.id
				).filter(models.User.id==author_id).first()
			)

			first_name, last_name = response["results"][i]["source"]["author"].pop("first_name"), response["results"][i]["source"]["author"].pop("last_name")
			if last_name:
				name = "{} {}".format(first_name, last_name)
			else:
				name = first_name

			response["results"][i]["source"]["author"]["name"] = name
			response["results"][i]["source"]["author"]["image"] = request.url_for('static', path="user_images/{}".format(response["results"][i]["source"]["author"]["image"]))

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


@router.get('/{blog_id}/like')
@is_authorized
def like_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	data = {"blog_id": blog_id}
	user = request.current_user
	result = user.like_blog(data, db)
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


@router.get('/{blog_id}/unlike')
@is_authorized
def unlike_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	data = {"blog_id": blog_id}
	user = request.current_user
	result = user.unlike_blog(data, db)
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


@router.get('/{blog_id}/comments')
@is_authorized
def get_blog_comments(request: Request, blog_id:int = None, page:int = 1, page_size:int = 10, db:Session = Depends(get_db)):
	comments = db.query(
		models.BlogComment.comment, 
		models.UserDetail.first_name, 
		models.UserDetail.last_name, 
		models.UserDetail.image
	).join(
		models.UserDetail, models.UserDetail.user_id==models.BlogComment.user_id, isouter=True
	).filter( models.BlogComment.blog_id==blog_id )

	total_comments = comments.count()
	comments = jsonable_encoder(comments.offset((page-1)*page_size).limit(page_size).all())
	for i in range(len(comments)):
		comments[i]["user"] = {}
		first_name = comments[i].pop("first_name")
		last_name = comments[i].pop("last_name")
		image = comments[i].pop("image")
		if last_name:
			comments[i]["user"]["name"] = "{} {}".format(first_name, last_name)
		else:
			comments[i]["user"]["name"] = first_name
		if image:
			comments[i]["user"]["image"] = request.url_for('static', path="user_images/{}".format(image))
		else:
			comments[i]["user"]["image"] = None

	return {
		"metadata":{
			"page": page,
			"page_size": page_size
		},
		"total_results": total_comments,
		"result": comments
	}
	

@router.post('/{blog_id}/comments')
@is_authorized
async def create_comment_blog(request: Request, blog_id:int = None, db:Session = Depends(get_db)):
	data = await request.json()
	data.update({"blog_id": blog_id})
	result = request.current_user.create_blog_comment(data, db)
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


@router.put('/{blog_id}/comments/{comment_id}')
@is_authorized
async def update_comment_blog(request: Request, blog_id:int = None, comment_id:int = None, db:Session = Depends(get_db)):
	data = await request.json()
	data.update({"blog_id": blog_id})
	data.update({"comment_id": comment_id})
	result = request.current_user.update_blog_comment(data, db)
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


@router.delete('/{blog_id}/comments/{comment_id}')
@is_authorized
async def delete_comment_blog(request: Request, blog_id:int = None, comment_id:int = None, db:Session = Depends(get_db)):
	data = {"blog_id": blog_id}
	data.update({"comment_id": comment_id})
	result = request.current_user.delete_blog_comment(data, db)
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

