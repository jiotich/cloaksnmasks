import json
import tldextract
from collections import defaultdict

META_URLS = ["whatsapp.com", "instagram.com", "facebook.com", "fb.me", "fb.com", "wa.me"]

def dco():
    entries = []
    singular_pattern = 0
    phising_pattern = 0

    net = defaultdict(dict)
    matrix = defaultdict(list)
    with open("data/dco.njson", "r", encoding="utf-8") as file:
        for d in file.readlines():
            entry = json.loads(d)
            content = {
                'body':[],
                'cta_type':[],





























































                
                #'cta_text':[],
                'caption':[],
                #'link_description':[],
                'link_url':[],
                #'title':[]
            }

            maybe_phish = 0
            domains = []
            for card in entry.get("snapshot").get("cards"):
                for prop in content:
                    card_data = card[prop]
                    
                    if prop == 'link_url' and card_data:
                        url = tldextract.extract(card[prop])
                        url = url.top_domain_under_registry_suffix.replace(url.subdomain,"")
                        domains.append(f"{url}:{card['caption']}")
                        if card["caption"].lower() not in url and url not in card["caption"].lower():
                            maybe_phish+=1
                        content[prop].append(url)
                        continue

                    content[prop].append(card_data)

                for url in content["link_url"]:
                    matrix[url]+=content["link_url"]
            
            content = {k:list(set(content[k])) for k in content}
                
            if maybe_phish:
                phising_pattern+=1
                #print(json.dumps(content, indent=2, ensure_ascii=False))
            
            if len(set(domains)) > 1:
                singular_pattern+=1
                #print(singular_pattern, entry["page_id"], entry["snapshot"]["page_name"], set(domains))
                net[entry["page_id"]][f"{singular_pattern} - {entry["snapshot"]["page_name"]}"] = list(set(domains))

            entries.append(entry)
            
    matrix = {v:list(set(matrix[v])) for v in matrix}
    #print(json.dumps({v:matrix[v] for v in matrix if len(matrix[v])>1}, indent=2))
    print(json.dumps(net, indent=2, ensure_ascii=False))
    print(f"DCOs:{len(entries)}\nVariação de Domínio:{singular_pattern} Domínios:{len(matrix)}, Anunciantes: {len(net)}\nPotencial Phishing:{phising_pattern}")


def image():
    entries = []
    singular_pattern = 0
    phising_pattern = 0

    matrix = defaultdict(list)
    with open("data/image.njson", "r", encoding="utf-8") as file:
        for d in file.readlines():
            entry = json.loads(d)
            snapshot = entry.get("snapshot")
            content = {
                'body':None,
                'cta_type':None,
                'cta_text':None,
                'caption':None,
                'link_description':None,
                'link_url':None,
                'title':None
            }

            for k in content:
                content[k] = snapshot.get(k)
                if k == "link_url" and content[k] and snapshot.get("caption"):
                    url = tldextract.extract(content[k])
                    url = url.top_domain_under_registry_suffix.replace(url.subdomain,"")
                    if url in META_URLS:
                        continue
                    caption = content["caption"].lower()
                    #print(caption)

                    if caption not in url and url not in caption:
                        phising_pattern+=1
                        #print(f"{content[k], caption}")


            entries.append(entry)

    print(f"IMAGEs:{len(entries)}\nVariação de Domínio:{singular_pattern} Domínios:{len(matrix)}\nPotencial Phishing:{phising_pattern}")

if __name__ == "__main__":
    dco()
    #image()