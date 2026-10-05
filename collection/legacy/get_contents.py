
import json
import argparse
import sql_manager
from collections import defaultdict

def is_phishing(ad):
    """ 
    simple heuristic aimed at getting all ads whose caption
    is different from the actual linked address and contains
    a dot, indicating URL-formatting. This is used to either
    offer an approxiamtion of the total phishing links on a db
    or to return all ads in this pattern to externally do further
    cleaning to select the actual phising ads.

    standard library solutions like urllib parse/split do not
    work for double suffix TLDs (such as 'meusite.bet.br')
    """
    try:
        ad_caption = ad["caption"].replace("www.","").replace("...","")
        ad_link_url = ad["link_url"].replace("www.","")
        if not "." in ad_caption:
            return 0
        if ad_link_url in ad_caption or ad_caption in ad_link_url:
            return 0
        return ad
    except:
        return 0

def query_db_phishing(db):
    phishing_ads = defaultdict(list)
    normal_ads = defaultdict(list)
    total = 0

    query = f"SELECT metadata FROM advert"
    result = db.connection.execute(query)
    content = result.fetchone()
    
    while content:
        data = json.loads(content[0])
        pk_advertiser = data.get("page_id")
        pk_ad_id = data.get("ad_archive_id")
        page_name = data.get("page_name")

        snapshot = data.get("snapshot")
        media_type = snapshot.get("display_format")
        profile_page = snapshot.get("page_profile_uri")
        if media_type == "error":
            content = result.fetchone()
            continue
        
        formatted_response = {
            "Page Name": page_name,
            "Page URL": profile_page,
            "AdLib ID": pk_ad_id,
            "True Link":snapshot.get("link_url"),
            "Fake Link":snapshot.get("caption")
            }
        
        cards = snapshot.get('cards')
        if not cards:
            # cards represent multiple versions of the same ad, each with potentailly
            # different media. Each version can be treated the same way as a singular ad,
            # which is done here to avoid writing redundant code.
            cards = [snapshot]
        
        for card in cards:
            card_link = card.get("link_url")
            card_caption = card.get("caption")
            instance = {"link_url": card_link, "caption": card_caption}
            if is_phishing(instance):
                total+=1
                formatted_response["True Link"] = card_link
                formatted_response["Fake Link"] = card_caption
                phishing_ads[pk_advertiser]=(formatted_response)
                continue
            normal_ads[pk_advertiser]=(formatted_response)

        content = result.fetchone()
    return {"total": total, "ads": phishing_ads}

def query_db_all_links(db):
    links_by_advertiser = defaultdict(dict)
    total = 0

    query = f"SELECT metadata FROM advert"
    result = db.connection.execute(query)
    content = result.fetchone()
    
    while content:
        data = json.loads(content[0])
        pk_advertiser = data.get("page_id")
        pk_ad_id = data.get("ad_archive_id")
        page_name = data.get("page_name")

        snapshot = data.get("snapshot")
        media_type = snapshot.get("display_format")
        profile_page = snapshot.get("page_profile_uri")
        if media_type == "error":
            content = result.fetchone()
            continue
        
        cards = snapshot.get('cards')
        cards_content = []
        if not cards:
            # cards represent multiple versions of the same ad, each with potentailly
            # different media. Each version can be treated the same way as a singular ad,
            # which is done here to avoid writing redundant code.
            cards = [snapshot]
        
        for card in cards:
            card_link = card.get("link_url")
            if not card_link:
                continue
            card_caption = card.get("caption")
            formatted_response = {
                "True Link":card_link,
                "Link Mask":card_caption,
            }
            if formatted_response not in cards_content:
                total+=1
                cards_content.append(formatted_response)
        
        if cards_content:
            links_by_advertiser[pk_advertiser]["info"] = {"page": page_name, "link": profile_page}
            links_by_advertiser[pk_advertiser][pk_ad_id] = cards_content

        content = result.fetchone()
    return {"total": total, "ads": links_by_advertiser}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db", "--database", type=str, default="adbank", help="Name of .db file to store the colletion. Deault is 'adbank'.")
    parser.add_argument("-phishing", default=False, action="store_true", help="Return possible phishing ads.")
    parser.add_argument("-links", default=False, action="store_true", help="Return all links and advertisers using them.")
    args = parser.parse_args()

    db = sql_manager.Manager(args.database)
    if args.phishing:
        phishing_ads = query_db_phishing(db)
        print(json.dumps(phishing_ads["ads"], ensure_ascii=False, indent=2))
        print("Total de anunciantes com potencial phishing: ", len(phishing_ads["ads"]))
        print("Total de anúncios com potencial phishing: ", phishing_ads["total"])
    
    if args.links:
        links = query_db_all_links(db)
        print(json.dumps(links, indent=2, ensure_ascii=False))
