import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin with service account
cred = credentials.Certificate("FIREBASE_KEY_JSON")
firebase_admin.initialize_app(cred)

# Firestore client instance
db = firestore.client()

def save_search_history(user_id, query):
    doc_ref = db.collection("search_history").document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        queries = data.get("queries", [])
        queries.append(query)
        queries = queries[-20:]  # Keep last 20 searches
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
