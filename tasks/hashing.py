import hashlib

def hash_url(url: str) -> str:
    "Return deterministic MD5 for use as doc_id."
    return hashlib.md5(url.encode()).hexdigest()