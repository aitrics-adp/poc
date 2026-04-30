/**
 * Web Push 구독 헬퍼 (FN-EVENT-004).
 *
 * 흐름:
 *   1. Service Worker 등록 (`/sw.js`)
 *   2. Notification 권한 요청 (사용자 승인 필요)
 *   3. 백엔드에서 VAPID 공개키 fetch
 *   4. PushManager.subscribe() — 브라우저가 endpoint·키 발급
 *   5. 백엔드 `/api/push/subscribe` 로 등록 (환자별 매핑)
 *
 * 반환 status:
 *   - subscribed   정상 구독 완료
 *   - already      이미 구독된 endpoint (백엔드가 patient_id만 갱신)
 *   - denied       사용자가 알림 권한 거부 (브라우저 자물쇠 → 알림 → 허용 필요)
 *   - unsupported  브라우저가 ServiceWorker/PushManager 미지원
 *   - error        VAPID 키 미설정 등 기타 오류
 *
 * HTTPS 필수 — localhost는 예외적으로 HTTP 허용 (Chrome).
 */
import { api } from "./api";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const arr = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) arr[i] = rawData.charCodeAt(i);
  return arr;
}

export async function registerPush(patient_id: string): Promise<{
  status: "subscribed" | "denied" | "unsupported" | "already" | "error";
  message?: string;
}> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return { status: "unsupported", message: "이 브라우저는 푸시 미지원" };
  }
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    const permission = await Notification.requestPermission();
    if (permission !== "granted")
      return { status: "denied", message: "알림 권한 거부됨" };

    const { public_key } = await api.vapidKey();
    if (!public_key)
      return { status: "error", message: "VAPID 키 미설정 (setup.sh 재실행)" };

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
    const json = sub.toJSON();
    await api.pushSubscribe({
      patient_id,
      endpoint: json.endpoint!,
      p256dh: json.keys!.p256dh!,
      auth: json.keys!.auth!,
    });
    return { status: "subscribed" };
  } catch (e: any) {
    return { status: "error", message: e?.message ?? String(e) };
  }
}
