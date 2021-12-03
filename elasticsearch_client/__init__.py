import asyncio
from datetime import datetime
from elasticsearch import Elasticsearch

es = Elasticsearch()

es.indices.create(index="blogs", ignore=400, mappings={
    "properties": {
        "id": {"type": "integer", "index": False},
        "title": {"type": "string", "index": True, "analyzer": "english"},
        "content": {"type": "string", "index": True, "analyzer": "english"},
        "categories": [{"type": "string", "index": False}],
        "createdOn": {"type": "datetime", "index": False},
    }
})

async def es_submit_blog_data(data:dict):
    response = es.create(
        index="blogs",
        id=str(data["id"]),
        document= data
    )
    return response


async def es_update_blog_data(data:dict):
    response = es.delete(
        index="blogs",
        id=str(data["id"]),
    )
    response = es.create(
        index="blogs",
        id=str(data["id"]),
        document= data
    )
    return response


async def es_delete_blog_data(blog_id:int):
    response = es.delete(
        index="blogs",
        id=blog_id
    )
    return response


async def es_search_blogs(data):
    response = es.search(
        index="blogs",
        body=data
    )

    blogs = []
    for blog in response["hits"]["hits"]:
        blogs.append({ "source": blog["_source"], "score": blog["_score"]})

    return { "results": blogs, "total_results": response['hits']["total"]["value"] }