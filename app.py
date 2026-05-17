from flask import Flask, render_template, request, jsonify
from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import urllib.parse

app = Flask(__name__)

TARGET_IMAGES = 200  # Changed to exactly 100 images
MAX_PAGES = 17  # Increased to ensure we can get 100 images

@app.route("/")
def home():
    return render_template("index.html")

def extract_images_from_html(html, seen):
    found = []
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all("a", class_="iusc"):
        m = tag.get("m")
        if m:
            try:
                data = json.loads(m)
                url = data.get("murl")
                if url and url.startswith("http") and url not in seen:
                    seen.add(url)
                    found.append(url)
            except:
                continue

    for tag in soup.find_all(attrs={"m": True}):
        try:
            data = json.loads(tag.get("m"))
            url = data.get("murl")
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                found.append(url)
        except:
            continue

    for match in re.finditer(r'"murl"\s*:\s*"(https?://[^"]+)"', html):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            found.append(url)

    return found

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"images": [], "error": "No query"})

    encoded_query = urllib.parse.quote_plus(query)

    try:
        session = requests.Session(impersonate="chrome120")
        session.get("https://www.bing.com", timeout=10)

        image_urls = []
        seen = set()
        first = 0
        page = 0

        # Keep fetching until we have exactly 100 images or run out of pages
        while len(image_urls) < TARGET_IMAGES and page < MAX_PAGES:
            url = (
                f"https://www.bing.com/images/search"
                f"?q={encoded_query}"
                f"&qft=+filterui:imagesize-large"
                f"&form=IRFLTR"
                f"&first={first}"
                f"&count=35"
            )

            response = session.get(url, timeout=15)
            if response.status_code != 200:
                break

            found_on_page = extract_images_from_html(response.text, seen)

            if not found_on_page:
                break

            # Calculate how many more images we need
            needed = TARGET_IMAGES - len(image_urls)
            
            # Add only the number of images we need to reach exactly 100
            if len(found_on_page) > needed:
                image_urls.extend(found_on_page[:needed])
            else:
                image_urls.extend(found_on_page)

            first += len(found_on_page)
            page += 1

        # Ensure we return exactly 100 images (or less if not enough found)
        result = image_urls[:TARGET_IMAGES]
        
        return jsonify({
            "images": result, 
            "count": len(result),
            "total_found": len(image_urls),
            "pages_fetched": page
        })

    except Exception as e:
        return jsonify({"images": [], "error": str(e), "count": 0})

if __name__ == "__main__":
    app.run(debug=True)