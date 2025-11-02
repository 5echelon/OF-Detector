from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import re

app = Flask(__name__)
CORS(app)

def search_google(query):
    """Simple Google search scraper"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=headers, timeout=5)
        return response.text
    except:
        return ""

def check_onlyfans_indicators(username):
    """Search for OnlyFans indicators across platforms"""
    
    search_patterns = [
        f'"{username}" onlyfans',
        f'"{username}" OF link',
        f'site:twitter.com "{username}" onlyfans.com',
        f'site:reddit.com "{username}" OF',
        f'"{username}" subscribe exclusive content',
    ]
    
    total_score = 0
    findings = []
    
    of_keywords = [
        r'onlyfans\.com/\w+',
        r'only\s*fans',
        r'\bOF\b.*link',
        r'subscribe.*exclusive',
        r'link\s+in\s+bio.*only',
        r'spicy.*content',
        r'exclusive.*content',
    ]
    
    for pattern in search_patterns:
        try:
            html = search_google(pattern)
            
            if not html:
                continue
                
            matches = 0
            matched_keywords = []
            
            for keyword in of_keywords:
                found = re.findall(keyword, html, re.IGNORECASE)
                if found:
                    matches += len(found)
                    matched_keywords.append(keyword)
            
            if matches > 0:
                source = 'Twitter' if 'twitter.com' in pattern else 'Reddit' if 'reddit.com' in pattern else 'Google'
                
                if matches >= 5:
                    score = 25
                elif matches >= 3:
                    score = 15
                else:
                    score = 10
                    
                total_score += score
                findings.append({
                    'source': source,
                    'matches': matches,
                    'confidence': score,
                    'keywords': matched_keywords[:3]
                })
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Search failed for {pattern}: {str(e)}")
            continue
    
    confidence = min(total_score, 100)
    
    if confidence >= 70:
        status = 'HIGHLY LIKELY'
        status_color = 'text-red-500'
    elif confidence >= 40:
        status = 'POSSIBLY'
        status_color = 'text-yellow-500'
    elif confidence >= 15:
        status = 'LOW CONFIDENCE'
        status_color = 'text-yellow-600'
    else:
        status = 'Not Found'
        status_color = 'text-green-500'
    
    return {
        'username': username,
        'confidence': confidence,
        'status': status,
        'status_color': status_color,
        'findings': findings
    }

@app.route('/api/check', methods=['POST'])
def check_username():
    """API endpoint to check a username"""
    data = request.get_json()
    username = data.get('username', '').strip().replace('@', '')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    result = check_onlyfans_indicators(username)
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'OF Detector API',
        'endpoint': '/api/check',
        'method': 'POST',
        'body': {'username': 'instagram_username'}
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

4. Scroll down, click **"Commit new file"**

---

**File 2: `requirements.txt`**

1. Click **"Add file"** → **"Create new file"**
2. Name it: `requirements.txt`
3. Paste this:
```
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
beautifulsoup4==4.12.2
