from sqlalchemy.exc import IntegrityError


def is_users_email_unique_violation(exc: IntegrityError) -> bool:
    """判断是否为 users.email 唯一约束冲突（PostgreSQL / asyncpg）。"""
    orig = exc.orig
    seen: set[int] = set()
    while orig is not None and id(orig) not in seen:
        seen.add(id(orig))
        cn = getattr(orig, "constraint_name", None)
        if cn and "email" in str(cn).lower():
            return True
        if getattr(orig, "table_name", None) == "users" and getattr(orig, "column_name", None) == "email":
            return True
        if getattr(orig, "sqlstate", None) == "23505":
            msg = (str(orig) + str(getattr(orig, "detail", ""))).lower()
            if "email" in msg or "users_email" in msg or "ix_users_email" in msg:
                return True
        orig = getattr(orig, "__cause__", None) or getattr(orig, "__context__", None)

    msg = str(exc).lower()
    return "email" in msg and ("unique" in msg or "duplicate" in msg)
