from landar import storage
from landar.core.security import verify_password
from landar.providers.base import AuthProvider

class LocalAuthProvider(AuthProvider):
    name = "local"
    def authenticate(self, username, password):
        with storage.connect() as c:
            u = c.execute("SELECT status,pw_salt,pw_hash FROM users WHERE username=?", (username,)).fetchone()
        return bool(u and u["status"] == "Active" and u["pw_hash"] and verify_password(password, u["pw_salt"], u["pw_hash"]))
