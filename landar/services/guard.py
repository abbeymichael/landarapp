from landar import storage
from landar.core.permissions import Actor, PermissionDenied
from landar.services import audit

def require(actor: Actor, perm: str) -> None:
    """Call at the top of every service function. Denials are audited."""
    if not actor.can(perm):
        with storage.connect() as c:
            audit.record(c, actor.username, "permission_denied", perm, result="denied")
        raise PermissionDenied(f"'{actor.role}' lacks permission {perm}")
