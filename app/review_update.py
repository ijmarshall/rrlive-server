
#
#   covid review updating code
#


#
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, date
import re
import sys
from typing import Counter
import pickle
# from mailjet_rest import Client
import os
import app
from typing import Generator
from .database import engine

screener_url = 'http://screen.robotreviewer.net/'

# function zoo
# Read pickle data
#with open('strlist_from_cui.pck', 'rb') as f:  # for franks file
with open(os.path.join(app._ROOT, 'strlist_from_cui.pck'), 'rb' ) as f:
    # with open('../trialstreamer/strlist_from_cui.pck', 'rb') as f:
    strlist_from_cui = pickle.load(f)

# old is_covid filter


def is_covid(text) -> bool:
    return any((syn in str(text).lower() for syn in fixed_covid_filter))

# old is_covid filter


def filter_topic_covid(df) -> pd.DataFrame:
    return df[(df.ti + ' ' + df.ab).apply(is_covid)]


def is_cui(text, strlists):
    return all((any((syn in text.lower() for syn in strlist)) for strlist in strlists))


def filter_topic_all(df) -> pd.DataFrame:
    return df[(df.ti + ' ' + df.ab).apply(is_important)]


def filter_topic_all_cui(df, keyword_filter) -> pd.DataFrame:
    cuis = [json.loads(i)['cui'] for i in keyword_filter]
    strlists = [strlist_from_cui[c] for c in cuis]
    return df[(df.ti + ' ' + df.ab).apply(lambda x: is_cui(x, strlists))]


def get_new_rcts(last_updated):
    # get all RCTs since the last classification date
    sql = f"""SELECT pmid, ti, ab FROM pubmed WHERE is_rct_balanced=true and
              update_date>='{last_updated.strftime('%Y-%m-%d')}'::date;"""
    updates = pd.read_sql(sql, engine)
    return updates


def filter_new(df, done_manual, done_auto) -> pd.DataFrame:
    return df[df['pmid'].apply(lambda x: (x not in done_manual) and (x not in done_auto))]


def get_api_json(df) -> list:
    return [{"ti": r.ti, "abs": r.ab} for (i, r) in df.iterrows()]


def fetch_preds(articles_list, revid) -> list:
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    predictions = requests.post(f'{screener_url}predict/{revid}', json=json.dumps(
        {"input_citations": articles_list}), headers=headers)
    return predictions.json()

####### UPDATES #########


def update_autoscreen_table(df):
    df.to_sql('autoscreen', engine, if_exists='append', index=False)


def update_manscreen_table(df):
    df.to_sql('manscreen', engine, if_exists='append', index=False)


def update_last_updated(revid):
    engine.execute(
        f"UPDATE revmeta SET last_updated = (%s) WHERE revid = '{revid}'", (date.today(),))


def update_is_trained(revid):
    engine.execute(
        f"UPDATE revmeta SET is_trained = 1 WHERE revid = '{revid}'")


def update_last_updated_all():
    engine.execute("UPDATE revmeta SET last_updated = (%s) ",
                   (datetime.date.today(),))

# updated way to get the data from the tables in the same way


def get_base_data(revid) -> dict:
    revmeta_query = engine.execute(
        "select last_updated, is_trained, keyword_filter, summary_update_needed from revmeta where revid=(%s);", (revid,)).fetchone()
    last_updated = revmeta_query.last_updated

    keyword_filter = engine.execute(
        "select keyword_filter from revmeta where revid=(%s);", (revid,)).fetchall()
    keyword_filter = [i[0]
                      for i in keyword_filter]  # convert tuple to values <-

    # initscreen — published (i.e. old) systematic review screening decisions uploaded by the authors
    # autoscreen — model predicted possibly relevant new studies for the living review
    # manscreen — manual validated studies (i.e. bow autoscreen studies which have gone on for
    # .             further review, and been assessed as relevant)

    done_manual = engine.execute(
        "select pmid from manscreen where revid=(%s);", (revid,)).fetchall()
    done_manual = [i[0] for i in done_manual]  # convert tuple to values

    done_auto = engine.execute(
        "select pmid from autoscreen where revid=(%s);", (revid,)).fetchall()
    done_auto = [i[0] for i in done_auto]  # convert tuple to values

    # same way to retrieve the data as before
    return {"last_updated": last_updated,
            "keyword_filter": revmeta_query.keyword_filter,
            "revid": revid,
            "is_trained": revmeta_query.is_trained,
            "done_manual": done_manual,
            "done_auto": done_auto
            }


def main():
    # *** main loop ***

    # this works the second screener.robotreviewer.net needs some tweaking
    # tmp testing url screener_url = "http://summarization.robotreviewer.net:7777/"
    #screener_url = 'screen.robotreviewer.net'
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    print("test-keyboarddd malfucntioon")
    revids_to_update_ = engine.execute(
        "select revid from revmeta where not revid='covax' ;").fetchall()
    revids_to_update = [i.revid for i in revids_to_update_]

    for revid in revids_to_update:

        # get baseline data

        print(f"Starting update of the {revid} review")
        base_data = get_base_data(revid)

        if not base_data['is_trained']:
            print(
                f"No model has been trained — we will train now for {revid} ")

            # then train a model using the articles in 'done_manual' before moving on

            print(
                f"Fetching manually labelled studies from publication version {revid} ")
            articles = engine.execute(
                f"SELECT * FROM init_screen where revid = '{revid}'").fetchall()
            print(revid)

            data = []

            print(f"Preparing data for RoboScreener format {revid} ")

            for art in articles:

                tmp = "1" if art.decision == "Include" else "0"

                row = {
                    'ti': art.ti,
                    'abs': art.ab,  # need to name it 'abs' as this is the way the screener eats it
                    'label': tmp  # decision # decisions -> 1=include, 0=exclude
                }
                data.append(row)

                # as test saved the payload as csv
                #pd.DataFrame(data).to_csv("CHECK_data.csv", index=False)
            # send to robotscreener for training

            # train the model
            print(
                f"Sending request for model training (this will take a while...) {revid} ")
            requests.post(
                screener_url + f"train/{revid}", json=json.dumps({"labeled_data": data}), headers=headers)
            # model is trained :) probably
        else:
            print(f"Model already trained, will use that one {revid} ")

        # use trained model to predict relevance of new articles

        # get all new rcts since the lat update
        print(
            f"Fetching all new RCTs from Trialstreamer since last update {revid} ")
        updates = get_new_rcts(base_data['last_updated'])
        if updates.shape[0] == 0:
            print("no new trials - exiting this review")
            continue

        # update to CUIs

        print(f"Checking which match our cuis for {revid} ")
        articles_cui_matching = filter_topic_all_cui(
            updates, base_data['keyword_filter'])
        print(
            f"Making sure they've not already been screened manually (in the publication) {revid} ")
        updates_filtered = filter_new(
            articles_cui_matching, base_data['done_manual'], base_data['done_auto'])

        # call the screener model
        print(f"Preparing data for RoboScreener {revid} ")
        articles_list = get_api_json(updates_filtered)
        print(
            f"Predicting relevance with RoboScreener (will take a while) {revid} ")
        preds = fetch_preds(articles_list, revid)

        # 1 for debug
        print(f"Saving pure predictions to a csv {revid} ")
        pd.DataFrame(preds).to_csv("pure_predictions.csv", index=False)

        print(f"Saving all the relevant data back in the database {revid} ")
        # set up table for saving in DB
        updates_filtered.drop(['ti', 'ab'], axis=1, inplace=True)
        print("Updates filtered...")
        updates_filtered['revid'] = revid
        updates_filtered['score'] = preds['predictions']
        updates_filtered['decision'] = updates_filtered['score'] >= 0.5

        # 2 for debug
        print(f"Saving filtered predictions to a csv {revid} ")
        pd.DataFrame(updates_filtered).to_csv(
            "filtered_predictions.csv", index=False)
        print("Writing debug testing files complete!")
        print("Updating autoscreen...")
        update_autoscreen_table(updates_filtered)

        man = updates_filtered[updates_filtered.decision == True].drop(
            ['decision', 'score'], axis=1)
        man['revid'] = revid
        man['decision'] = None
        man['login'] = None
        # by default new studies are included up until they are incorporated in the review
        man['in_live_update'] = True

        print("Updating manscreen...")
        update_manscreen_table(man)
        print("Updating last_updated...")
        update_last_updated(revid)
        update_is_trained(revid)
        print(f"FINISHED - ALL COMPLETE :) {revid} ")


if __name__ == '__main__':
    main()
