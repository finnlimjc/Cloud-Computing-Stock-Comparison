from pathlib import Path
import boto3
from botocore.exceptions import BotoCoreError, ClientError

class LocalObjectStore:
    """
    Files kept under one folder by key, with the same methods as S3ObjectStore.
    
    Inputs:
    - root: folder holding every object
    """
    
    def __init__(self, root:Path) -> None:
        self.root = root.resolve()
    
    def _path(self, key:str) -> Path:
        """Resolve a key to a file path, refusing any key that points outside the root."""
        path = (self.root / key).resolve()
        # Prevent malicious actors from accessing root using ".."
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError(f"Invalid object key: {key}")
        return path
    
    def put(self, key:str, data:bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True) # Create all parent folders and do nothing if already exist
        path.write_bytes(data)
    
    def get(self, key:str) -> bytes:
        return self._path(key).read_bytes()
    
    def delete(self, key:str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True) # Delete the file, if does not exist, do nothing
        if path.parent != self.root and not any(path.parent.iterdir()): # Protect the root and checks if folder is empty
            path.parent.rmdir() #drop the empty document_id folder

def _check_key(key:str) -> str:
    """Refuse keys that are empty, absolute or contain "..", matching what LocalObjectStore allows."""
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError(f"Invalid object key: {key}")
    return key

class S3ObjectStore:
    """
    Files kept in one private S3 bucket by key, with the same methods as LocalObjectStore.
    
    Inputs:
    - bucket: bucket name
    - client: boto3 S3 client, or None to create one from the instance's region and credentials
    """
    
    def __init__(self, bucket:str, client:object=None) -> None:
        self.bucket = bucket
        self.client = client or boto3.client("s3")
    
    def put(self, key:str, data:bytes) -> None:
        try:
            self.client.put_object(Bucket=self.bucket, Key=_check_key(key), Body=data)
        except (BotoCoreError, ClientError) as error: #raised as OSError so the sidebar's file error handling covers S3
            raise OSError(f"Could not save {key} to S3: {error}") from error # from allows for traceback from OS error to Boto/Client Error
    
    def get(self, key:str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=_check_key(key))
            return response["Body"].read()
        except (BotoCoreError, ClientError) as error:
            raise OSError(f"Could not read {key} from S3: {error}") from error
    
    def delete(self, key:str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=_check_key(key)) #versioned bucket: adds a delete marker, old version expires after 30 days
        except (BotoCoreError, ClientError) as error:
            raise OSError(f"Could not delete {key} from S3: {error}") from error
