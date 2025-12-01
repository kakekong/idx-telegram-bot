import http.server
import json
import logging
import socketserver

PORT = 8000

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        # Read content length
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
            print("Received Payload:")
            print(json.dumps(payload, indent=2))
        except json.JSONDecodeError:
            print("Received non-JSON:")
            print(body.decode())

        # Response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def log_message(self, format, *args):
        return  # Disable noisy logs


if __name__ == "__main__":
    print(f"Starting webhook listener on port {PORT}...")
    with socketserver.TCPServer(("", PORT), WebhookHandler) as httpd:
        print("Webhook server running. Waiting for POST requests...")
        httpd.serve_forever()
