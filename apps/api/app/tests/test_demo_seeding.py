from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import verify_password
from app.db.base import Base
from app.db.session import DEMO_ACCOUNTS, seed_demo_accounts
from app.models.domain import User, UserRole


def _session_factory(tmp_path):
    database_path = tmp_path / "demo-seeding.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def test_seed_demo_accounts_creates_all_four_users_when_enabled(tmp_path):
    session_factory = _session_factory(tmp_path)

    seed_demo_accounts(enabled=True, session_factory=session_factory)

    with session_factory() as db:
        users = db.scalars(select(User).where(User.email.in_([account["email"] for account in DEMO_ACCOUNTS]))).all()

    assert len(users) == 4
    users_by_email = {user.email: user for user in users}
    for account in DEMO_ACCOUNTS:
        user = users_by_email[account["email"]]
        assert user.role == account["role"]
        assert user.full_name == account["full_name"]
        assert verify_password(account["password"], user.password_hash)


def test_seed_demo_accounts_does_not_duplicate_on_repeated_calls(tmp_path):
    session_factory = _session_factory(tmp_path)

    seed_demo_accounts(enabled=True, session_factory=session_factory)
    seed_demo_accounts(enabled=True, session_factory=session_factory)

    with session_factory() as db:
        users = db.scalars(select(User).where(User.email.in_([account["email"] for account in DEMO_ACCOUNTS]))).all()

    assert len(users) == 4


def test_seed_demo_accounts_does_not_seed_when_disabled(tmp_path):
    session_factory = _session_factory(tmp_path)

    seed_demo_accounts(enabled=False, session_factory=session_factory)

    with session_factory() as db:
        count = len(db.scalars(select(User)).all())

    assert count == 0


def test_seed_demo_accounts_does_not_overwrite_existing_users(tmp_path):
    session_factory = _session_factory(tmp_path)
    existing_email = "demo.admin@example.com"

    with session_factory() as db:
        db.add(
            User(
                email=existing_email,
                full_name="Existing Real Admin",
                role=UserRole.superadmin,
                password_hash="existing-hash",
                is_active=False,
            )
        )
        db.commit()

    seed_demo_accounts(enabled=True, session_factory=session_factory)

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == existing_email))

    assert user is not None
    assert user.full_name == "Existing Real Admin"
    assert user.role == UserRole.superadmin
    assert user.password_hash == "existing-hash"
    assert user.is_active is False
