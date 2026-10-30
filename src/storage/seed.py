import secrets
from pathlib import Path

from src.storage.storage import DocumentStore

# Demo accounts: username -> is_admin
SEED_ACCOUNTS = {"admin": True, "alice": False, "bob": False, "carol": False}
PASSWORD_BYTES = 12 #token_urlsafe turns this into 16 characters, above the minimum password length

def seed_accounts(store:DocumentStore, credentials_path:Path) -> list[str]:
    """Create the demo admin and users that do not exist yet, appending their generated passwords to credentials_path.
    
    Inputs:
    - store: document store the accounts are created in
    - credentials_path: gitignored file that receives one "username: password" line per new account
    
    Outputs:
    - Usernames created by this call, empty when every account already existed
    """
    created = []
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    for username, is_admin in SEED_ACCOUNTS.items():
        if store.database.get_user_by_name(username) is not None:
            continue
        password = secrets.token_urlsafe(PASSWORD_BYTES)
        store.register(username, password, is_admin)
        with credentials_path.open("a", encoding="utf-8") as file:
            file.write(f"{username}: {password}{' (admin)' if is_admin else ''}\n")
        created.append(username)
    return created
