#
#   covid review updating code
#


# this can be minimally tweaked, and TODO to make it general purpose update.py

import pandas as pd
import numpy as np
import requests
import json
import datetime
from .database import engine


def get_baseline_meta() -> dict:
    return {"last_updated": pd.read_sql("select * from revmeta where revid='covax';", engine).last_updated[0],
            "done_manual": set(pd.read_sql("select pmid from manscreen where revid='covax';", engine).pmid.values),
            "done_auto": set(pd.read_sql("select pmid from autoscreen where revid='covax';", engine).pmid.values)}

# this can be adapted to any topic filter kewword list
covid_filter = ["2019 ncov",
            "ncov sars2",
            "covid 19",
            "covid19",
            "covid",
            "coronavirus disease 2019",
            "coronavirus disease 19",            
            "2019 ncov disease",
            "2019 novel coronavirus disease",
            "2019 novel coronavirus infection",            
            "2019 ncov infection"
            "covid 2019",
            "coronavirus",
            "novel coronavirus",
            "wuhan coronavirus",
            "wuhan flu",
            "wuhan pneumonia",
            "wuhan virus",
            "2019 novel coronavirus",
            "sars cov 2",
            "severe acute respiratory syndrome coronavirus 2",
            "ncov"]

def is_covid(text) -> bool:
    return any((syn in text.lower() for syn in covid_filter))


def get_new_rcts(last_updated):
    # get all RCTs since the last classification date
    sql = f"""SELECT pmid, ti, ab FROM pubmed WHERE is_rct_balanced=true and
              update_date>='{last_updated.strftime('%Y-%m-%d')}'::date and year>=2020;"""
    updates = pd.read_sql(sql, engine)
    return updates

def filter_topic(df) -> pd.DataFrame:
    return df[(df.ti + ' ' + df.ab).apply(is_covid)]

def filter_new(df, done_manual, done_auto) -> pd.DataFrame:
    return df[df['pmid'].apply(lambda x: (x not in done_manual) and (x not in done_auto))]

def get_api_json(df) -> list:
    return [{"ti": r.ti, "abs": r.ab} for (i, r) in df.iterrows()]

def fetch_preds(articles_list) -> list:
    base_url="http://127.0.0.1:5000/"
    headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
    predictions = requests.post(base_url+'predict/vaccine_model', json=json.dumps({"input_citations": articles_list}), headers=headers)
    return predictions.json()


def update_autoscreen_table(df):
    df.to_sql('autoscreen', engine, if_exists='append', index=False)


def update_manscreen_table(df):
    df.to_sql('manscreen', engine, if_exists='append', index=False)


def update_last_updated():
    engine.execute("UPDATE revmeta SET last_updated = (%s) WHERE revid = 'covax'", (datetime.date.today(),))

def main():
    # *** main loop ***
    
    meta = get_baseline_meta()
    updates = get_new_rcts(meta['last_updated'])
    if updates.shape[0] == 0:
        print("no new trials - exiting")
        quit()
    updates_filtered = filter_new(filter_topic(updates), meta['done_manual'], meta['done_auto'])
    articles_list = get_api_json(updates_filtered)
    preds = fetch_preds(articles_list)
    # set up table for saving in DB

    updates_filtered.drop(['ti', 'ab'], axis=1, inplace=True)
    updates_filtered['revid'] = 'covax' 
    updates_filtered['score'] = preds['predictions']
    updates_filtered['decision'] = updates_filtered['score'] >= 0.5    
    update_autoscreen_table(updates_filtered)

    man = updates_filtered[updates_filtered.decision==True].drop(['decision', 'score'], axis=1)
    man['decision'] = None
    man['login'] = None
    man['in_live_update'] = True # by default new studies are included up until they are incorporated in the review
    update_manscreen_table(man)
    update_last_updated()


if __name__ == '__main__':
    main()


