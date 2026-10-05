import csv
import sys
from collections import defaultdict

def group_domains_by_resolution(csv_path):
    # resolution -> set of main domains
    resolution_to_domains = defaultdict(set)

    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Verify required columns exist
        required = {'domain', 'resolutions'}
        if not required.issubset(reader.fieldnames):
            missing = required - set(reader.fieldnames)
            raise ValueError(f"CSV is missing columns: {missing}")

        for row in reader:
            main_domain = row['domain'].strip()
            resolutions_str = row['resolutions'].strip()
            if not resolutions_str:
                continue
            # Split by whitespace (space, tab, etc.)
            resolutions = resolutions_str.split()
            for res in resolutions:
                res = res.strip()
                if res:
                    resolution_to_domains[res].add(main_domain)

    # Convert sets to sorted lists for stable output
    grouped = {res: sorted(domains) for res, domains in resolution_to_domains.items()}
    return grouped

def main():
    if len(sys.argv) != 2:
        print("Usage: python group_domains.py <input.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    grouped = group_domains_by_resolution(csv_path)

    # Output as CSV: resolution, domain_count, domains (comma-separated)
    writer = csv.writer(sys.stdout)
    writer.writerow(['resolution', 'domain_count', 'domains'])
    for res, domains in sorted(grouped.items()):
        writer.writerow([res, len(domains), ','.join(domains)])

if __name__ == '__main__':
    main()