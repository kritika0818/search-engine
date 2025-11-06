from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from transformers import pipeline
from collections import OrderedDict, defaultdict
import re
import urllib.parse
import firebase_admin
from firebase_admin import credentials, firestore

from newspaper import Article
from boilerpy3 import extractors

app = Flask(__name__)
app.secret_key = "verysecrethackathonkey123"
CORS(app)

cred = credentials.Certificate("C:\Users\lenovo\OneDrive\Desktop\my-project\backend\serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
classifier = pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-1")

cache = OrderedDict()
CACHE_SIZE = 20

DEFAULT_LIMIT = 20
MAX_LIMIT = 80
SUMMARIZE_LIMIT = 5

feedback_store = defaultdict(list)
USER_ID = "default_user"

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return text.strip()

def summarize_texts(snippets):
    summaries = []
    for text in snippets:
        cleaned = clean_text(text)
        max_len = min(60, max(25, len(cleaned.split()) - 1))
        if len(cleaned.split()) < 20:
            summaries.append(cleaned)
        else:
            try:
                summary = summarizer(cleaned, min_length=20, max_length=max_len)[0]["summary_text"]
            except Exception as e:
                print(f"Summarization error: {e}")
                summary = cleaned
            summaries.append(summary)
    return summaries

def scrape_duckduckgo_search(query, start=0, limit=DEFAULT_LIMIT):
    cache_key = f"{query}:{start}:{limit}"
    if cache_key in cache:
        print(f"Cache hit for key: {cache_key}")
        return cache[cache_key]

    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")

    all_results = []
    for res in soup.find_all("div", class_="result"):
        title_tag = res.find("a", class_="result__a")
        snippet_tag = res.find("a", class_="result__snippet")
        if title_tag and snippet_tag:
            all_results.append({
                "title": clean_text(title_tag.get_text(strip=True)),
                "link": title_tag.get("href"),
                "snippet": clean_text(snippet_tag.get_text(strip=True))
            })

    selected_results = all_results[start:start+limit]

    summaries = summarize_texts([r["snippet"] for r in selected_results[:SUMMARIZE_LIMIT]])
    for i, summary in enumerate(summaries):
        selected_results[i]["summary"] = summary

    for r in selected_results:
        r["category"] = categorize_text(r["snippet"], query)

    save_search_history(USER_ID, query)

    if len(cache) >= CACHE_SIZE:
        cache.popitem(last=False)
    cache[cache_key] = selected_results

    print(f"Returning {len(selected_results)} results for query '{query}'")
    return selected_results

def save_search_history(user_id, query):
    doc_ref = db.collection("search_history").document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        queries = data.get("queries", [])
        queries.append(query)
        queries = queries[-20:]
        doc_ref.set({"queries": queries})
    else:
        doc_ref.set({"queries": [query]})

def get_search_history(user_id):
    doc_ref = db.collection("search_history").document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("queries", [])
    else:
        return []

def get_real_url(possible_url):
    if possible_url.startswith("//duckduckgo.com/l/?"):
        parsed = urllib.parse.urlparse(possible_url)
        query = urllib.parse.parse_qs(parsed.query)
        uddg_list = query.get('uddg')
        if uddg_list:
            return urllib.parse.unquote(uddg_list[0])
    return possible_url

def extract_full_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = article.text
        if not text or len(text.split()) < 20:
            extractor = extractors.ArticleExtractor()
            html = requests.get(url, timeout=10).text
            text = extractor.get_content(html)
        return text
    except Exception as e:
        print(f"Full text extraction error: {e}")
        return None

def summarize_full_text(text, max_input_tokens=1024, max_summary_length=100):
    words = text.split()
    if len(words) <= max_input_tokens:
        return summarizer(text, min_length=20, max_length=max_summary_length)[0]['summary_text']
    summaries = []
    chunk_size = max_input_tokens - 50
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        try:
            chunk_sum = summarizer(chunk, min_length=20, max_length=max_summary_length)[0]['summary_text']
            summaries.append(chunk_sum)
        except Exception as e:
            print(f"Chunk summarization error: {e}")
            summaries.append(chunk)
    if len(summaries) > 1:
        try:
            return summarizer(" ".join(summaries), min_length=20, max_length=max_summary_length)[0]['summary_text']
        except Exception as e:
            print(f"Final chunk summarization error: {e}")
            return " ".join(summaries)
    return summaries[0]

def categorize_text(text, query):
    query = query.lower()
    text_lc = text.lower()

    if any(w in query for w in ['learn', 'tutorial', 'course']):
        labels = ["Early Learner", "Intermediate", "Advanced"]
    elif any(w in query for w in ['news', 'update', 'latest']):
        labels = ["Politics", "Sports", "Technology", "Health", "Business", "Entertainment", "Economy"]
    elif any(w in query for w in ['shopping', 'buy', 'price']):
        labels = ["Electronics", "Fashion", "Home", "Books", "Toys"]
    else:
        labels = ["General", "Other"]

    sport_kw = ["match", "tournament", "goal", "score", "team", "player", "league", "cricket", "football", "soccer"]
    if any(w in text_lc for w in sport_kw):
        return "Sports"
    tech_kw = ["technology", "tech", "AI", "software", "hardware", "smartphone", "computer"]
    if any(w in text_lc for w in tech_kw):
        return "Technology"
    politics_kw = ["government", "election", "policy", "minister", "president", "parliament"]
    if any(w in text_lc for w in politics_kw):
        return "Politics"
    health_kw = ["health", "medical", "doctor", "hospital", "covid", "vaccine", "medicine"]
    if any(w in text_lc for w in health_kw):
        return "Health"

    try:
        result = classifier(text, candidate_labels=labels)
        return result['labels'][0]
    except Exception as e:
        print(f"Category classification error: {e}")
        return "Uncategorized"

@app.route('/summary', methods=['GET'])
def summary():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400

    url_real = get_real_url(url)
    cache_key = f"full_summary:{url_real}"
    if cache_key in cache:
        print(f"Cache hit for summary: {url_real}")
        return jsonify({"summary": cache[cache_key]}), 200

    full_text = extract_full_text(url_real)
    if not full_text or len(full_text.strip()) == 0:
        return jsonify({"summary": "Full content unavailable or could not be extracted."}), 200
    summary_text = full_text if len(full_text.split()) < 20 else summarize_full_text(full_text)

    if len(cache) >= CACHE_SIZE:
        cache.popitem(last=False)
    cache[cache_key] = summary_text
    return jsonify({"summary": summary_text})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing search query parameter q"}), 400
    try:
        limit = int(request.args.get('limit', DEFAULT_LIMIT))
        start = int(request.args.get('start', 0))
        limit = min(max(limit, 1), MAX_LIMIT)
        start = max(start, 0)
    except Exception:
        limit, start = DEFAULT_LIMIT, 0

    try:
        data = scrape_duckduckgo_search(query, start=start, limit=limit)
        return jsonify({"results": data}), 200
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get("text")
    if not text:
        return jsonify({"error": "Missing text for TTS"}), 400
    return jsonify({"ok": True, "text": text})

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    url = data.get("url")
    category = data.get("category")
    summary_fb = data.get("summary_feedback")
    if not url:
        return jsonify({"error": "Missing url in feedback"}), 400
    feedback_store[url].append({
        "category": category,
        "summary_feedback": summary_fb
    })
    return jsonify({"ok": True})

@app.route('/feedback', methods=['GET'])
def get_feedback():
    return jsonify(feedback_store)

@app.route('/history', methods=['GET'])
def get_history():
    history = get_search_history(USER_ID)
    return jsonify({"history": history})

def get_search_history(user_id):
    doc_ref = db.collection("search_history").document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("queries", [])
    else:
        return []

if __name__ == '__main__':
    app.run(debug=True)
