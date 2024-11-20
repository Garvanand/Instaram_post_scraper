from flask import Flask, request, jsonify
import requests
from PIL import Image
import pytesseract
from io import BytesIO
import re

app = Flask(__name__)

GEMINI_API_KEY = ''
GEMINI_API_URL = ''

def extract_text_from_image(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        image = Image.open(BytesIO(response.content))
        return pytesseract.image_to_string(image).strip() if image else ""
    except Exception:
        return ""

def analyze_content_with_gemini(post_content, image_text, source_platform, media_url):
    payload = {
        "post_content": post_content,
        "image_text": image_text,
        "source_platform": source_platform,
        "media_url": media_url
    }
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to process with Gemini API: {e}"}

def fetch_instagram_post(post_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(post_url, headers=headers, timeout=10)
        response.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        og_title = soup.find("meta", property="og:title")
        og_description = soup.find("meta", property="og:description")
        og_image = soup.find("meta", property="og:image")

        post_content = og_title["content"] if og_title else "No title found"
        post_description = og_description["content"] if og_description else "No description found"
        post_image = og_image["content"] if og_image else None

        return {
            "content": post_content,
            "description": post_description,
            "image_url": post_image,
            "source_platform": "Instagram"
        }
    except Exception as e:
        return {"error": f"Error fetching Instagram post: {e}"}

def parse_instagram_post_for_product_details(post_content):
    product_details = {
        "title": "",
        "price": "",
        "category": "General",
        "description": "",
        "brand": "Unknown",
        "colors": [],
        "material": "",
    }

    match_title = re.search(r"([A-Za-z0-9\s]+)\s+(is now available|now available|for sale|on sale|buy now)", post_content, re.IGNORECASE)
    if match_title:
        product_details["title"] = match_title.group(1)

    match_price = re.search(r"(Rs\.\d{1,3}(?:,\d{3})*(?:\.\d{2})?)|(USD\s?\d+(\.\d{2})?)", post_content)
    if match_price:
        product_details["price"] = match_price.group(0)

    match_colors = re.findall(r"(Black|Grey|Blue|Red|Green|Yellow|Gold|Silver)", post_content, re.IGNORECASE)
    if match_colors:
        product_details["colors"] = match_colors

    match_material = re.search(r"(Cotton|Silk|Gold|Silver|Leather|Wool|Polyester)", post_content, re.IGNORECASE)
    if match_material:
        product_details["material"] = match_material.group(1)

    product_details["description"] = f"Discover {product_details['title']} at {product_details['price']} with colors like {', '.join(product_details['colors']) if product_details['colors'] else 'Various options'}."

    return product_details

@app.route('/generate-listing', methods=['POST'])
def generate_product_listing():
    data = request.json
    post_url = data.get('post_url')
    if not post_url or "instagram.com" not in post_url:
        return jsonify({"error": "Invalid or missing Instagram post URL"}), 400
    
    try:
        post_data = fetch_instagram_post(post_url)
        if "error" in post_data:
            return jsonify({"error": post_data["error"]}), 400

        post_content = post_data.get('content', "No content available")
        image_url = post_data.get('image_url', None)
        image_text = extract_text_from_image(image_url) if image_url else ""

        product_listing = analyze_content_with_gemini(
            post_content, image_text, post_data['source_platform'], image_url
        )
        if "error" in product_listing:
            return jsonify({"error": product_listing["error"]}), 500

        product_listing["product_type"] = product_listing.get("product_type", "Default Type")
        product_listing["category"] = product_listing.get("category", "Default Category")
        product_listing["title"] = product_listing.get("title", "Default Title")
        product_listing["brand"] = product_listing.get("brand", "Unknown")
        product_listing["description"] = product_listing.get("description", "No description available")
        product_listing["price"] = product_listing.get("price", {"amount": "0", "currency": "USD"})
        product_listing["dimensions"] = product_listing.get("dimensions", {"length": "0", "width": "0", "height": "0", "unit": "cm"})
        product_listing["item_weight"] = product_listing.get("item_weight", {"value": "0", "unit": "kg"})
        product_listing["keywords"] = product_listing.get("keywords", ["default", "product", "keywords"])
        product_listing["source_platform"] = post_data.get('source_platform', "Instagram")

        return jsonify(product_listing), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
