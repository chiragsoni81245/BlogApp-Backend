from functools import lru_cache
from fastapi import responses
from fastapi.encoders import jsonable_encoder
from sqlalchemy.sql.elements import Grouping
from sqlalchemy.sql.functions import concat
from app import models
from sqlalchemy.sql import func

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
			models.BlogMapCategory.blog_id==models.BlogLike.id, isouter=True
		).join(
			models.BlogCategory,
			models.BlogCategory.id==models.BlogMapCategory.category_id
		).group_by(
			models.BlogMapCategory.category_id
		).filter(
			models.BlogLike.user_id==user.id
		).all()

		categories = list(map(lambda x: x.category_id, categories_for_user))
		should_queries = []
		for i in categories:
			should_queries.append({ 
				"match": { 
					"categories.name": {
						"query": i,
					}, 
				}, 
			})

		response = await es_search_blogs({
			"from": str((page-1)*page_size),
			"size": str(page_size),
			"query":{
				"bool":{
					"should":should_queries
				}
			}
		})

		return response


