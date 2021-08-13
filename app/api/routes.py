from typing import Dict
from urllib.parse import urlencode, parse_qsl

import httpx
from fastapi import APIRouter, Depends, status, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
import io

from sqlalchemy.orm import Session
from app.settings import settings
from app.database import get_db, SQLBase, engine
from .schemas import Url, AuthorizationResponse, GithubUser, User, Token, ReviewList, ArticleList, ScreeningDecision, LiveSummaryData, LiveSummarySections
from .helpers import generate_token, create_access_token, generate_uuid
from .crud import get_user_by_login, create_user, get_user, get_reviewlist_from_db, get_screenlist_from_db, sumbit_decision_to_db, get_review_status_text, get_review_included_studies_df, generate_summary_of_new_evidence, autocomplete, submit_live_summary_to_db, get_live_summary_from_db, update_user
from .dependencies import get_user_from_header
from .models import User as DbUser
from fastapi.encoders import jsonable_encoder

import app
import shutil
import os
import json

LOGIN_URL = "https://github.com/login/oauth/authorize"
REDIRECT_URL = f"{settings.app_url}/auth/github"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"

# create tables if not exist
SQLBase.metadata.create_all(engine)    

router = APIRouter()

@router.get("/login")
def get_login_url() -> Url:
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": REDIRECT_URL,
        "state": generate_token(),
    }
    return Url(url=f"{LOGIN_URL}?{urlencode(params)}")

@router.post("/authorize")
async def verify_authorization(
    body: AuthorizationResponse, db: Session = Depends(get_db)
) -> Token:
    params = {
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "code": body.code,
        "state": body.state,
    }

    async with httpx.AsyncClient() as client:
        token_request = await client.post(TOKEN_URL, params=params)
        response: Dict[bytes, bytes] = dict(parse_qsl(token_request.content))
        print("RESPONSE:")
        print(response)
        github_token = response[b"access_token"].decode("utf-8")
        github_header = {"Authorization": f"token {github_token}"}
        user_request = await client.get(USER_URL, headers=github_header)
        print(user_request.json())
        github_user = GithubUser(**user_request.json())
    db_user = get_user_by_login(db, github_user.login)

    
    if db_user is not None and db_user.login not in settings.github_whitelist:
        raise HTTPException(status_code=404, detail="User not found")


    if db_user is None:
        db_user = create_user(db, github_user)

    verified_user = User.from_orm(db_user)
    access_token = create_access_token(data=verified_user)

    return Token(access_token=access_token, token_type="bearer", user=db_user)


@router.get("/get_session", response_model=User)
def get_session(
    user: User = Depends(get_user_from_header),
    db: Session = Depends(get_db),
) -> DbUser:
    db_user = get_user(db, user.id)

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.get("/get_reviewlist", response_model=ReviewList)
def get_reviewlist(user: User = Depends(get_user_from_header),
                   db: Session = Depends(get_db),
) -> ReviewList:
    db_user = get_user(db, user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {"reviews": get_reviewlist_from_db(engine, user.login)}


@router.get("/get_screenlist/{revid}", response_model=ArticleList)
def get_screenlist(revid: str,
                   user: User = Depends(get_user_from_header),
                   db: Session = Depends(get_db),

) -> ArticleList:
    db_user = get_user(db, user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    articles = get_screenlist_from_db(engine, revid, user.login)
    return {"articles": articles}


@router.post("/update_abstract/")
def update_abstract(
               decision: ScreeningDecision,
               user: User = Depends(get_user_from_header),
               db: Session = Depends(get_db),):
    db_user = get_user(db, user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")    
    sumbit_decision_to_db(db, user.login, decision.revid, decision.pmid, decision.decision)
    return {"didit": True}


@router.get("/summarize_new_evidence/{revid}")
def get_generated_summary(
               revid: str,               
               db: Session = Depends(get_db),):    
    #update_text = get_review_status_text(db, revid)
    #return update_text
    #import pdb; pdb.set_trace()
    summary = generate_summary_of_new_evidence(db, revid)
    return summary



@router.get("/get_review_included_studies/{revid}")
def get_review_included_studies(
               revid: str,               
               db: Session = Depends(get_db),):    
    update_text = get_review_status_text(db, revid)
    stream = io.StringIO()

    df = get_review_included_studies_df(db, revid)

    df.to_csv(stream, index = False)

    response = StreamingResponse(iter([stream.getvalue()]),
                        media_type="text/csv"
    )

    response.headers["Content-Disposition"] = "attachment; filename=included_studies.csv"

    return response

@router.get("/get_autocomplete_tags")
def get_autocomplete_tags(
                q: str,):
    tags = autocomplete(q)
    return JSONResponse(content=tags)

@router.post("/create_live_summary")
def create_live_summary(
                live_summary: LiveSummaryData,
                user: User = Depends(get_user_from_header),
                db: Session = Depends(get_db),):
    db_user = get_user(db, user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # tags (keyword_filters) to json
    keyword_filter = json.dumps([tag.json() for tag in live_summary.tags])
    print(keyword_filter)

    live_summary_sections = LiveSummarySections(
        background=live_summary.background,
        methods=live_summary.methods,
        results=live_summary.results,
        conclusion=live_summary.conclusion
    )

    submit_live_summary_to_db(db, live_summary.name, live_summary.date, keyword_filter, live_summary_sections, live_summary.document[0].path, user.login)
    return {"success": True}

@router.get("/get_live_review_summary/{revid}", response_model=LiveSummarySections)
def get_reviewlist(revid: str,               
                db: Session = Depends(get_db),) -> LiveSummarySections:
    live_summary_sections_from_db = get_live_summary_from_db(db, revid)

    if len(live_summary_sections_from_db) == 0:
        return LiveSummarySections()

    response_dict = {}
    for section in live_summary_sections_from_db:
        section_name = section.section
        response_dict[section_name] = section.text

    response = LiveSummarySections(
        background=response_dict["background"],
        methods=response_dict["methods"],
        results=response_dict["results"],
        conclusion=response_dict["conclusion"],
        automated_narrative_summary=response_dict["automated_narrative_summary"]
    )
    return response

@router.post("/update_user_information")
def update_user_information(
                new_user_info: User,
                user: User = Depends(get_user_from_header),
                db: Session = Depends(get_db),):
    update_user(db, user.id, new_user_info)
    return {"success": True}


@router.post("/upload_csv")
async def upload_csv(csv_file: UploadFile = File(...)):
    uuid = generate_uuid(5)
    filename = uuid + "-" + csv_file.filename
    file_location = os.path.join(app.CSV_ROOT, filename)
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(csv_file.file, file_object)
    
    return {"name": filename, "path": file_location}


