from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urlparse, urljoin

app = Flask(__name__)
CORS(app)

# Known link aggregator platforms
LINK_AGGREGATORS = [
    'linktr.ee', 'beacons.ai', 'allmylinks.com', 'hoo.be', 'bio.fm',
    'solo.to', 'taplink.cc', 'linkpop.com', 'snipfeed.co', 'lnk.bio',
    'campsite.bio', 'tap.bio', 'later.com', 'carrd.co', 'linkin.bio'
]

def fetch_page(url, timeout=5):
    """Safely fetch a webpage"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return response.text, response.url
    except:
        return "", url

def scrape_instagram_profile(username):
    """Scrape Instagram profile info (using public endpoints)"""
    try:
        # Try Instagram's public API
        url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        # Fallback: scrape HTML
        if response.status_code != 200:
            url = f"https://www.instagram.com/{username}/"
            html, _ = fetch_page(url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract from meta tags
            profile_data = {
                'username': username,
                'display_name': '',
                'bio': '',
                'profile_pic': '',
                'bio_links': []
            }
            
            # Get bio from meta description
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                content = meta_desc.get('content', '')
                # Parse: "X Followers, Y Following, Z Posts - See Instagram photos..."
                profile_data['bio'] = content
            
            # Look for links in bio
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if 'instagram.com' not in href and href.startswith('http'):
                    profile_data['bio_links'].append(href)
            
            return profile_data
        
        # If JSON worked
        data = response.json()
        user = data.get('graphql', {}).get('user', {})
        
        return {
            'username': username,
            'display_name': user.get('full_name', ''),
            'bio': user.get('biography', ''),
            'profile_pic': user.get('profile_pic_url_hd', ''),
            'bio_links': [user.get('external_url')] if user.get('external_url') else []
        }
        
    except Exception as e:
        print(f"Instagram scrape failed: {e}")
        return {
            'username': username,
            'display_name': '',
            'bio': f'Profile check for @{username}',
            'profile_pic': '',
            'bio_links': []
        }

def extract_name_variations(profile):
    """Generate all possible name variations"""
    variations = set()
    
    # Add username
    variations.add(profile['username'])
    
    # Add display name
    if profile['display_name']:
        variations.add(profile['display_name'])
        
        # Split name parts
        name_parts = profile['display_name'].split()
        variations.update(name_parts)
        
        # Concatenated version
        variations.add(''.join(name_parts))
    
    return list(variations)

def detect_of_indicators(text):
    """Smart pattern detection for OF hints"""
    if not text:
        return 0, []
    
    score = 0
    indicators = []
    text_lower = text.lower()
    
    # Emoji detection
    spicy_emojis = ['🌶️', '🌶', '🔥', '💦', '🍑', '🍆', '😈', '😏', '💋', '🔞', '💎', '✨', '🎀', '🍓', '🍒']
    emoji_count = sum(text.count(emoji) for emoji in spicy_emojis)
    if emoji_count > 0:
        score += emoji_count * 10
        indicators.append(f"{emoji_count} suggestive emoji(s)")
    
    # Keyword proximity patterns
    patterns = [
        (r'exclusive.{0,20}(content|access|link|subscribe|see)', 25, "Exclusive content pattern"),
        (r'link.{0,30}bio', 20, "Link in bio mention"),
        (r'subscribe.{0,20}(exclusive|content|more|see|unlock|access|premium)', 25, "Subscribe pattern"),
        (r'18\+|21\+|adults?\s+only|nsfw|🔞', 20, "Age restriction"),
        (r'what you.{0,15}(here for|looking for)', 30, "Direct invitation"),
        (r'see (more|what)|find out (more|what)', 15, "Teaser pattern"),
    ]
    
    for pattern, points, description in patterns:
        if re.search(pattern, text_lower):
            score += points
            indicators.append(description)
    
    # Premium/VIP indicators
    premium_words = ['premium', 'vip', 'private', 'special', 'unlock', 'paid']
    found_premium = [w for w in premium_words if w in text_lower]
    if found_premium:
        score += len(found_premium) * 15
        indicators.append(f"Premium indicators: {', '.join(found_premium)}")
    
    # Suggestive words
    suggestive = ['spicy', 'naughty', 'wild', 'uncensored', 'unfiltered', 'raw', 'explicit']
    found_suggestive = [w for w in suggestive if w in text_lower]
    if found_suggestive:
        score += len(found_suggestive) * 10
        indicators.append(f"Suggestive: {', '.join(found_suggestive)}")
    
    return score, indicators

def is_link_aggregator(url):
    """Check if URL is a link aggregator"""
    return any(domain in url.lower() for domain in LINK_AGGREGATORS)

def follow_links_for_of(bio_links, max_depth=2):
    """Recursively follow links to find OF"""
    of_links = []
    checked = set()
    
    def follow(url, depth=0):
        if depth > max_depth or url in checked or not url:
            return
        
        checked.add(url)
        
        try:
            html, final_url = fetch_page(url)
            
            # Check if we landed on OF
            if 'onlyfans.com' in final_url:
                of_links.append(final_url)
                return
            
            # Parse page for OF links
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(url, href)
                
                # Found OF link
                if 'onlyfans.com' in href.lower():
                    of_links.append(href)
                
                # Follow aggregator links
                elif is_link_aggregator(url) and depth < max_depth:
                    follow(href, depth + 1)
            
            time.sleep(0.3)  # Be nice
            
        except Exception as e:
            print(f"Error following {url}: {e}")
    
    for link in bio_links:
        follow(link)
    
    return of_links

def search_google_for_of(query):
    """Search Google for OF mentions"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=headers, timeout=5)
        html = response.text
        
        # Count OF-related keywords
        of_keywords = [
            r'onlyfans\.com',
            r'only\s*fans',
            r'\bOF\b.*link',
            r'subscribe.*exclusive',
        ]
        
        matches = 0
        for keyword in of_keywords:
            found = re.findall(keyword, html, re.IGNORECASE)
            matches += len(found)
        
        return matches
    except:
        return 0

def comprehensive_check(username):
    """Full OF detection system"""
    
    # 1. Get Instagram profile
    profile = scrape_instagram_profile(username)
    
    # 2. Check bio for indicators
    bio_score, bio_indicators = detect_of_indicators(profile['bio'])
    
    # 3. Follow all bio links
    of_links = follow_links_for_of(profile['bio_links'])
    
    # 4. Search with name variations
    name_variations = extract_name_variations(profile)
    search_score = 0
    search_findings = []
    
    for name in name_variations[:3]:  # Top 3 variations
        matches = search_google_for_of(f'"{name}" onlyfans')
        if matches > 0:
            search_score += min(matches * 2, 25)
            search_findings.append(f"{name}: {matches} mentions")
        time.sleep(0.5)
    
    # 5. Calculate total score
    total_score = bio_score
    
    if of_links:
        total_score = 100  # Direct link = confirmed
    else:
        total_score += min(search_score, 40)
    
    confidence = min(total_score, 100)
    
    # 6. Determine status
    if of_links:
        status = "CONFIRMED ✓"
        status_color = "text-red-500"
    elif confidence >= 70:
        status = "HIGHLY LIKELY"
        status_color = "text-red-500"
    elif confidence >= 40:
        status = "POSSIBLY"
        status_color = "text-yellow-500"
    elif confidence >= 15:
        status = "LOW CONFIDENCE"
        status_color = "text-yellow-600"
    else:
        status = "NOT FOUND"
        status_color = "text-green-500"
    
    return {
        'profile': {
            'username': profile['username'],
            'display_name': profile['display_name'],
            'bio': profile['bio'],
            'profile_pic': profile['profile_pic'],
        },
        'confidence': confidence,
        'status': status,
        'status_color': status_color,
        'of_links': of_links,
        'evidence': {
            'bio_indicators': bio_indicators,
            'search_findings': search_findings,
            'bio_links_checked': len(profile['bio_links'])
        }
    }

@app.route('/api/check', methods=['POST'])
def check_username():
    """API endpoint"""
    data = request.get_json()
    username = data.get('username', '').strip().replace('@', '')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    result = comprehensive_check(username)
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'OF Detector API', 'status': 'online'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
