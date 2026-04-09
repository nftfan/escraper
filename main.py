import requests
import time
import math
from shapely.geometry import Point, Polygon
import json
import re
from urllib.parse import urlparse
import os

# Securely load the API Key from Railway Environment Variables
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Firebase Realtime Database endpoint for emails collection
FIREBASE_DB_URL = "https://trackingclients-default-rtdb.firebaseio.com/emails.json"
EMAILS_FILE = "emails.txt"

EXCLUDED_DOMAINS = {
    "sentry.wixpress.com",
    "sentry-next.wixpress.com"
}

def fetch_all_results(url, params):
    all_results = []
    while True:
        response = requests.get(url, params=params).json()
        results = response.get("results", [])
        all_results.extend(results)
        next_token = response.get("next_page_token")
        if not next_token:
            break
        time.sleep(2)
        params["pagetoken"] = next_token
    return all_results

def search_nearby(lat, lng, radius):
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY environment variable is not set!")
        return []
        
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "key": API_KEY
    }
    return fetch_all_results(url, params)

def get_website(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "website,geometry",
        "key": API_KEY
    }
    response = requests.get(url, params=params).json()
    result = response.get("result", {})
    website = result.get("website")
    location = result.get("geometry", {}).get("location", {})
    return website, location.get("lat"), location.get("lng")

def generate_grid(lat_min, lat_max, lng_min, lng_max, step_meters):
    R = 6378137
    points = []
    lat = lat_min
    while lat <= lat_max:
        lng = lng_min
        while lng <= lng_max:
            points.append((lat, lng))
            lng += (step_meters / (R * math.cos(math.pi * lat / 180))) * (180 / math.pi)
        lat += (step_meters / R) * (180 / math.pi)
    return points

def add_backslash_to_urls(url_list):
    return [url + '\\' for url in url_list if url]

def load_emails_from_file(filename=EMAILS_FILE):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r") as f:
        emails = {line.strip() for line in f if line.strip()}
    return emails

def append_emails_to_file(emails, filename=EMAILS_FILE):
    with open(filename, "a") as f:
        for email in emails:
            f.write(email + "\n")

def save_email_to_firebase(email):
    data = {"email": email}
    try:
        response = requests.post(FIREBASE_DB_URL, data=json.dumps(data))
        if response.ok:
            print(f"Saved to Firebase: {email}")
            return True
        else:
            print(f"Failed to save {email} to Firebase: {response.text}")
            return False
    except Exception as e:
        print(f"Error saving to Firebase: {e}")
        return False

def clean_url(url):
    url = url.replace("\\", "")  # Remove backslashes
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
    return url

def extract_emails_from_url(url):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    url = clean_url(url)
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        print(f"Fetching webpage: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        source_code = response.text
        print(f"Successfully fetched {len(source_code)} characters of source code")
        email_matches = re.findall(email_pattern, source_code)
        unique_emails = list(set(email_matches))
        print(f"Found {len(unique_emails)} unique email addresses from {url}")
        return unique_emails
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred with {url}: {e}")
        return []

def is_probably_system_email(email):
    domain = email.split('@')[-1]
    if domain in EXCLUDED_DOMAINS:
        return True
    local = email.split('@')[0]
    if re.fullmatch(r"[0-9a-f]{16,}", local, re.IGNORECASE):
        return True
    if re.fullmatch(r"\d{8,}", local):
        return True
    return False

def is_valid_email(email):
    image_exts = ('.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp', '.bmp', '.tiff', '.ico')
    if email.lower().endswith(image_exts):
        return False
    valid_pattern = re.compile(
        r"^(?!\.)[a-zA-Z0-9._%+-]+@(?!-)(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
    )
    if not valid_pattern.match(email):
        return False
    if '..' in email:
        return False
    if is_probably_system_email(email):
        return False
    return True

def filter_valid_emails_and_save(email_list):
    valid_emails = []
    emails_already_saved = load_emails_from_file()
    new_emails_to_file = []
    for email in set(email_list):
        if is_valid_email(email):
            valid_emails.append(email)
            if email not in emails_already_saved:
                if save_email_to_firebase(email):
                    new_emails_to_file.append(email)
            else:
                print(f"Skipped saving {email} to Firebase: already in file")
    if new_emails_to_file:
        append_emails_to_file(new_emails_to_file)
    return sorted(valid_emails)

def extract_emails_from_urls(urls):
    all_emails = []
    print(f"Processing {len(urls)} URLs...")
    print("=" * 60)
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing: {url}")
        emails = extract_emails_from_url(url)
        all_emails.extend(emails)
        if emails:
            print(f"  → Found emails: {emails}")
        else:
            print(f"  → No emails found")
    unique_all_emails = sorted(list(set(all_emails)))
    print(f"\n" + "=" * 60)
    print(f"SUMMARY: Found {len(unique_all_emails)} unique email addresses across all URLs")
    print("=" * 60)
    valid_emails = filter_valid_emails_and_save(unique_all_emails)
    return unique_all_emails, valid_emails

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
