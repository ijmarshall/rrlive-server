#
# Update Summarization for each review
#

import pandas as pd
import requests
import json
import os
import urllib.parse

from typing import Generator
from .database import engine

update_summarization_url="http://127.0.0.1:8081/update_summary"
update_summarization_from_diff_url="http://127.0.0.1:8081/update_summary_from_diff"
update_diff_url="http://127.0.0.1:8081/update_diff"

def get_api_input_format(original_summary, articles_list):
    # Currently don't have original summary title so will just pass empty string
    return {
        "existing_summary_title": "",
        "existing_summary": original_summary,
        "articles": articles_list
    }

def fetch_updated_summary(input_data):
    headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
    response = requests.post(update_summarization_url, json=input_data, headers=headers)
    return response.json()

####### UPDATES #########

def update_automated_narrative(text, revid):
    engine.execute(f"UPDATE live_abstracts SET text = '{text}' WHERE revid = '{revid}' AND section='automated_narrative_summary'")

def update_summary_update_needed(revid):
    engine.execute(f"UPDATE revmeta SET summary_update_needed = false WHERE revid = '{revid}'")
    
def main():
    # MAIN LOOP
    revids_to_update_ = engine.execute("select revid, title, last_updated, summary_update_needed from revmeta where coalesce(summary_update_needed, FALSE) = TRUE;").fetchall()
    revids_to_update = [i.revid for i in revids_to_update_]

    for revid in revids_to_update:
        
        print(f"Starting update summarization of the {revid} review")
        original_summary = engine.execute("SELECT text FROM live_abstracts WHERE revid=(%s) and section='conclusion';", (revid,)).fetchone()[0]
        
        print(f"Fetching manually labelled studies from screener {revid} ")
        articles = engine.execute(f"SELECT pm.ti, pm.ab FROM pubmed AS pm, manscreen AS ms WHERE ms.revid='{revid}' AND ms.decision=true AND pm.pmid=ms.pmid;").fetchall()
        print(revid)

        article_list = []

        print(f"Preparing data for Update Summarization API format {revid} ")

        for art in articles:
            row = {
                    'title': art.ti,
                    'abstract': art.ab,
                  }
            article_list.append(row)
        
        # call the update summarization API
        print(f"Preparing data for Update Summarization API {revid} ")
        input_data = get_api_input_format(original_summary, article_list)
        print(f"Getting updated summarization with API (will take a while) {revid} ")        
        response = fetch_updated_summary(input_data)
        
        # for debug
        print(f"Print updated summary output {revid} ")   
        print(response)
        
        print(f"Saving all the relevant data back in the database {revid} ")        
        
        print("Updating automated_narrative_summary...") 
        update_automated_narrative(response["updated_summary"], revid)
        print("Updating revmeta summary_update_needed...")  
        update_summary_update_needed(revid)
        print(f"FINISHED - ALL COMPLETE :) {revid} ")

if __name__ == '__main__':
    main()