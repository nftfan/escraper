def get_polygon_websites():
    print("Loading polygon coordinates from coordinates.json...")
    try:
        with open("coordinates.json", "r") as f:
            polygon_coords = json.load(f)
            
        if isinstance(polygon_coords[0][0], list) and isinstance(polygon_coords[0][0][0], float):
            polygon_coords = polygon_coords[0]
        if not all(isinstance(c, list) and len(c) == 2 for c in polygon_coords):
            raise ValueError("Each coordinate must be [lat, lng]")
    except Exception as e:
        print(f"Error loading coordinates.json: {e}")
        return []

    polygon = Polygon(polygon_coords)

    lats = [c[0] for c in polygon_coords]
    lngs = [c[1] for c in polygon_coords]
    lat_min, lat_max = min(lats), max(lats)
    lng_min, lng_max = min(lngs), max(lngs)

    radius = 1500
    step = 1000

    grid_points = generate_grid(lat_min, lat_max, lng_min, lng_max, step)
    valid_points = [pt for pt in grid_points if polygon.contains(Point(pt[0], pt[1]))]
    print(f"{len(valid_points)} circle centers inside polygon.")

    all_websites = set()
    for idx, (lat, lng) in enumerate(valid_points):
        print(f"Searching circle {idx+1}/{len(valid_points)} at ({lat:.5f}, {lng:.5f})")
        results = search_nearby(lat, lng, radius)
        for place in results:
            site, plat, plng = get_website(place["place_id"])
            if site and plat is not None and plng is not None:
                if polygon.contains(Point(plat, plng)):
                    all_websites.add(site)

    modified_urls = add_backslash_to_urls(list(all_websites))
    return modified_urls

def main():
    print("Starting 24/7 Polygon-based Email Address Extractor")
    print("=" * 50)
    
    while True:
        print("\n--- Starting new scan cycle ---")
        urls = get_polygon_websites()
        if not urls:
            print("No URLs found or error in coordinates. Retrying in 1 hour...")
            time.sleep(3600)
            continue
            
        cleaned_urls = [clean_url(url) for url in urls]
        all_emails, valid_emails = extract_emails_from_urls(cleaned_urls)
        
        print(f"\nCycle complete. Found {len(valid_emails)} valid emails.")
        print("Sleeping for 24 hours before scanning again...")
        time.sleep(86400) # Sleep for 24 hours

if __name__ == "__main__":
    main()
