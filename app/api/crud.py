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

def get_review_included_studies_df(db, revid: str) -> pd.DataFrame:
    included_studies_df = pd.read_sql("""select pm.pmid, pm.year, pm.ti, pm.ab, pm.pm_data->'authors' as authors,
            pm.pm_data->'journal' as journal from manscreen as ms, pubmed as pm
            where decision=true and ms.revid=%(revid)s login!='init' and pm.pmid=ms.pmid;""",
            db.connection(), params={"revid": revid})
    return included_studies_df


def get_review_status_text(db, revid: str) -> list:
    live_update_studies = pd.read_sql("""select pm.pmid, pm.year, pm.ti, pm.ab, pm.pm_data->'authors' as authors,
            pm.pm_data->'journal' as journal, pa.num_randomized, pa.prob_low_rob, pa.effect, decision from manscreen as ms, pubmed as pm,
            pubmed_annotations as pa where in_live_update=true and ms.revid=%(revid)s and pm.pmid=ms.pmid and pm.pmid=pa.pmid;""",
            db.connection(), params={"revid": revid})
    cites = [get_cite(r.authors, r.journal, r.year) for (i, r) in live_update_studies.iterrows()]
    live_update_studies.drop("authors", axis=1, inplace=True)
    live_update_studies['citation'] = cites

    num_studies_total = live_update_studies.shape[0]

    if num_studies_total == 0:
        return ("Trialstreamer is monitoring PubMed live for any new potentially relevant studies."
                "So far no relevant studies have been identified")
    num_studies_to_screen = live_update_studies.decision.isna().sum()
    num_studies_screened = num_studies_total - num_studies_to_screen

    if num_studies_screened == 0:
        return (f"Since the review was published, Trialstreamer has identified {num_studies_total} new studies"
                " which appear eligible to include. These studies are awaiting manual review")

    studies_to_include = live_update_studies[live_update_studies.decision==True]
    num_studies_to_include = studies_to_include.shape[0]

    if num_studies_to_include == 0:
        return (f"Since the review was published, Trialstreamer has identified {num_studies_total} new studies which appeared"
                "  eligible to include. These studies have been reviewed by the review authors, and none meet the inclusion criteria.")


    template = (f"Since the review was published, Trialstreamer has identified {num_studies_total} new studies which appear"
                f" eligible to include. {num_studies_to_screen} are waiting to be screened by the review authors. {num_studies_screened}"
                f" have been manually reviewed, and {num_studies_to_include} of these were judged relevant and are due to be included. ")
    

    num_studies_with_ss = (~studies_to_include.num_randomized.isna()).sum()
    if num_studies_with_ss == 0:
        template += " We couldn't automatically extract the sample size."
    else:
        ss_total = studies_to_include.num_randomized.dropna().sum()
        template += f" We were able to extract the sample size from {num_studies_with_ss} studies, which included a total of {int(ss_total):,} participants."

    return template


def get_cite(authors, journal, year) -> str:
    if len(authors) >= 1 and authors[0]['LastName']:
        return f"{authors[0]['LastName']}{' et al.' if len(authors) > 1 else ''}, {journal}. {year}"
    else:
        return f"{journal}. {year}"

def sumbit_decision_to_db(db: Session, userid, revid, pmid, decision):
    # update the last updated date    


    db.connection().execute("""UPDATE manscreen SET decision = %(decision)s, login = %(userid)s 
                        FROM permissions WHERE manscreen.revid=%(revid)s AND manscreen.pmid=%(pmid)s AND
                        permissions.login = %(userid)s AND permissions.revid=manscreen.revid;""",
                        ({"revid":revid, "pmid": pmid,"decision": decision, "userid": userid}))
    db.commit()
    