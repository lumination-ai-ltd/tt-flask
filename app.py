from flask import Flask, request, jsonify
import requests
import re
import time
from google_play_scraper import Sort, reviews
from app_store_scraper import AppStore
from flask_cors import CORS
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})

api_key = 'RMlCZe2sGkoMPtfl_xDtL07nK5vTDJv3ZccnUpmNCf0'

def fetch_data(query, api_key):
    url = 'https://api.producthunt.com/v2/api/graphql'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    response = requests.post(url, headers=headers, json={'query': query})
    return response.json()

def get_product_details(slug):
    query = f'''
    query {{
      post(slug: "{slug}") {{
        name
        tagline
        description
        website
        
        comments {{
          edges {{
            node {{
              id
              user {{
                id
                username
                profileImage
              }}
              body
              url
              createdAt
            }}
          }}
        }}
      }}
    }}
    '''
    data = fetch_data(query, api_key)
    product = data.get('data', {}).get('post', {})
    
    if not product:
        return None

    product_details = {
        'Name': product.get('name'),
        'Tagline': product.get('tagline'),
        'Description': product.get('description'),
        'Website': product.get('website'),
        
        'Comments': [
            {
                'CommentID': comment.get('node', {}).get('id'),
                'UserID': comment.get('node', {}).get('user', {}).get('id'),
                'Username': comment.get('node', {}).get('user', {}).get('username'),
                'ProfileImage': comment.get('node', {}).get('user', {}).get('profileImage'),
                'Body': comment.get('node', {}).get('body'),
                'CreatedAt': comment.get('node', {}).get('createdAt'),
                "Url": comment.get('node', {}).get('url'),
            }
            for comment in product.get('comments', {}).get('edges', [])
        ]
    }
    
    return product_details

def extract_slug_from_url(url):
    path = urlparse(url).path
    slug = path.split('/')[-1]
    return slug

class Trustpilot:
    def __init__(self):
        self.remote_base_url = 'https://trustpilot.com'
        self.place_id = None

    def handle_credential_save(self, url_value):
        business_info = self.verify_credential(url_value)
        return business_info

    def verify_credential(self, download_url):
        if not download_url:
            raise ValueError('URL field should not be empty!')

        if self.is_valid_url(download_url):
            reviews = []
            business_unit = {}

            download_url = download_url.split('?')[0]
            self.remote_base_url = download_url

            url_array = download_url.split('/')
            business_name = url_array[-1].split('?')[0]
            self.place_id = business_name

            curr_url = f"{download_url}?languages=all"
            is_found_next_url = True
            for x in range(1, 6):
                if not is_found_next_url:
                    break

                response = requests.get(curr_url)
                file_url_contents = response.text

                if not file_url_contents:
                    raise Exception("Can't fetch reviews due to slow network, please try again")

                html = BeautifulSoup(file_url_contents, 'html.parser')
                script = html.find('script', {'id': '__NEXT_DATA__'})

                if script:
                    data = json.loads(script.string)

                    if 'businessUnit' in data['props']['pageProps'] and x == 1:
                        business_unit = data['props']['pageProps']['businessUnit']

                    if 'reviews' in data['props']['pageProps']:
                        reviews_data = data['props']['pageProps']['reviews']
                        reviews.extend(reviews_data)

                    is_found_next_url = False
                    if business_unit:
                        total_reviews = business_unit.get('numberOfReviews')
                        if total_reviews > (x * 20):
                            curr_url = f"{self.remote_base_url}?page={x + 1}"
                            is_found_next_url = True

            return reviews
        else:
            raise ValueError('Please enter a valid url!')

    def is_valid_url(self, url):
        try:
            result = requests.get(url)
            return result.status_code == 200
        except:
            return False

def redeem_coupon_code(coupon_code):
    api_url = "https://script.google.com/macros/s/AKfycbx8aD10U35Rh4mk0xMuw6lLxWI6-wFq5ArcFk7AMYdMMU6r1o3qcgDHxWzr56RqyEVH/exec"
    
    if not coupon_code:
        print("Please provide a coupon code.")
        return

    request_data = {
        'code': coupon_code
    }

    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(request_data))
        
        if response.status_code != 200:
            response.raise_for_status()
        
        result = response.text
        print("RESULT", result)
        return result, 200
    except requests.exceptions.HTTPError as http_err:
        return f'HTTP error occurred: {http_err}', 500
    except Exception as err:
        return f'Other error occurred: {err}', 500
    

@app.route('/api/get-trustpilot-reviews', methods=['GET'])
def get_reviews():
    business_name = request.args.get('business_name')
    if not business_name:
        return jsonify({'error': 'Business name is required'}), 400

    url = f'https://www.trustpilot.com/review/{business_name}'
    
    trustpilot = Trustpilot()
    try:
        reviews = trustpilot.handle_credential_save(url)
        return jsonify({'reviews': reviews, "platform": "Trustpilot"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/test', methods=['GET'])
def redeem_coupon():
    return jsonify({'sucess': 'Work'}), 200

    
@app.route('/api/get-producthunt-reviews', methods=['GET'])
def product():
    full_url = request.args.get('url')
    if not full_url:
        return jsonify({'error': 'URL parameter is required'}), 400
    
    slug = extract_slug_from_url(full_url)
    if not slug:
        return jsonify({'error': 'Invalid URL'}), 400
    
    product_details = get_product_details(slug)
    if product_details:
        print({'reviews': product_details, "platform": "ProductHunt" })
        return jsonify({'reviews': product_details,"platform": "ProductHunt" })
    else:
        return jsonify({'error': 'Product not found'}), 404


@app.route('/api/getTweet', methods=['GET'])
def get_tweet():
    tweet_id = request.args.get('id')
    if not tweet_id:
        return jsonify({'error': 'No tweet ID provided'}), 400

    url = f'https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en&features=tfw_timeline_list%3A%3Btfw_follower_count_sunset%3Atrue%3Btfw_tweet_edit_backend%3Aon%3Btfw_refsrc_session%3Aon%3Btfw_fosnr_soft_interventions_enabled%3Aon%3Btfw_show_birdwatch_pivots_enabled%3Aon%3Btfw_show_business_verified_badge%3Aon%3Btfw_duplicate_scribes_to_settings%3Aon%3Btfw_use_profile_image_shape_enabled%3Aon%3Btfw_show_blue_verified_badge%3Aon%3Btfw_legacy_timeline_sunset%3Atrue%3Btfw_show_gov_verified_badge%3Aon%3Btfw_show_business_affiliate_badge%3Aon%3Btfw_tweet_edit_frontend%3Aon&token=4dfmf1arq4v'

    try:
        response = requests.get(url)
        response.raise_for_status()
        return jsonify({'reviews': response.json(),"platform": "X"  })
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500


def extract_id_from_url(url):
    # Regular expression to match the package ID in the URL
    pattern = r"https://play.google.com/store/apps/details\?id=([^&]+)"
    
    # Search for the package ID in the URL
    match = re.search(pattern, url)

    if match:
        return match.group(1)
    else:
        return None
    
def fetch_all_reviews(url, count=200, stars=5):
    package_id = extract_id_from_url(url)
    if not package_id:
        raise ValueError("Invalid URL: Could not extract package ID.")

    results = []
    continuation_token = None

    while len(results) < count:
        result, continuation_token = reviews(
            package_id,
            lang='en',
            country='us',
            sort=Sort.NEWEST,
            filter_score_with=stars,
            count=min(count - len(results), 100),  # Adjust count to avoid fetching too many at once
            continuation_token=continuation_token
        )

        results.extend(result)
        time.sleep(1)  # Add a delay to avoid rate limiting

    return results

    
def extract_app_info(url):
    pattern = r"https://apps\.apple\.com/(\w+)/app/([^/]+)/id(\d+)"
    match = re.match(pattern, url)
    if match:
        country, app_name, app_id = match.groups()
        app_name = app_name.replace('-', ' ')  # Convert hyphens to spaces
        return country, app_name, app_id
    return None, None, None

@app.route("/test")
def test():
    return jsonify({"message": "Hello World"})


@app.route('/api/get-playstore-reviews', methods=['GET'])
def fetch_reviews():
    """API endpoint to fetch reviews for a given Google Play Store app."""
    url = request.args.get('url')
    count = int(request.args.get('count', 200))
    stars = int(request.args.get('stars', 5))
    
    if not url:
        return jsonify({"error": "Please provide a Google Play Store URL."}), 400
    
    try:
        reviews_data = fetch_all_reviews(url, count=count, stars=stars)
        return jsonify({"reviews": reviews_data, "platform": "PlayStore"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching reviews."}), 

@app.route('/api/get-appstore-reviews', methods=['GET'])
def get_appstore_reviews():
    url = request.args.get('url')
    num_reviews = request.args.get('num_reviews', default=20, type=int)

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    country, app_name, app_id = extract_app_info(url)

    if not all([country, app_name, app_id]):
        return jsonify({"error": "Invalid App Store URL"}), 400

    try:
        app = AppStore(country=country, app_name=app_name, app_id=app_id)
        app.review(how_many=num_reviews)
        return jsonify({"reviews": app.reviews, "platform": "AppStore"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
   