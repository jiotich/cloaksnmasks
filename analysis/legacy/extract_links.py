import json
import csv
import sys
from collections import defaultdict
import tldextract


def get_owners_by_link(links, exclude: list[str]=[]):
    counter = defaultdict(lambda: defaultdict(set))
    subdomains = defaultdict(set)
    for owner in links["ads"]:
        for ad in links["ads"][owner]:
            if ad != "info":
                for link in links["ads"][owner][ad]:
                    link["True Link"] = link["True Link"].lower()
                    if "fbgeo" in link["True Link"]:
                        # 'fbgeo://' é usado no tipo raro de CTA 'GET_DIRECTIONS'
                        continue
                    elif "www." in link["True Link"]:
                        link["True Link"] = link["True Link"].replace("www.","")
                    psl_url = tldextract.extract(link["True Link"])
                    cleaned_url = f"{psl_url.domain}.{psl_url.suffix}"
                    if psl_url.subdomain:
                        subdomains[cleaned_url].add(f"{psl_url.subdomain}")
                    counter[cleaned_url][link["True Link"]].add(f"{owner}")
    for item in counter:
        counter[item] = {"subdomains":list(subdomains[item]),
                        "advertisers": {url:list(counter[item][url]) for url in counter[item]}}
    
    sorted_dict = dict(sorted(counter.items(), key=lambda item: len(item[1]), reverse=True))
    return sorted_dict

def main(input_file, output_file, sbd=False):
    # Load the JSON data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Dictionary to accumulate total advertiser IDs per host
    host_counts = defaultdict(list)
    complete_refs = {}
    # Process each top-level domain entry
    for apex_domain, info in data.items():
        advertisers = info.get('advertisers', {})
        for url, advertiser_ids in advertisers.items():
            # Extract the full domain (host) using tldextract
            ext = tldextract.extract(url.lower())
            # Build the full domain: subdomain + domain + suffix
            main_domain = f"{ext.domain}.{ext.suffix}"
            if ext.subdomain and sbd:
                full_domain = f"{ext.subdomain}.{ext.domain}.{ext.suffix}"     
            # Add the number of advertiser IDs for this URL to the host total
            host_counts[main_domain] += advertiser_ids
        complete_refs[main_domain] = url
    # Write CSV
    with open(output_file, 'w+', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['url', 'advertiser_total'])
        for host, total in sorted(host_counts.items()):
            unique = len(set(total))
            writer.writerow([complete_refs[host], unique])

    print(f"Done. Results written to {output_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python script.py <input.json> <output.csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

    """with open(sys.argv[1], "r", encoding="utf-8") as file:
        content = json.load(file)
        print(json.dumps(get_owners_by_link(content), ensure_ascii=False, indent=2))"""