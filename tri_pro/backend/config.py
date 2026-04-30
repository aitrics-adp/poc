"""환경 설정 — pydantic-settings 기반.

로드 순서 (뒤가 우선):
  1. 클래스 기본값
  2. 프로젝트 루트 `.env` 파일
  3. OS 환경 변수 (배포 시 주로 이쪽)

운영 환경에서는 .env를 안 두고 환경변수로만 주입하는 게 안전 (시크릿 관리).
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트의 .env 사용 (backend/ 의 부모)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """전역 설정. `from config import settings` 로 접근."""

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), extra="ignore")

    # ── LLM ────────────────────────────────────────
    LLM_MODE: str = "mock"               # "mock" | "real"
    ANTHROPIC_API_KEY: str = ""          # LLM_MODE=real 일 때만 필요

    # ── DB ─────────────────────────────────────────
    # SQLite (POC 기본): sqlite:///./dev.db
    # Postgres (운영):   postgresql://user:pass@host/db
    DATABASE_URL: str = "sqlite:///./dev.db"

    # ── 네트워크 ────────────────────────────────────
    BACKEND_PORT: int = 8000
    # 콤마 구분된 도메인 — Vercel·Render 배포 시 production URL 추가
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # ── Web Push (VAPID) ───────────────────────────
    # setup.sh가 1회 생성 후 .env에 저장. 재생성하면 기존 구독 모두 무효.
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:tri-pro-poc@aitrics.com"

    @property
    def cors_list(self) -> list[str]:
        """CORS_ORIGINS 콤마 구분 문자열을 list로 파싱."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
