
import json
from collections import defaultdict
import tldextract

def get_owners_by_link(links):
    counter = defaultdict(list)
    #print(json.dumps(links["ads"], ensure_ascii=False, indent=2))
    #print(f"{links["total"]} {len(links["ads"])}")

    for owner in links["ads"]:
        for ad in links["ads"][owner]:
            if ad != "info":
                for link in links["ads"][owner][ad]:
                    url = tldextract.extract(link["True Link"])
                    counter[url.top_domain_under_public_suffix].append(links["ads"][owner]["info"]["page"])
    
    print("{")
    for item in counter:
        counter[item] = set(counter[item])
        if len(counter[item]) > 1 and len(counter[item]) < 200:
            #print(item, counter[item], "\n")
            print(f"\"{item}\": {list(counter[item])},")
    print("}")

if __name__ == "__main__":
    content = {}
    with open("data/experimental/breuro/pt_init_links.json", "r") as file:
        content = json.load(file)
    get_owners_by_link(content)
