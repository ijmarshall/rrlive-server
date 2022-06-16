import app
from typing import List, Optional
import pandas as pd
from sqlalchemy.orm import Session


from .schemas import GithubUser, LiveSummarySections
from .models import User, RevMeta, LiveSummarySection, InitScreenRecord, Permission
from .helpers import generate_rev_id, get_api_input_format

import os
import pickle
import csv

# For Loading autocompleter data
print("loading autocompleter")
with open(os.path.join(app.DATA_ROOT, 'pico_cui_autocompleter.pck'), 'rb') as f:
    pico_trie = pickle.load(f)
print("done loading autocompleter")


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

def update_user(db: Session, user_id: int, new_user_info: User) -> User:
    user_from_db = db.query(User).filter_by(id=user_id).first()
    user_from_db.name = new_user_info.name
    user_from_db.email = new_user_info.email
    db.commit()
    db.refresh(user_from_db)
    return user_from_db

def get_reviewlist_from_db(engine, user_id: str) -> list:
    reviewmeta = pd.read_sql("select revmeta.revid, revmeta.title, revmeta.last_updated from revmeta, permissions where permissions.login=%(user_id)s and revmeta.revid=permissions.revid ORDER BY permissions.revid;",
                             engine,
                             params = {"user_id": user_id})
    revids = tuple(r.revid for (i, r) in reviewmeta.iterrows())

    # Including the number of abstracts for each review for the dashboard

    if len(revids) > 1:
        query = f"""
        select (select count(pm.pmid) from manscreen as ms, pubmed as pm, pubmed_annotations as pa, permissions p
        where permissions.revid=p.revid and p.login='{user_id}' and decision is null
        and pm.pmid=ms.pmid and pm.pmid=pa.pmid and permissions.revid=ms.revid) as num_abstracts_to_screen
        from permissions
        where permissions.revid IN {revids}
        group by permissions.revid order by permissions.revid;
        """
    else:
        query = f"""
        select (select count(pm.pmid) from manscreen as ms, pubmed as pm, pubmed_annotations as pa, permissions p
        where permissions.revid=p.revid and p.login='{user_id}' and decision is null
        and pm.pmid=ms.pmid and pm.pmid=pa.pmid and permissions.revid=ms.revid) as num_abstracts_to_screen
        from permissions
        where permissions.revid='{revids[0]}'
        group by permissions.revid order by permissions.revid;
        """
    num_abstracts_to_screen = pd.read_sql_query(query, engine)
    reviewmeta['num_abstracts_to_screen'] = num_abstracts_to_screen

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


def generate_summary_of_new_evidence(db, revid: str) -> str: 
    
    import requests
    import json
    import time

    live_update_studies = pd.read_sql("""select pm.pmid, pm.year, pm.ti, pm.ab, pm.pm_data->'authors' as authors,
            pm.pm_data->'journal' as journal, pa.num_randomized, pa.prob_low_rob, pa.effect, decision from manscreen as ms, pubmed as pm,
            pubmed_annotations as pa where in_live_update=true and pm.pmid=ms.pmid and pm.pmid=pa.pmid;""",
            db.connection(), params={"revid": revid})

    
    articles = []

    for (idx, citation) in live_update_studies.iterrows():
        articles.append({"ti": citation.ti, "abs": citation.ab})

   
    headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
    base_url="http://127.0.0.1:5000/"
    #import pdb; pdb.set_trace()
    summary = requests.post(base_url+'summarize', json=json.dumps({"articles":articles}), headers=headers)
    return summary.text



def get_cite(authors, journal, year) -> str:
    if len(authors) >= 1 and authors[0]['LastName']:
        return f"{authors[0]['LastName']}{' et al.' if len(authors) > 1 else ''}, {journal}. {year}"
    else:
        return f"{journal}. {year}"

def sumbit_decision_to_db(db: Session, userid, revid, pmid, decision):
    # update the last updated date    
    try:

        db.connection().execute("""UPDATE manscreen SET decision = %(decision)s, login = %(userid)s 
                            FROM permissions WHERE manscreen.revid=%(revid)s AND manscreen.pmid=%(pmid)s AND
                            permissions.login = %(userid)s AND permissions.revid=manscreen.revid;""",
                            ({"revid":revid, "pmid": pmid,"decision": decision, "userid": userid}))
        if decision:
            db.connection().execute("""UPDATE revmeta SET summary_update_needed = %(decision)s
                                WHERE revmeta.revid=%(revid)s;""",
                            ({"revid":revid, "decision": decision}))
        db.commit()
    except:
        db.rollback()
        raise

def autocomplete(q):
    """
    retrieves most likely MeSH PICO terms from data in pico_cui_autocompleter.pck
    """

    min_char = 3
    max_return = 5
    substr = q
    if substr is None or not pico_trie.has_subtrie(substr):
        return []

    matches = pico_trie.itervalues(prefix=substr)

    def flat_list(l):
        return [item for sublist in l for item in sublist]

    def dedupe(l):
        encountered = set()
        out = []
        for r in l:
            if r['cui_pico_display'] not in encountered:
                encountered.add(r['cui_pico_display'])
                out.append(r)
        return out

    if len(substr) < min_char:
        # for short ones just return first 5
        return dedupe(flat_list([r for _, r in zip(range(max_return), matches)]))
    else:
        # where we have enough chars, process and get top ranked
        return sorted(dedupe(flat_list(matches)), key=lambda x: x['count'], reverse=True)[:max_return]

def get_live_summary_from_db(db, revid: str) -> List[LiveSummarySection]:
    return db.query(LiveSummarySection).filter_by(revid=revid).all()

def submit_live_summary_to_db(db: Session, title: str, date: str, keyword_filter: str, live_summary_sections: LiveSummarySections, csv_path: str, user_login: str):
    try:

        # Insert to DB table revmeta
        review_id = generate_rev_id(title)
        # Add time of default of all zeros
        last_updated_date = date + " 00:00:00"

        revmeta = RevMeta(
            revid=review_id,
            title=title,
            last_updated=last_updated_date,
            keyword_filter=keyword_filter,
        )
        db.add(revmeta)
        

        # Insert to DB table live_abstracts
        sections = [
            LiveSummarySection(section="background", text=live_summary_sections.background, revid=review_id),
            LiveSummarySection(section="methods", text=live_summary_sections.methods, revid=review_id),
            LiveSummarySection(section="results", text=live_summary_sections.results, revid=review_id),
            LiveSummarySection(section="conclusion", text=live_summary_sections.conclusion, revid=review_id),
            LiveSummarySection(section="automated_narrative_summary", text=None, revid=review_id),
        ]
        db.bulk_save_objects(sections)

        # Insert to DB table init_screen
        screen_records = []
        # Read from saved csv and save to DB table init_screen
        with open(csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # should populate into list of models/schemas so we can save to db
                # add to list of MODEL
                record = InitScreenRecord(
                    revid=review_id,
                    pmid=row['pmid'],
                    ti=row['ti'],
                    ab=row['ab'],
                    decision=row['decision']
                )
                screen_records.append(record)
        db.bulk_save_objects(screen_records)

        # Insert into DB table permissions
        permission = Permission(login=user_login, revid=review_id)
        db.add(permission)

        db.commit()
        db.refresh(revmeta)
        db.refresh(permission)
    except:
        db.rollback()
        raise

def get_updated_summary(engine, revid) -> str:
    """Get the updated summary from one edit at a time model - only one edit per call"""
    import requests
    try:
        # get original summary title
        original_summary_title = engine.execute("SELECT title FROM revmeta WHERE revid = (%s);", (revid,)).fetchone()[0]

        # get original summary
        original_summary = engine.execute("SELECT text FROM live_abstracts WHERE revid=(%s) and section='conclusion';", (revid,)).fetchone()[0]
        
        # get articles
        articles = engine.execute(f"SELECT pm.ti, pm.ab FROM pubmed AS pm, manscreen AS ms WHERE ms.revid='{revid}' AND ms.decision=true AND pm.pmid=ms.pmid;").fetchall()
        
        # format for API input
        input_data = get_api_input_format(original_summary_title, original_summary, articles) 

        # call the API   
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        update_summarization_url="http://127.0.0.1:8081/update_summary_from_diff"
        response = requests.post(update_summarization_url, json=input_data, headers=headers)
        response_json = response.json()
        print(response_json)

        # update automated narrative
        engine.execute(f"UPDATE live_abstracts SET text = '{response_json['updated_summary']}' WHERE revid = '{revid}' AND section='automated_narrative_summary'")
        return response_json['updated_summary']
    except:
        raise

def update_live_summary_conclusion(db: Session, revid, conclusion):
    # update the conclusion for given revid
    try:
        db.connection().execute("""UPDATE live_abstracts SET text = %(conclusion)s
                            live_abstracts.section = 'conclusion' AND live_abstracts.revid = %(revid)s;""",
                            ({"revid":revid, "conclusion": conclusion}))
        db.commit()
    except:
        db.rollback()
        raise