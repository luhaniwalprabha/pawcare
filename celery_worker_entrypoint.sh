#!/bin/bash
# Start a minimal HTTP server on port 8080 for Cloud Run health checks
# Cloud Run requires every service to listen on a port
# This runs alongside the Celery worker

python3 -c "
import http.server
import threading
import os

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, format, *args):
        pass  # suppress access logs

port = int(os.environ.get('PORT', 8080))
server = http.server.HTTPServer(('0.0.0.0', port), HealthHandler)
thread = threading.Thread(target=server.serve_forever)
thread.daemon = True
thread.start()
print(f'Health server running on port {port}')
" &

# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info --concurrency=2
