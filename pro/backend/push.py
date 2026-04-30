"""Web Push 발송 — VAPID 자체 생성 키 + pywebpush.

플로우 (FN-EVENT-004):
  1. 환자 브라우저가 Service Worker 등록 → PushManager.subscribe()
  2. subscription endpoint·p256dh·auth → PushSubscription 테이블 저장
  3. 의료진/시스템이 send_push() 호출 → 등록된 모든 디바이스로 발송
  4. 브라우저 SW가 push 이벤트 수신 → showNotification

VAPID 키 영속:
  - setup.sh가 1회 생성 (cryptography ec.SECP256R1)
  - .env의 VAPID_PUBLIC_KEY/PRIVATE_KEY로 저장
  - 재생성하면 기존 구독 모두 무효화 → 1회 고정 운영

오류 처리:
  - VAPID 미설정: 즉시 0건 + error 메시지 반환 (환경변수 누락 알림)
  - WebPushException: 디바이스별 endpoint+에러 메시지를 failed에 누적
  - 기타 예외: 클래스명+메시지로 failed에 기록 (호출자가 표시)
"""
import json
from typing import Optional
from pywebpush import webpush, WebPushException
from sqlmodel import Session, select
from config import settings
from models import PushSubscription, engine


def send_push(
    patient_id: str,
    title: str,
    body: str,
    url: Optional[str] = None,
) -> dict:
    """환자에게 등록된 모든 Web Push 구독으로 발송.

    Returns: {"sent": N, "failed": [{endpoint, error}, ...]}
    """
    if not settings.VAPID_PRIVATE_KEY:
        return {"sent": 0, "failed": [],
                "error": "VAPID_PRIVATE_KEY 미설정. setup.sh 재실행 필요"}

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/",
        "icon": "/icon-192.png",
        "badge": "/badge-72.png",
    })

    sent = 0
    failed = []
    with Session(engine) as session:
        subs = session.exec(
            select(PushSubscription).where(PushSubscription.patient_id == patient_id)
        ).all()
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                )
                sent += 1
            except WebPushException as e:
                failed.append({"endpoint": sub.endpoint[:60], "error": str(e)})
            except Exception as e:
                failed.append({"endpoint": sub.endpoint[:60],
                               "error": f"{type(e).__name__}: {e}"})

    return {"sent": sent, "failed": failed}
