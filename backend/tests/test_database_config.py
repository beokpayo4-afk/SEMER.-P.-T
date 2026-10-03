from app.core.config import Settings, normalize_database_url


def test_database_url_rewrites_postgres_schemes() -> None:
    assert normalize_database_url("postgres://db.example/semer") == "postgresql+psycopg://db.example/semer"
    assert normalize_database_url("postgresql://db.example/semer") == "postgresql+psycopg://db.example/semer"
    try:
        normalize_database_url("  ")
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("An empty database URL should be rejected")


def test_pytest_uses_test_database_url_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/semer")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://localhost/semer_test")
    configured = Settings(_env_file=None)

    assert configured.sqlalchemy_database_url == "postgresql+psycopg://localhost/semer"
    assert configured.sqlalchemy_test_database_url == "postgresql+psycopg://localhost/semer_test"


def test_pytest_falls_back_to_the_application_database(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/semer")
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    configured = Settings(_env_file=None)

    assert configured.sqlalchemy_test_database_url == configured.sqlalchemy_database_url
