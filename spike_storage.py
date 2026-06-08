"""
Day-1 spike: prove boto3 can talk to Nyas S3-compatible storage.
List bucket, upload a file, generate a presigned URL, fetch it back.
"""
import os
import urllib.request
import boto3
from botocore.config import Config

def load_env(path=".env"):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

load_env()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name=os.environ["S3_REGION"],
    config=Config(s3={"addressing_style": "path"}),  # Nyas uses path-style
)
bucket = os.environ["S3_BUCKET"]
print(f"Endpoint: {os.environ['S3_ENDPOINT']}  bucket: {bucket}")

# 1. List existing objects
resp = s3.list_objects_v2(Bucket=bucket)
existing = [o["Key"] for o in resp.get("Contents", [])]
print(f"✓ Listed bucket — {len(existing)} object(s): {existing}")

# 2. Upload a file via boto3
key = "boto3_spike.txt"
body = b"uploaded via boto3 from the conversation-memory app"
s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
print(f"✓ put_object '{key}' ({len(body)} bytes)")

# 3. Presigned download URL
url = s3.generate_presigned_url("get_object",
                                Params={"Bucket": bucket, "Key": key},
                                ExpiresIn=600)
print(f"✓ Generated presigned URL (host: {url.split('/')[2]})")

# 4. Fetch it back over HTTP
with urllib.request.urlopen(url) as r:
    fetched = r.read()
assert fetched == body, f"mismatch! got {fetched!r}"
print(f"✓ Fetched back via HTTP, content matches: {fetched.decode()!r}")

# 5. Clean up (this credential is read+write, no delete — expected to be denied)
try:
    s3.delete_object(Bucket=bucket, Key=key)
    print("✓ Cleaned up test object")
except Exception as e:
    print(f"  (delete denied as expected — cred has delete=false: {type(e).__name__})")

print("\n🎉 Storage spike PASSED — boto3 ⇄ Nyas storage works (upload + presign + fetch).")
