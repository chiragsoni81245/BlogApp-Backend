from functools import lru_cache
from fastapi import responses
from fastapi.encoders import jsonable_encoder
from sqlalchemy.sql.elements import Grouping
from sqlalchemy.sql.functions import concat
from app import models
from sqlalchemy.sql import func
import elasticsearch
from app.models.blog import BlogLike, BlogMapCategory
from elasticsearch_client import es_search_blogs

class ContentBaseRecommender:

	def __init__(self):
		pass

	async def recommend(self, db, user, page, page_size):
		categories_for_user = db.query(
			models.BlogCategory.name
		).join(
			models.BlogMapCategory,
			models.BlogCategory.id==models.BlogMapCategory.category_id
		).join(
			models.BlogLike, 
			models.BlogMapCategory.blog_id==models.BlogLike.blog_id, isouter=True
		).group_by(
			models.BlogCategory.name
		).filter(
			models.BlogLike.user_id==user.id
		).all()

		categories = list(map(lambda x: x.name, categories_for_user))
		should_queries = []
		for i in categories:
			should_queries.append({ 
				"match": { 
					"categories": {
						"query": i,
					}, 
				}, 
			})

		users_viewed_blogs = list(map(
			lambda x: x.blog_id, 
			db.query(models.BlogView.blog_id).filter_by(user_id=user.id).all()
		))
		must_not_queries = []
		for blog_id in users_viewed_blogs:
			must_not_queries.append({
				"term": { 
					"id": blog_id
				}
			})	

		try:
			response = await es_search_blogs({
				"from": str((page-1)*page_size),
				"size": str(page_size),
				"query":{
					"bool":{
						"should":should_queries,
						"must_not": must_not_queries
					}
				}
			})
		except elasticsearch.exceptions.RequestError as error:
			print(error)
			response = {"results": [], "total_results": 0}

		return response


