from typing import List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from .schemas import GithubUser
from .models import User



def get_user(db: Session, user_id: int) -> Optional[User]:
    print("get user")
    return db.query(User).filter_by(id=user_id).first()


def get_user_by_login(db: Session, login: str) -> Optional[User]:
    print("get user by login")
    return db.query(User).filter_by(login=login).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    print("getting users")
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, github_user: GithubUser) -> User:
    user = User(
        login=github_user.login,
        name=github_user.name,
        email=github_user.email,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_reviewlist_from_db(engine, user_id: str) -> list:
    reviewmeta = pd.read_sql("select revmeta.* from revmeta, permissions where permissions.login=%(user_id)s and revmeta.revid=permissions.revid;",
                             engine,
                             params = {"user_id": user_id})
    return reviewmeta.to_dict('records')
    
def get_screenlist_from_db(engine, revid: str, user_id: str) -> list:
    toscreen = pd.read_sql("""select pm.pmid, pm.year, pm.ti, pm.ab, pm.pm_data->'authors' as authors,
            pm.pm_data->'journal' as journal, pa.num_randomized, pa.prob_low_rob, pa.effect from manscreen as ms, pubmed as pm,
            pubmed_annotations as pa, permissions where permissions.revid=%(revid)s and permissions.login=%(user_id)s
            and decision is null and pm.pmid=ms.pmid and pm.pmid=pa.pmid and permissions.revid=ms.revid;""",
            engine, params={"revid": revid, "user_id": user_id})
    cites = [get_cite(r.authors, r.journal, r.year) for (i, r) in toscreen.iterrows()]
    toscreen.drop("authors", axis=1, inplace=True)
    toscreen['citation'] = cites
    return toscreen.to_dict('records')


def get_cite(authors, journal, year) -> str:
    if len(authors) >= 1 and authors[0]['LastName']:
        return f"{authors[0]['LastName']}{' et al.' if len(authors) > 1 else ''}, {journal}. {year}"
    else:
        return f"{journal}. {year}"

def sumbit_decision_to_db(db: Session, userid, revid, pmid, decision):
    # update the last updated date    


    db.connection().execute("""UPDATE manscreen SET decision = %(decision)s, login = %(userid)s 
                        FROM permissions WHERE manscreen.revid='covax' AND manscreen.pmid=%(pmid)s AND
                        permissions.login = %(userid)s AND permissions.revid=manscreen.revid;""",
                        ({"revid":revid, "pmid": pmid,"decision": decision, "userid": userid}))
    db.commit()
    