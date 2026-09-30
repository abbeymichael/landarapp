import hashlib, hmac, os

def hash_password(password: str) -> tuple[bytes, bytes]:
    salt = os.urandom(16)
    return salt, hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)

def verify_password(password: str, salt: bytes, expected: bytes) -> bool:
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1), expected)
