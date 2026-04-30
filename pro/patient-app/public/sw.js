// Web Push Service Worker (FN-EVENT-004 환자앱 측 receiver)
//
// 라이프사이클:
//   install  — 즉시 활성 (skipWaiting). 기존 SW 빠르게 대체.
//   activate — 모든 페이지 즉시 제어 (clients.claim).
//   push     — 백엔드 webpush가 보낸 페이로드 → showNotification.
//   notificationclick — 알림 클릭 시 지정 URL 새 창으로 열기.
//
// 페이로드 형식 (backend/push.py와 일치):
//   { title, body, url, icon?, badge? }
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  const data = (() => { try { return event.data.json(); } catch { return {}; } })();
  const title = data.title || "TRI-PRO";
  const options = {
    body: data.body || "",
    icon: data.icon || "/icon-192.png",
    badge: data.badge || "/badge-72.png",
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(self.clients.openWindow(url));
});
