"""VAPID 키 1회 생성 (Web Push) — 결과를 Render·Vercel 환경변수에 입력.

사용:
  python3 backend/scripts/gen_vapid.py
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def main():
    priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pub = priv.public_key()

    priv_bytes = priv.private_numbers().private_value.to_bytes(32, "big")
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    priv_b64 = base64.urlsafe_b64encode(priv_bytes).decode().rstrip("=")
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).decode().rstrip("=")

    print()
    print("═══════════════════════════════════════════")
    print("  VAPID 키 — 한 번만 생성, 영구 보관")
    print("═══════════════════════════════════════════")
    print()
    print("Render Backend 환경변수에 입력:")
    print(f"  VAPID_PUBLIC_KEY={pub_b64}")
    print(f"  VAPID_PRIVATE_KEY={priv_b64}")
    print()
    print("Vercel Patient/Admin App 환경변수에 입력:")
    print(f"  NEXT_PUBLIC_VAPID_PUBLIC_KEY={pub_b64}")
    print()


if __name__ == "__main__":
    main()
