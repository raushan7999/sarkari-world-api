"""User ORM model, mapped onto the Prisma-managed `"User"` table."""

from datetime import datetime

from sqlalchemy import CHAR, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.enums import StateName, UserRole


class User(Base):
    __tablename__ = "User"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    other_email: Mapped[str | None] = mapped_column(String(255), unique=True)
    mobile: Mapped[str | None] = mapped_column(String(10))
    other_mobile: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    # Must use the native enum type: binding this column as text makes every
    # INSERT fail with "column state is of type StateName but expression is of
    # type character varying".
    state: Mapped[StateName | None] = mapped_column(
        Enum(
            StateName,
            name="StateName",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    pin: Mapped[str | None] = mapped_column(CHAR(6))
    address: Mapped[str | None] = mapped_column(String(500))

    google_id: Mapped[str | None] = mapped_column(Text, unique=True)
    picture_url: Mapped[str | None] = mapped_column(Text)
    auth_provider: Mapped[str] = mapped_column(Text, default="subscription")
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="UserRole",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=UserRole.USER,
    )

    # Legacy plaintext column, never read at runtime. Never serialised.
    api_key: Mapped[str | None] = mapped_column(Text, unique=True)
    api_key_prefix: Mapped[str | None] = mapped_column(Text, unique=True)
    api_key_hash: Mapped[str | None] = mapped_column(Text)
    api_key_name: Mapped[str | None] = mapped_column(Text)
    api_key_created_at: Mapped[datetime | None]
    api_key_last_used_at: Mapped[datetime | None]
    api_key_revoked_at: Mapped[datetime | None]

    last_login_at: Mapped[datetime | None]
    # The only timezone-aware column in the schema.
    session_invalidated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
