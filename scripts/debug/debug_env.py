#!/usr/bin/env python3
"""
Simple environment debug script for Railway
"""

import os
import sys

print("🔍 RAILWAY ENVIRONMENT DEBUG - NO CACHE BUILD")
print("=" * 50)

# Check PORT
port = os.environ.get('PORT')
print(f"PORT env var: '{port}' (type: {type(port)})")

# Check all environment variables
print("\n📝 All Environment Variables:")
for key in sorted(os.environ.keys()):
    value = os.environ[key]
    if any(secret in key.upper() for secret in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'JSON']):
        value = value[:10] + "..." if len(value) > 10 else "***"
    print(f"  {key}: {value}")

# Test simple HTTP server
if port:
    try:
        port_int = int(port)
        print(f"\n✅ PORT can be converted to integer: {port_int}")

        # Start simple HTTP server
        from http.server import HTTPServer, SimpleHTTPRequestHandler

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"""
                <html>
                <body>
                <h1>🎉 SUCCESS!</h1>
                <p>Railway app is working on port {port_int}</p>
                <p>Environment variables are properly set</p>
                <hr>
                <h2>Environment Info:</h2>
                <ul>
                <li>PORT: {port}</li>
                <li>Python: {sys.version}</li>
                <li>Working Directory: {os.getcwd()}</li>
                </ul>
                </body>
                </html>
                """.encode())

        server = HTTPServer(('0.0.0.0', port_int), Handler)
        print(f"🚀 Starting HTTP server on port {port_int}")
        server.serve_forever()

    except ValueError as e:
        print(f"❌ Cannot convert PORT to integer: {e}")
        sys.exit(1)
else:
    print("❌ PORT environment variable not set")
    sys.exit(1)