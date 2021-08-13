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
    company: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class User(BaseModel):
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None

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
    num_abstracts_to_screen: int

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

class Tag(BaseModel):
    classes: str
    text: str
    cui: str

class Document(BaseModel):
    name: str
    path: str

class LiveSummaryData(BaseModel):
    name: str
    date: str
    tags: List[Tag] = None
    document: List[Document] = None
    background: Optional[str] = None
    methods: Optional[str] = None
    results: Optional[str] = None
    conclusion: Optional[str] = None

class LiveSummarySections(BaseModel):
    background: Optional[str] = None
    methods: Optional[str] = None
    results: Optional[str] = None
    conclusion: Optional[str] = None
    automated_narrative_summary: Optional[str] = None


