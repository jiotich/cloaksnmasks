
import networkx as nx

def build_advertiser_co_media_graph(db, output_gexf=None):
    """
    Build a graph where:
      - Nodes = all advertisers from the 'advertiser' table.
      - Edges = pairs of advertisers that used at least one identical media hash
        (weight = number of distinct shared hashes).
    Node attributes: 'page_name' (for display in Gephi).
    Saves the graph as a GEXF file if output_gexf is given.
    """
    conn = db.connection
    cursor = conn.cursor()

    # 1. Create all advertiser nodes with page_name
    cursor.execute("SELECT page_id, page_name FROM advertiser")
    advertisers = cursor.fetchall()

    G = nx.Graph()
    for page_id, page_name in advertisers:
        G.add_node(page_id, page_name=page_name, label=page_name)

    # 2. Add edges from shared media
    query = """
        SELECT
            a1.advertiser_id AS adv1,
            a2.advertiser_id AS adv2,
            COUNT(DISTINCT am1.hash) AS shared_media_count
        FROM ad_media am1
        JOIN advert a1 ON am1.ad_archive_id = a1.ad_archive_id
        JOIN ad_media am2 ON am1.hash = am2.hash
            AND am2.ad_archive_id != am1.ad_archive_id
        JOIN advert a2 ON am2.ad_archive_id = a2.ad_archive_id
            AND a1.advertiser_id < a2.advertiser_id
        GROUP BY adv1, adv2
    """
    cursor.execute(query)
    for adv1, adv2, weight in cursor.fetchall():
        G.add_edge(adv1, adv2, weight=weight, shared_media_count=weight)

    # 3. Export to GEXF if requested
    if output_gexf:
        nx.write_gexf(G, output_gexf)
        print(f"Graph saved to {output_gexf}")

    return G
