from functools import lru_cache
from fastapi.encoders import jsonable_encoder
from app import models
from sqlalchemy.sql import func

from app.models.blog import BlogView


class PopularityBaseRecommander:

    def __init__(self):
        pass

    def recommend(self, db, user, page:int, page_size:int):
        blog_like = db.query( 
                models.BlogLike.blog_id.label('blog_id'),  func.count(models.BlogLike.user_id).label('like_count')
        ).group_by( models.BlogLike.blog_id ).subquery()
        blog_comment = db.query( 
                models.BlogComment.blog_id.label('blog_id'),  func.count(models.BlogComment.user_id).label('comment_count')
        ).group_by( models.BlogComment.blog_id ).subquery()
        blog_view = db.query( 
                models.BlogView.blog_id.label('blog_id'),  func.count(models.BlogView.user_id).label('view_count')
        ).group_by( models.BlogView.blog_id ).subquery()

        blogs = db.query(
            models.Blog.id,
            models.Blog.title,
            models.Blog.content,
            models.Blog.read_time,
            models.Blog.created_on.label("createdOn")
        ).join(
            blog_view, blog_view.columns.get("blog_id")==models.Blog.id, isouter=True
        ).join(
            blog_like, blog_like.columns.get("blog_id")==models.Blog.id, isouter=True
        ).join(
            blog_comment, blog_comment.columns.get("blog_id")==models.Blog.id, isouter=True
        ).filter(
            models.Blog.id.notin_(list(map(
                lambda x: x.blog_id, 
                db.query(BlogView.blog_id).filter_by(user_id=user.id).all()
            )))   
        ).order_by(
            blog_view.columns.get("view_count").desc(),
            blog_like.columns.get("like_count").desc(),
            blog_comment.columns.get("comment_count").desc(),
        )

        total_blogs = blogs.count()
        blogs = blogs.offset((page-1)*page_size).limit(page_size).all()
        blogs = jsonable_encoder(blogs)
        for i in range(len(blogs)):
            categories = list(map(
                lambda x: x.name,
                db.query(
                    models.BlogCategory.id,
                    models.BlogCategory.name
                ).join(
                    models.BlogMapCategory,
                    models.BlogMapCategory.category_id==models.BlogCategory.id
                ).filter(
                    models.BlogMapCategory.blog_id==blogs[i]["id"]
                ) 
            ))
            blogs[i]["categories"] = categories

        return {
            "total_results": total_blogs,
            "results": blogs
        }


# psi -> population stability index
# new_product -> 
# auc -> 