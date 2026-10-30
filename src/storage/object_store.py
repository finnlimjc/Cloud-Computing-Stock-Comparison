from pathlib import Path

class LocalObjectStore:
    """
    Files kept under one folder by key, with the same methods as the planned S3 store.
    
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
