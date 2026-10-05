
import json
import time
import logging
import requests
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import sql_manager

MINIMUM_DOC_SIZE = 2 # Kb
STD_HEADER_PATH = Path("data/request-templates/std-headers.json")
STD_BODY_PATH = Path("data/request-templates/std-body.json")
STD_VARS_PATH = Path("data/request-templates/std-variables.json")
REL_VARS_PATH = Path("data/request-templates/relevancy-variables.json")
IMP_VARS_PATH = Path("data/request-templates/impressions-variables.json")

PDT_HEADER_PATH = Path("data/request-templates/page-detail-headers.json")
PDT_BODY_PATH = Path("data/request-templates/page-detail-body.json")
PDT_VARS_PATH = Path("data/request-templates/page-detail-variables.json")

start_time = datetime.today()
logs_dir = Path(f'data/logs/{start_time.year}-{start_time.month}')
if not logs_dir.is_dir():
    logs_dir.mkdir()

supported_media_displays = {
    "TEXT":None,
    "IMAGE":"single",
    "VIDEO":"single",
    "EVENT":"single",
    "PAGE_LIKE":"single",
    "DCO": "cards",
    "DPA": "cards",
    "CAROUSEL": "cards",
    "MULTI_IMAGES": "multi",
    "MULTI_VIDEOS": "multi",
    "MULTI_MEDIAS": "multi",
    None:"error"
}

def load_json(path, override: dict = {}):
    with open(path, "r") as file:
        content = json.load(file)
        for key in override:
            if key in content:
                content[key] = override[key]
            else:
                logging.warning(f"[Template Load WARNING load_json() override key not found]> {key}")
        return content

def get_author_info(page_id, author_ad_id):
    url = "https://www.facebook.com/api/graphql/"
    variables = load_json(PDT_VARS_PATH, override={
        "deeplinkAdID":author_ad_id,
        "viewAllPageID": page_id
    })
    payload = load_json(PDT_BODY_PATH, override={"variables": json.dumps(variables)})
    headers = load_json(STD_HEADER_PATH)
    response = requests.request("POST", url, headers=headers, data=payload)
    try:
        content = json.loads(response.text.split("\n")[1]).get("data")
        author_info = {
            "ad_library_page_info": content.get("ad_library_page_info"),
            "page": content.get("page")
        }
        return json.dumps(author_info, indent=1)
    except:
        logging.error("[AdLibrary ERROR get_author_info()]> Rate Limited.")
        return {}

def search_ad_library(
        query = "*",
        state = "ACTIVE",
        lang = ["pt"],
        collation_token = "22d1696fb7-acid-4519-b55d-a1d913b2b2ca",
        cursor = "",
        advertisers = [],
        procedure = STD_VARS_PATH,
        countries = ["BR"]
    ):
    
    url = "https://www.facebook.com/api/graphql/"
    sid = "320fcatf-7c16-4319-9dt2-299s3113af95"
    variables = load_json(procedure, override={
        "activeStatus": state,
        "queryString": query,
        "collationToken": collation_token,
        "contentLanguages": lang,
        "countries": countries,
        "sessionID": sid,
        "pageIDs":advertisers,
        "cursor": cursor
        }
    )
    
    # overrides the templates variables
    payload = load_json(STD_BODY_PATH, override={"variables": json.dumps(variables)})
    headers = load_json(STD_HEADER_PATH)
    
    if not db.keyword_exists(variables['queryString']):
        db.insert_keyword_and_cursors(variables['queryString'])
    
    response = requests.request("POST", url, headers=headers, data=payload)
    next_cursor = {"next_cursor":{"end_cursor":cursor, "has_next_page": False}}
    total_ads = 0
    new_ads = 0
    rsize = len(response.content)/1000
    print(f"\t+ Got {rsize:.2f} Kb.")
    if rsize < MINIMUM_DOC_SIZE:
        # might indicate rate limiting
        logging.warning(f"[AdLibrary WARNING 'Empty Response']> {response.json()}")
        return {"has_errors": 1,"collection_totals":(total_ads, new_ads),"next_cursor":next_cursor}

    response_json = response.json()
    next_cursor = response_json.get("data").get("ad_library_main").get("search_results_connection").get("page_info")
    edges = response_json.get("data").get("ad_library_main").get("search_results_connection").get("edges")
    for edge in edges:
        total_ads+=1
        found_new = False
        content = edge.get("node").get("collated_results")
        for collation in content:
            pk_advertiser = collation.get("page_id")
            pk_ad_id = collation.get("ad_archive_id")
            page_name = collation.get("page_name")
            snapshot = collation.get("snapshot")
            media_type = snapshot.get("display_format")
            cards = snapshot.get('cards')
            
            if not db.advert_exists(pk_ad_id, pk_advertiser):
                found_new = True
                if not db.advertiser_exists(pk_advertiser):
                    advertiser_metadata = {}
                    if args.owner_metadata:
                        advertiser_metadata = get_author_info(pk_advertiser, pk_ad_id)
                    db.insert_advertiser(pk_advertiser, page_name, advertiser_metadata)
                match supported_media_displays[media_type]:
                    case None:
                        db.insert_advert(pk_advertiser, collation, query)
                    
                    case "single":
                        urls = snapshot.get('videos'), snapshot.get('images')
                        displays = ['video_sd_url', 'original_image_url', 'video_hd_url']
                        medias = []
                        hashes = {}
                        for display,url in enumerate(urls):
                                if not url:
                                    continue
                                media_url = url[0].get(displays[display])
                                if not media_url:
                                    continue
                                media_name = media_url.split("?")[0].split("/")[-1]
                                media_hash =  db.media_url_exists_return_hash(media_name)
                                if not media_hash:
                                    media_bytes = download_bytestream(media_url)
                                    if not media_bytes:
                                        continue
                                    media_hash = db.insert_media_return_hash(media_name, media_bytes)
                                medias.append(media_name)
                                hashes[media_name] = media_hash
                                break

                        db.insert_advert(pk_advertiser, collation, query, medias, hashes)

                    case "multi":
                        video_urls = [urls["video_sd_url"] for urls in snapshot.get('videos')]
                        image_urls = [urls["original_image_url"] for urls in snapshot.get('images')]
                        medias = []
                        hashes = {}
                        for url in video_urls:
                            media_name = url.split("?")[0].split("/")[-1]
                            media_hash = db.media_url_exists_return_hash(media_name)
                            if not media_hash:
                                media_bytes = download_bytestream(url)
                                if not media_bytes:
                                    continue
                                media_hash = db.insert_media_return_hash(media_name, media_bytes)
                            medias.append(media_name)
                            hashes[media_name] = media_hash
                        
                        for url in image_urls:
                            media_name = url.split("?")[0].split("/")[-1]
                            media_hash = db.media_url_exists_return_hash(media_name)
                            if not media_hash:
                                media_bytes = download_bytestream(url)
                                if not media_bytes:
                                    continue
                                media_hash = db.insert_media_return_hash(media_name, media_bytes)
                            medias.append(media_name)
                            hashes[media_name] = media_hash
                        db.insert_advert(pk_advertiser, collation, query, medias, hashes)

                    case "cards":
                        medias = []
                        hashes = {}
                        for card in cards:
                            urls = card.get("video_sd_url"), card.get("original_image_url")
                            for url in urls:
                                if not url:
                                    continue
                                media_name = url.split("?")[0].split("/")[-1]
                                media_hash = db.media_url_exists_return_hash(media_name)
                                if not media_hash:
                                    media_bytes = download_bytestream(url)
                                    if not media_bytes:
                                        continue
                                    media_hash = db.insert_media_return_hash(media_name, media_bytes)
                                medias.append(media_name)
                                hashes[media_name] = media_hash
                        db.insert_advert(pk_advertiser, collation, query, medias, hashes)
                    
                    case _:
                        collation["snapshot"]["display_format"] = "error"
                        db.insert_advert(pk_advertiser, collation, query)
                        logging.info(f"[AdLibrary WARNING 'No Display Format']> {media_type} [{supported_media_displays[media_type]}]\n [{snapshot}]")
        new_ads+=found_new

    db.commit_session()    
    if not new_ads:
        time.sleep(1.5)
        
    print(f"\t+ Total Returned Ads: {total_ads} New Ads: {new_ads}")
    if total_ads == 0:
        return {"has_errors": 1,"collection_totals":(total_ads, new_ads),"next_cursor":next_cursor}
    return {"has_errors": 0,"collection_totals":(total_ads, new_ads),"next_cursor":next_cursor}

def download_bytestream(url):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        return response.content
    
    except Exception as e:
        logging.warning(f"[Media Download WARNING 'Failed to download content']> {url}: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db", "--database", type=str, default="adbank",
                        help="Name of .db file to store the collection. Default is 'adbank'.")
    parser.add_argument("-kws", "--keywords", type=str, nargs="+", default=["*"],
                        help="Keywords to search for. Default is a single asterisk, a full search.")
    parser.add_argument("-max", "--maxreqs", type=int, default=0,
                        help="Maximum number of requests. The default 0 means no fixed limit, searching until cursor depletes.")
    parser.add_argument("-insist", type=int,
                        help="Keeps requesting until amount is reached, even if returns are repeated.")
    parser.add_argument("-owners", type=str, nargs="+", default=[],
                        help="Search string for specific advertisers. Receives a list of Page IDs.")
    parser.add_argument("-restart", action="store_true",
                        help="Resets cursor progression.")
    parser.add_argument("-tolerance", type=int, default=5,
                        help="Maximum cumulative error total, to prevent continuing when rate limited.")
    parser.add_argument("-ad_state", default="ACTIVE",
                        help="Collect adverts currently being shown (ACTIVE), not currently shown (INACTIVE) or both (ALL).")
    parser.add_argument("-autostart", action="store_true",
                        help="Skips interactive confirmation of collection parameters.")
    parser.add_argument("-check_owners", action="store_true",
                        help="Check all currently stored advertisers for new adverts.")
    parser.add_argument("-check_keywords", action="store_true",
                        help="Check all currently stored keywords for new adverts.")
    parser.add_argument("-owner_metadata", action="store_true",
                        help="Includes additional metadata for all new advertisers found. This resource gets limited faster than ad searches.")
    parser.add_argument("-locs", "--countries", type=str, nargs="+", default=["BR"],
                        help="Targeted countries. Default is 'BR' (Brazil).")
    parser.add_argument("-langs", type=str, nargs="+", default=["pt"],
                        help="Targeted languages. Default is ['pt'] (Portuguese).")
    args = parser.parse_args()

    logging.basicConfig(
        format="[%(asctime)s: %(levelname)s]> %(message)s",
        style="%",
        datefmt="%Y-%m-%d %H:%M",
        level=logging.INFO,
        filename=f"{logs_dir}/{start_time.strftime('%Y-%m-%d %Hh%Mm%Ss')} [{args.database}.db].log",
    )

    if args.insist and not args.maxreqs:
        args.maxreqs = args.insist

    db = sql_manager.Manager(args.database)

    search_strings = args.keywords
    advertisers = args.owners

    if args.check_keywords:
        stored_kws = db.get_all_kws()
        if stored_kws:
            search_strings = stored_kws
        else:
            logging.info("No stored keywords found despite '-check_keywords' flag. Defaulting to '*'.")

    if args.check_owners:
        stored_advertisers = db.get_all_advertisers()
        if stored_advertisers:
            advertisers = stored_advertisers
        else:
            message = "[Argument ERROR]: No stored advertisers found despite '-check_owners' flag. Returning."
            logging.error(message)
            raise ValueError(message)

    settings = "\n\t\t-".join(
        f"{key}: {value}" for key, value in vars(args).items()
        if key not in ("keywords", "owners")
    )
    logging.info(
        " Starting collection procedure.\n\t[COLLECTION SETTINGS]:"
        f"\n\t\t-search_strings: {search_strings}\n\t\t-advertisers: {advertisers}\n\t\t-{settings}"
    )

    if not args.autostart:
        green, red, reset = "\033[92m", "\033[91m", "\033[0m"
        owners_text = f"{green}{advertisers}" if advertisers else f"{red}Unset"
        maxreqs_text = f"{red}{args.maxreqs or 'Unset'}{reset}"
        insist_text = args.insist if args.insist else f"{red}Unset{reset}"
        input(
            f"Database: {green}data/{args.database}.db{reset}\tKeywords: {green}{search_strings}{reset}\n"
            f"Specific Advertisers: {owners_text}{reset}\t Max Requests: {maxreqs_text}\t"
            f"Insist: {insist_text}\nConfirm Start> "
        )

    iteration = 0
    errors = 0
    # If cursors are restarted, create an empty dict to track and overwrite them.
    current_cursor = defaultdict(dict) if args.restart else db.get_last_cursor_keywords(search_strings)
    session_totals = {"total": 0, "new": 0}

    while search_strings and errors < args.tolerance:
        iteration += 1
        if args.maxreqs and iteration > args.maxreqs:
            logging.info("[FINISH]: Max iterations reached.")
            break

        current_search = search_strings.pop(0)
        print(f"[{iteration}]:  Currently searching '{current_search}'")

        request = dict(
            query=current_search,
            state=args.ad_state,
            advertisers=advertisers,
            procedure=REL_VARS_PATH,
            lang=args.langs,
            countries=args.countries,
        )
        try:
            cursor = current_cursor.get(current_search)
            # If the search has a stored cursor, continue it; otherwise start fresh.
            if cursor:
                result = search_ad_library(**request, cursor=cursor)
            else:
                result = search_ad_library(**request)

            next_cursor = result.get("next_cursor") or {}
            end_cursor = next_cursor.get("end_cursor")
            current_cursor[current_search] = end_cursor

            if cursor:
                db.insert_keyword_and_cursors(current_search, last_cursor=end_cursor)
            else:
                db.insert_keyword_and_cursors(current_search, start_cursor=end_cursor)

            errors += result["has_errors"]
            session_totals["total"] += result["collection_totals"][0]
            session_totals["new"] += result["collection_totals"][1]

            if next_cursor.get("has_next_page") or args.insist:
                search_strings.append(current_search)

        except Exception as e:
            errors+=1
            print("> Got an unexpected error. Check logs for further details.")
            logging.error(f"[Unexpected error {type(e)}]> {e}. Aborting procedure.")
            break

    logging.info(
        f"[COLLECTION REPORT]: {iteration} requests done in {datetime.now() - start_time} total."
        f"\n\t\tTotal ads verified: {session_totals['total']}"
        f"\n\t\tTotal New Adverts: {session_totals['new']}"
        f"\n\t\tNew Media: {dict(db.session_report()[0])}"
    )

    if errors >= args.tolerance:
        logging.error(f"[FINISH]: Error total surpassed tolerance. Errors: {errors} Tolerance: {args.tolerance}")

    if not search_strings:
        logging.info("[FINISH]: All cursors finished.")
