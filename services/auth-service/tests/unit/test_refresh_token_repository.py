from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.refresh_token_repository import RefreshTokenRepository


def test_get_by_jti_for_update_statement_avoids_outer_join() -> None:
    repository = RefreshTokenRepository()
    statement = repository._build_get_by_jti_for_update_stmt(uuid4())

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled).upper()

    assert "LEFT OUTER JOIN" not in sql
    assert " FOR UPDATE" in sql
