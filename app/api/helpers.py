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
    unique_id = base64.urlsafe_b64encode(os.urandom(16))[:11].decode('utf-8')
    from_review_title = review_title[:5].lower()
    return from_review_title + unique_id
