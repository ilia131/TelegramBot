from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HiddifyUser:
    external_id: str
    quota_gb: float
    used_gb: float
    expires_at: datetime
    enabled: bool


class HiddifyAdapter:
    """Contract for a version-verified panel client."""

    async def create_user(self, *, order_id: int, name: str, quota_gb: int,
                          duration_days: int) -> HiddifyUser:
        raise NotImplementedError

    async def set_quota(self, external_id: str, quota_gb: int) -> HiddifyUser:
        raise NotImplementedError

    async def set_expiration(self, external_id: str, expires_at: datetime) -> HiddifyUser:
        raise NotImplementedError

    async def subscription_url(self, external_id: str) -> str:
        raise NotImplementedError

    async def usage(self, external_id: str) -> float:
        raise NotImplementedError

    async def user_info(self, external_id: str) -> HiddifyUser:
        raise NotImplementedError

    async def disable(self, external_id: str) -> HiddifyUser:
        raise NotImplementedError

    async def renew(self, external_id: str, *, quota_gb: int, duration_days: int) -> HiddifyUser:
        raise NotImplementedError
