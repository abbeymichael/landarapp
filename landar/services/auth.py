import secrets
from landar import storage
from landar.core.permissions import Actor
from landar.core.security import hash_password
from landar.providers.registry import AUTH_PROVIDERS
from landar.services import audit

def bootstrap_admin():
    """Create the first admin with a random one-time password. Returns it, or None if users exist."""
    with storage.connect() as c:
        if c.execute("SELECT 1 FROM users LIMIT 1").fetchone(): return None
        pw = secrets.token_urlsafe(12); salt, h = hash_password(pw)
        c.execute("""INSERT INTO users(username,full_name,group_id,role_id,pw_salt,pw_hash,created_at) VALUES('admin','Administrator',
                     (SELECT id FROM groups WHERE name='Administrators'),(SELECT id FROM roles WHERE name='Super Administrator'),?,?,?)""",
                  (salt, h, audit.now()))
        audit.record(c, "system", "seed_admin", "admin")
        return pw

def login(username, password) -> Actor | None:
    for p in AUTH_PROVIDERS:
        if p.authenticate(username, password):
            with storage.connect() as c:
                role = c.execute("SELECT r.name FROM users u JOIN roles r ON r.id=u.role_id WHERE username=?", (username,)).fetchone()
                if role:
                    audit.record(c, username, "login", username, source=p.name)
                    return Actor(username, role[0])
    with storage.connect() as c:
        audit.record(c, username, "login", username, result="failure")
    return None
