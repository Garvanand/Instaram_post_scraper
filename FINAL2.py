from flask import Flask, request, jsonify
import tweepy
import requests
from PIL import Image
import pytesseract
from io import BytesIO
import re

app = Flask(__name__)

TWITTER_API_KEY = ''
TWITTER_API_SECRET = ''
TWITTER_ACCESS_TOKEN = ''
TWITTER_ACCESS_TOKEN_SECRET = ''
GEMINI_API_KEY = ''
GEMINI_API_URL = ''

def extract_text_from_image(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        image = Image.open(BytesIO(response.content))
        return pytesseract.image_to_string(image).strip() if image else ""
    except Exception:
        return ""

def analyze_content_with_gemini(tweet_content, image_text, source_platform, media_url):
    payload = {
        "tweet_content": tweet_content,
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

def fetch_twitter_post(post_url):
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    try:
        tweet_id = re.search(r"status/(\d+)", post_url).group(1)
        tweet = api.get_status(tweet_id, tweet_mode="extended")
        media_url = tweet.entities.get("media", [{}])[0].get("media_url_https", None)
        metrics = {
            "likes": tweet.favorite_count or 0,
            "shares": tweet.retweet_count or 0,
            "comments": 0
        }
        return {
            "content": tweet.full_text or "No content available",
            "image_url": media_url,
            "metrics": metrics,
            "source_platform": "Twitter"
        }
    except Exception as e:
        return {"error": f"Error fetching Twitter post: {e}"}

def parse_tweet_for_product_details(tweet_content):
    product_details = {
        "title": "",
        "price": "",
        "category": "General",
        "description": "",
        "brand": "Unknown",
        "colors": [],
        "ram": "",
        "rom": "",
        "material": "",
    }

    match_title = re.search(r"([A-Za-z0-9\s]+)\s+(is now available|now available|for sale|on sale|buy now)", tweet_content)
    if match_title:
        product_details["title"] = match_title.group(1)

    match_price = re.search(r"(Rs\.\d{1,3}(?:,\d{3})*(?:\.\d{2})?)|(USD\s?\d+(\.\d{2})?)", tweet_content)
    if match_price:
        product_details["price"] = match_price.group(0)

    match_colors = re.findall(r"(Black|Grey|Blue|Red|Green|Yellow|Gold|Silver)", tweet_content, re.IGNORECASE)
    if match_colors:
        product_details["colors"] = match_colors

    match_ram_rom = re.search(r"(\d{1,2}GB)\s+RAM\s+\+?\s*(\d{1,3}GB)\s+ROM", tweet_content)
    if match_ram_rom:
        product_details["ram"] = match_ram_rom.group(1)
        product_details["rom"] = match_ram_rom.group(2)

    match_material = re.search(r"(Cotton|Silk|Gold|Silver|Leather|Wool|Polyester)", tweet_content, re.IGNORECASE)
    if match_material:
        product_details["material"] = match_material.group(1)

    product_details["description"] = f"Grab the stylish and high-quality {product_details['title']} at an incredible price of {product_details['price']}. Available in colors: {', '.join(product_details['colors']) if product_details['colors'] else 'Various colors available'}. With specifications like {product_details['ram']} RAM and {product_details['rom']} ROM, this product is perfect for your needs."

    return product_details

def generate_product_listing_from_tweet(tweet_content):
    product_details = parse_tweet_for_product_details(tweet_content)

    product_listing = {
        "asin": "DefaultASIN",
        "availability": "In Stock",
        "brand": product_details["brand"],
        "category": product_details["category"],
        "country_of_origin": "Unknown",
        "description": product_details["description"],
        "dimensions": {
            "height": "0",
            "length": "0",
            "unit": "cm",
            "width": "0"
        },
        "generated_listing": f"""
## Product Listing: {product_details['title']}

**Title:** {product_details['title']}

**Price:** {product_details['price']}

**Availability:** In Stock

**Brand:** {product_details['brand']}

**Category:** {product_details['category']}

**Specifications:**
* **Colors:** {', '.join(product_details['colors']) if product_details['colors'] else 'Various colors available'}
* **Material:** {product_details['material'] if product_details['material'] else 'N/A'}
* **RAM:** {product_details['ram'] if product_details['ram'] else 'N/A'}
* **ROM:** {product_details['rom'] if product_details['rom'] else 'N/A'}

**Description:**
{product_details['description']}

**Call to Action:**
Buy Now! [Link to Product Page]

**Image:** (Requires an image of the product)
""",
        "item_package_quantity": 1,
        "item_weight": {
            "unit": "kg",
            "value": "0"
        },
        "keywords": [product_details["title"], product_details["category"], "product", "sale"],
        "price": {
            "amount": product_details["price"],
            "currency": "INR"
        },
        "product_type": product_details["category"],
        "shipping_weight": {
            "unit": "kg",
            "value": "0"
        },
        "sku": "DefaultSKU",
        "social_media_metrics": {
            "comments": 0,
            "likes": 0,
            "shares": 0
        },
        "source_platform": "Twitter",
        "title": product_details["title"]
    }

    return product_listing

@app.route('/generate-listing', methods=['POST'])
def generate_product_listing():
    data = request.json
    post_url = data.get('post_url')
    if not post_url or "twitter.com" not in post_url:
        return jsonify({"error": "Invalid or missing Twitter post URL"}), 400
    
    try:
        post_data = fetch_twitter_post(post_url)
        if "error" in post_data:
            return jsonify({"error": post_data["error"]}), 400
        tweet_content = post_data.get('content', "No content available")
        image_text = extract_text_from_image(post_data.get('image_url', None)) if post_data.get('image_url') else ""
        metrics = post_data.get('metrics', {"likes": 0, "shares": 0, "comments": 0})
        product_listing = analyze_content_with_gemini(
            tweet_content, image_text, post_data['source_platform'], post_data.get('image_url')
        )
        if "error" in product_listing:
            return jsonify({"error": product_listing["error"]}), 500
        
        product_listing["social_media_metrics"] = metrics
        product_listing["product_type"] = product_listing.get("product_type", "Default Type")
        product_listing["category"] = product_listing.get("category", "Default Category")
        product_listing["title"] = product_listing.get("title", "Default Title")
        product_listing["brand"] = product_listing.get("brand", "Unknown")
        product_listing["description"] = product_listing.get("description", "No description available")
        product_listing["price"] = product_listing.get("price", {"amount": "0", "currency": "USD"})
        product_listing["dimensions"] = product_listing.get("dimensions", {"length": "0", "width": "0", "height": "0", "unit": "cm"})
        product_listing["item_weight"] = product_listing.get("item_weight", {"value": "0", "unit": "kg"})
        product_listing["keywords"] = product_listing.get("keywords", ["default", "product", "keywords"])
        product_listing["source_platform"] = post_data.get('source_platform', "Unknown")
        return jsonify(product_listing), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
