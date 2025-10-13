import boto3
import os
from core.config import settings

session = boto3.session.Session()
s3 = session.client(
    "s3",
    endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'localhost:9000')}",
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "admin"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "supersecret"),
    region_name="us-east-1",
    use_ssl=os.getenv("MINIO_SECURE", "False").lower() == "true",
)

def ensure_bucket_exists(bucket_name: str):
    buckets = s3.list_buckets()
    if not any(b["Name"] == bucket_name for b in buckets.get("Buckets", [])):
        s3.create_bucket(Bucket=bucket_name)
