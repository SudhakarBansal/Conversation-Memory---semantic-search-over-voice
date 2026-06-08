"""Central config — loads secrets from .env so nothing is hard-coded."""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env from the project root into os.environ

DATABASE_URL = os.environ["DATABASE_URL"]

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_REGION = os.environ["S3_REGION"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_BUCKET = os.environ["S3_BUCKET"]

# The embedding model. all-MiniLM-L6-v2: 384-dim, fast, runs on CPU, free.
# A solid default for semantic search — small enough to download in seconds.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
