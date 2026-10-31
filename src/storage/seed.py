import secrets
from collections.abc import Callable
from pathlib import Path

from src.storage.parameters import ParameterStore
from src.storage.storage import DocumentStore

# Demo accounts: username -> is_admin
SEED_ACCOUNTS = {"admin": True, "alice": False, "bob": False, "carol": False}
PASSWORD_BYTES = 12 #token_urlsafe turns this into 16 characters, above the minimum password length

def append_credentials(credentials_path:Path, username:str, password:str, is_admin:bool) -> None:
    """Append one "username: password" line to a gitignored file, for local runs."""
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    with credentials_path.open("a", encoding="utf-8") as file:
        file.write(f"{username}: {password}{' (admin)' if is_admin else ''}\n")

def save_to_parameters(parameters:ParameterStore, prefix:str, username:str, password:str, is_admin:bool) -> None:
    """Save a password as the SecureString {prefix}/{username}, for AWS where the servers have no shell access.
    
    Inputs:
    - parameters: Parameter Store wrapper the SecureString is written through
    - prefix: parameter name prefix, e.g. SEED_PARAMETER_PREFIX
    - username: account the password belongs to
    - password: generated password to store
    - is_admin: not used here; accepted so the signature matches append_credentials, since seed_accounts calls either one as record_password(username, password, is_admin)
    """
    parameters.put_secret(f"{prefix}/{username}", password)

def seed_accounts(store:DocumentStore, record_password:Callable[[str, str, bool], None]) -> list[str]:
    """Create the demo admin and users that do not exist yet, passing each generated password to record_password.
    
    Inputs:
    - store: document store the accounts are created in
    - record_password: called with (username, password, is_admin) for every new account, e.g. append_credentials or save_to_parameters via functools.partial
    
    Outputs:
    - Usernames created by this call, empty when every account already existed
    """
    created = []
    for username, is_admin in SEED_ACCOUNTS.items():
        if store.database.get_user_by_name(username) is not None:
            continue # skip the account
        
        password = secrets.token_urlsafe(PASSWORD_BYTES)
        try:
            store.register(username, password, is_admin)
        except ValueError: #another web server created it between the check and the insert, and recorded its password
            continue
        record_password(username, password, is_admin)
        created.append(username)
    
    return created
