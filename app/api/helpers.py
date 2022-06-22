from datetime import datetime, timedelta
import string
import random

import jwt
import os
import base64

from app.settings import settings

from .schemas import User

def generate_token(length: int = 24) -> str:
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(length)
    )


def create_access_token(*, data: User, exp: int = None) -> bytes:
    to_encode = data.dict()
    if exp is not None:
        to_encode.update({"exp": exp})
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt

def generate_rev_id(review_title):
    unique_id = base64.urlsafe_b64encode(os.urandom(16))[:10].decode('utf-8')
    from_review_title = review_title[:5].lower().strip()
    return from_review_title + "-" + unique_id


def generate_uuid(length):
    return base64.urlsafe_b64encode(os.urandom(16))[:length].decode('utf-8')


def get_api_input_format(original_title, original_summary, articles):
    articles_list = []
    for art in articles:
        row = {
                'title': art.ti,
                'abstract': art.ab,
                }
        articles_list.append(row)

    return {
        "existing_summary_title": original_title,
        "existing_summary": original_summary,
        "articles": articles_list
    }