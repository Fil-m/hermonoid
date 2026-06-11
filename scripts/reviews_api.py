# Reviews API for Hermonoid landing page
# Deploy on fly.io or similar

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

REVIEWS_FILE = "reviews.json"
PORT = int(os.environ.get("PORT", 8000))

# Load reviews
def load_reviews():
    if os.path.exists(REVIEWS_FILE):
        with open(REVIEWS_FILE) as f:
            return json.load(f)
    return []

def save_reviews(reviews):
    with open(REVIEWS_FILE, "w") as f:
        json.dump(reviews, f, indent=2)

class ReviewHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/reviews":
            reviews = load_reviews()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"reviews": reviews}).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/reviews":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            reviews = load_reviews()
            reviews.insert(0, data)
            save_reviews(reviews)
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), ReviewHandler)
    print(f"Reviews API on :{PORT}")
    server.serve_forever()
