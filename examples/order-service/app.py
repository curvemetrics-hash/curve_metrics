import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# In a Curve Metrics managed environment, these are injected automatically
# by the platform into your container. You never hardcode credentials!
PORT = int(os.environ.get("PORT", "8080"))
ENV_NAME = os.environ.get("CURVE_ENV_NAME", "checkout-dev")
TEAM_NAME = os.environ.get("CURVE_TEAM", "checkout")
DB_HOST = os.environ.get("DB_HOST", "checkout-dev-db.internal.cluster.local")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "orders_db")
S3_BUCKET = os.environ.get("S3_BUCKET", "curve-checkout-dev-receipts")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# In-memory storage for local demo
MOCK_ORDERS = [
    {"id": "ord-101", "item": "Cloud Architecture Blueprint", "amount": 299.00, "status": "completed"},
    {"id": "ord-102", "item": "Terraform Enterprise Module", "amount": 450.00, "status": "processing"}
]

class OrderServiceHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "service": "order-service",
                "environment": ENV_NAME,
                "team": TEAM_NAME,
                "managed_by": "Curve Metrics Platform",
                "cloud_resources": {
                    "database": f"{DB_HOST}:{DB_PORT}/{DB_NAME}",
                    "storage_bucket": S3_BUCKET,
                    "region": AWS_REGION
                }
            })
        elif self.path == "/api/orders":
            self._send_json(200, {
                "orders": MOCK_ORDERS,
                "total": len(MOCK_ORDERS),
                "storage_backend": f"s3://{S3_BUCKET}/orders/"
            })
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        if self.path == "/api/orders":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode("utf-8")) if post_data else {}
            except Exception:
                payload = {}

            new_order = {
                "id": f"ord-{len(MOCK_ORDERS) + 101}",
                "item": payload.get("item", "Standard Provisioned License"),
                "amount": payload.get("amount", 99.00),
                "status": "confirmed",
                "receipt_s3_key": f"s3://{S3_BUCKET}/receipts/ord-{len(MOCK_ORDERS) + 101}.json"
            }

            # If cloud storage is available, upload real receipt to Floci/AWS S3
            endpoint = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint and S3_BUCKET:
                try:
                    import boto3
                    from botocore.client import Config
                    s3_cli = boto3.client(
                        "s3",
                        endpoint_url=endpoint,
                        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
                        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
                        region_name=AWS_REGION,
                        config=Config(
                            s3={"addressing_style": "path"},
                            request_checksum_calculation="when_required",
                            response_checksum_validation="when_required"
                        )
                    )
                    s3_cli.put_object(
                        Bucket=S3_BUCKET,
                        Key=f"receipts/{new_order['id']}.json",
                        Body=json.dumps(new_order, indent=2).encode("utf-8"),
                        ContentType="application/json"
                    )
                    new_order["s3_uploaded"] = True
                    new_order["s3_endpoint"] = endpoint
                except Exception as s3_err:
                    new_order["s3_uploaded"] = False
                    new_order["s3_error"] = str(s3_err)

            MOCK_ORDERS.append(new_order)
            self._send_json(201, {
                "message": "Order created successfully! S3 receipt saved.",
                "order": new_order
            })
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        # Format log as JSON for CloudWatch
        sys.stdout.write(f"[order-service] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

if __name__ == "__main__":
    print(f"[*] [order-service] Starting on port {PORT}")
    print(f"[*] Environment: {ENV_NAME} (Team: {TEAM_NAME})")
    print(f"[*] Connected DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"[*] Connected S3: {S3_BUCKET}")
    server = HTTPServer(("0.0.0.0", PORT), OrderServiceHandler)
    server.serve_forever()
