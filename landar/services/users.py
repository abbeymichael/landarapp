import sqlite3
from landar import config, storage
from landar.core.security import hash_password
from landar.services import audit
from landar.services.guard import require

def list_users(actor):
    require(actor, "users.view")
    with storage.connect() as c:
        return c.execute("""SELECT u.id,u.username,u.full_name,u.email,g.name,r.name,u.status FROM users u
                            LEFT JOIN groups g ON g.id=u.group_id LEFT JOIN roles r ON r.id=u.role_id ORDER BY u.id""").fetchall()

def create_user(actor, username, full_name, email, group, role, password):
    require(actor, "users.create")
    if not username or not full_name: raise ValueError("Username and full name are required")
    if len(password) < config.MIN_PASSWORD_LEN: raise ValueError(f"Password must be at least {config.MIN_PASSWORD_LEN} characters")
    salt, h = hash_password(password)
    with storage.connect() as c:
        try:
            c.execute("""INSERT INTO users(username,full_name,email,group_id,role_id,pw_salt,pw_hash,created_at) VALUES(?,?,?,
                         (SELECT id FROM groups WHERE name=?),(SELECT id FROM roles WHERE name=?),?,?,?)""",
                      (username, full_name, email, group, role, salt, h, audit.now()))
        except sqlite3.IntegrityError: raise ValueError(f"Username '{username}' already exists")
        audit.record(c, actor.username, "user_created", username, new=f"group={group}, role={role}")

def set_status(actor, user_id, status):
    require(actor, "users.edit")
    with storage.connect() as c:
        u = c.execute("SELECT username,status FROM users WHERE id=?", (user_id,)).fetchone()
        if u["username"] == actor.username: raise ValueError("You cannot change your own account status")
        c.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
        audit.record(c, actor.username, "user_status_changed", u["username"], old=u["status"], new=status)
