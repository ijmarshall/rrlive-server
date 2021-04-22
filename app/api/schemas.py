from pydantic import BaseModel
import datetime
from typing import Optional, List


class Url(BaseModel):
    url: str


class AuthorizationResponse(BaseModel):
    state: str
    code: str


class GithubUser(BaseModel):
    login: str
    name: str = None
    company: str = None
    location: str = None
    email: str = None
    avatar_url: str = None


class User(BaseModel):
    id: int
    login: str
    name: str
    email: str = None

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class Review(BaseModel):
    revid: str
    title: str
    last_updated: datetime.datetime

class ReviewList(BaseModel):
    reviews: List[Review]

class Article(BaseModel):
    """
    structured Trialstreamer data on an article
    """
    pmid: str
    year: int
    ti: str
    ab: str
    citation: str
    journal: str
    num_randomized: str
    prob_low_rob: float
    effect: str
    decision: str = None

class ArticleList(BaseModel):
    articles: List[Article] = None

class ScreeningDecision(BaseModel):
    pmid: str
    revid: str
    decision: bool = None



