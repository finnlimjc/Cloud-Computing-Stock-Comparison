import hashlib
import hmac
import re
import secrets

# Password hashing (scrypt cost parameters, stored with each hash so they can be raised later)
SCRYPT_N = 2**14 #Memory used per hash
SCRYPT_R = 8 #Memory used per step
SCRYPT_P = 1 #Number of parallel lanes
SALT_BYTES = 16 #Ensure two users with the same password product different hashes

# Credential rules
USERNAME_PATTERN = re.compile(r"[a-z0-9_-]{3,32}") # allowed characters 3 to 32 repeated times
MIN_PASSWORD_LENGTH = 8

def _scrypt(password:str, salt:bytes, n:int, r:int, p:int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)

def hash_password(password:str) -> str:
    """Hash a password as scrypt$n$r$p$salt_hex$hash_hex. All passwords have the same hash length."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"

def verify_password(password:str, stored_hash:str) -> bool:
    """Check a password against a stored scrypt hash in constant time."""
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    
    if scheme != "scrypt":
        return False
    
    digest = _scrypt(password, bytes.fromhex(salt_hex), int(n), int(r), int(p))
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex)) # Each comparison takes the same time, == will leak time information

def normalize_username(username:str) -> str:
    return username.strip().lower()

def validate_username(username:str) -> str | None:
    """Return why a normalized username is not allowed, or None when it is valid."""
    if not USERNAME_PATTERN.fullmatch(username):
        return "Usernames are 3 to 32 characters: letters, numbers, - and _."
    return None

def validate_password(password:str) -> str | None:
    """Return why a password is not allowed, or None when it is valid."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Passwords need at least {MIN_PASSWORD_LENGTH} characters."
    return None
