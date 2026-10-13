from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import AppSetting


def get_setting(db: Session, key: str) -> Optional[str]:
    row = db.get(AppSetting, key)
    return row.value if row else None


def set_setting(db: Session, key: str, value: Optional[str]) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def delete_settings(db: Session, *keys: str) -> None:
    db.query(AppSetting).filter(AppSetting.key.in_(keys)).delete(synchronize_session=False)
    db.commit()
