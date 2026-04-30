# TRI-PRO POC 배포 체크리스트

외부에 URL만 공유해서 시연·체험할 수 있게 배포하기 위한 전체 정리.

---

## 1. 추천 배포 구성 (가장 빠름·저렴)

```
┌─ Patient App (Next.js) ──┐    ┌─ Admin App (Next.js) ──┐
│  Vercel · 무료            │    │  Vercel · 무료          │
│  patient.vercel.app      │    │  admin.vercel.app      │
└──────────┬───────────────┘    └──────────┬─────────────┘
           │                                │
           └──────────┬─────────────────────┘
                      ↓ HTTPS
              ┌─── Backend (FastAPI) ───┐
              │  Render Web Service     │
              │  api.onrender.com       │
              │  + Postgres 무료 1GB    │
              └─────────────────────────┘
```

월 비용: **무료 ~ $1** (Render persistent disk 사용 시)
첫 cold start: 30~50초 (Render 무료) — 시연 직전 1회 호출 권장

---

## 2. 코드 변경 필수 항목

### 2.1 Backend

| 항목 | 현재 | 배포용 변경 |
|---|---|---|
| **CORS** | `localhost:3000/3001` 허용 | production 도메인 추가 |
| **DB** | SQLite `dev.db` | Postgres or SQLite + persistent disk |
| **VAPID 키** | `setup.sh`로 매번 생성 | 환경변수로 주입 |
| **server runner** | `uvicorn --reload` | `gunicorn -k uvicorn.workers.UvicornWorker -w 2` |
| **DB 초기화** | `seed.py` 수동 | `startup` 이벤트에서 자동 |
| **Health check** | `/api/health` ✓ 이미 있음 | 그대로 |
| **로그** | stdout | 그대로 (Render 자동 수집) |

**구체 변경:**

`backend/config.py` (이미 환경변수 기반이지만 확인):
```python
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./dev.db"
    LLM_MODE: str = "mock"
    ANTHROPIC_API_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@aitrics.com"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    @property
    def cors_list(self):
        return self.CORS_ORIGINS.split(",")
```

`backend/main.py` startup에 시드 자동 실행 (있으면 스킵):
```python
@app.on_event("startup")
def on_startup():
    init_db()
    from sqlmodel import Session, select
    with Session(engine) as s:
        if not s.exec(select(Patient)).first():
            from seed import seed
            seed()
```

`backend/requirements.txt` 추가:
```
gunicorn==23.0.0
psycopg2-binary==2.9.10  # Postgres 사용 시
```

### 2.2 Patient App + Admin App (Next.js)

| 항목 | 현재 | 배포용 변경 |
|---|---|---|
| **API URL** | `process.env.NEXT_PUBLIC_API_URL` ✓ | Vercel 환경변수에 주입 |
| **VAPID 공개키** | runtime fetch (`/api/push/vapid-public-key`) ✓ | 그대로 OK |
| **빌드** | `next dev` | `next build && next start` |
| **HTTPS** | localhost (HTTP OK) | **HTTPS 필수** (Web Push, Service Worker) |
| **Service Worker** | `/public/sw.js` | basePath 영향 — Vercel은 root이므로 그대로 OK |

각 앱 루트에 `vercel.json`:
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "env": {
    "NEXT_PUBLIC_API_URL": "@tri_pro_api_url"
  }
}
```

---

## 3. 환경변수 매트릭스

### Backend (Render)
| 키 | 예시 | 비고 |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` 또는 `sqlite:///./data/prod.db` | Render이 Postgres 자동 생성 시 자동 주입 |
| `LLM_MODE` | `mock` | 자체 모델 연동 시 `real` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | LLM_MODE=real일 때만 |
| `VAPID_PUBLIC_KEY` | `BC...` | 1회 생성해서 고정 (1️⃣) |
| `VAPID_PRIVATE_KEY` | `Hf...` | 1️⃣과 페어 |
| `VAPID_SUBJECT` | `mailto:admin@aitrics.com` | RFC 8030 |
| `CORS_ORIGINS` | `https://patient.vercel.app,https://admin.vercel.app` | 콤마 구분 |
| `PORT` | `10000` | Render이 자동 할당 |

VAPID 키 1회 생성:
```bash
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
pub = priv.public_key()
priv_b = priv.private_numbers().private_value.to_bytes(32, 'big')
pub_b = pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
print('PUBLIC=' + base64.urlsafe_b64encode(pub_b).decode().rstrip('='))
print('PRIVATE=' + base64.urlsafe_b64encode(priv_b).decode().rstrip('='))
"
```

### Frontend (Vercel — patient/admin 공통)
| 키 | 예시 |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://tri-pro-api.onrender.com` |

---

## 4. 보안 — 외부 공유 시 필수

현재 POC는 **인증 없음** + 환자 데이터 노출. 외부 공유면 최소 다음 중 하나:

### 옵션 A: Basic Auth (가장 빠름, 5분)
- 어드민·환자앱 둘 다 Vercel Password Protection (Pro $20/월) 또는
- Cloudflare Access 무료 티어 (이메일 인증)

### 옵션 B: 토큰 헤더 (개발 가능, 30분)
- backend FastAPI에 `Depends(verify_token)` 추가
- 프론트엔드에서 `Authorization: Bearer <demo-token>` 자동 주입
- demo-token은 환경변수로

### 옵션 C: 가짜 데이터만 (가장 안전)
- 현재 합성 환자 5명 모두 실제 인물 아님 → 그대로 공유 가능
- caregiver_phone은 `010-0000-0000` 더미 OK
- 외부 사용자가 직접 만든 응답·메시지가 누적되니 주기적 reset 필요

**POC 수준이면 옵션 C + Basic Auth 조합 충분.**

기타 체크:
- [ ] HTTPS 강제 (Render·Vercel 자동)
- [ ] Rate limit (선택, slowapi 미들웨어)
- [ ] PII 마스킹 ✓ 이미 구현
- [ ] LLM 응답 audit ✓ 이미 구현
- [ ] DB 백업 (Render Postgres 일별 자동 백업, 무료 티어는 7일 보존)

---

## 5. 데이터·DB 전환

### SQLite 그대로 (가장 쉬움)
**조건**: Render persistent disk 1GB ($1/월)
- `DATABASE_URL=sqlite:///./data/prod.db`
- `data/` 디렉토리를 disk에 마운트
- **장점**: 코드 0줄 변경
- **단점**: cold start 시 컨테이너 재시작 → 디스크 마운트 후 접근 (1~2초 추가)

### Postgres 전환 (확장성·다중 워커)
- `DATABASE_URL=postgresql://...`
- `requirements.txt`에 `psycopg2-binary` 추가
- **변경 거의 없음** — SQLModel은 둘 다 호환
- **장점**: 다중 워커 동시 쓰기 안전
- **단점**: 첫 마이그레이션 시 schema 차이 점검 필요 (Text 길이 등)

### 시드 데이터 처리
배포 후 첫 부팅 시 `Patient` 테이블 비어있으면 자동 시드:
```python
@app.on_event("startup")
def on_startup():
    init_db()
    with Session(engine) as s:
        if not s.exec(select(Patient).limit(1)).first():
            print("📦 첫 부팅 — 시드 데이터 생성")
            from seed import seed
            seed()
```

DB reset이 필요하면 `/api/admin/reset-db` 같은 보호된 엔드포인트 추가 (옵션).

---

## 6. 단계별 배포 가이드 (Render + Vercel)

### Step 1. GitHub 푸시 (5분)
```bash
cd ~/poc/tri-pro-poc
git init
git add .
git commit -m "POC v1.0"
gh repo create tri-pro-poc --private --source=. --push
```
`.gitignore`:
```
backend/venv/
backend/dev.db
backend/__pycache__/
**/node_modules/
**/.next/
.logs/
.pids/
.env
demo/screenshots/
demo/videos/
```

### Step 2. Backend → Render (10분)
1. [render.com](https://render.com) 가입 (GitHub 연동)
2. **New → Web Service** → 리포 선택
3. 설정:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:$PORT main:app`
   - **Plan**: Starter $7/월 (또는 무료 — cold start 있음)
4. **Environment**: 위 환경변수 표 입력
5. (선택) Postgres 추가 → `DATABASE_URL` 자동 주입

또는 `render.yaml` 한 번에:
```yaml
services:
  - type: web
    name: tri-pro-api
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:$PORT main:app
    envVars:
      - key: LLM_MODE
        value: mock
      - key: VAPID_PUBLIC_KEY
        sync: false
      - key: VAPID_PRIVATE_KEY
        sync: false
      - key: CORS_ORIGINS
        value: https://tri-pro-patient.vercel.app,https://tri-pro-admin.vercel.app
    disk:
      name: data
      mountPath: /opt/render/project/src/backend/data
      sizeGB: 1
databases:
  - name: tri-pro-db
    plan: free
```

### Step 3. Patient App → Vercel (5분)
1. [vercel.com](https://vercel.com) 로그인
2. **New Project** → 리포 import → **Root Directory: `patient-app`**
3. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL=https://tri-pro-api.onrender.com`
4. Deploy

### Step 4. Admin App → Vercel (5분)
같은 리포에서 별도 프로젝트로:
- **Root Directory: `admin-app`**
- 같은 `NEXT_PUBLIC_API_URL`

### Step 5. CORS 업데이트 (3분)
Vercel 도메인 두 개를 backend `CORS_ORIGINS` 환경변수에 추가 → Render 자동 재배포

### Step 6. Web Push 검증 (5분)
- 배포된 환자앱에서 푸시 구독 클릭
- HTTPS이므로 Service Worker 등록 OK
- 어드민에서 발송 → 알림 수신 확인

---

## 7. 대안 — Docker Compose (사내·VPS)

`docker-compose.yml` (프로젝트 루트):
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/tripro
      VAPID_PUBLIC_KEY: ${VAPID_PUBLIC_KEY}
      VAPID_PRIVATE_KEY: ${VAPID_PRIVATE_KEY}
      CORS_ORIGINS: http://localhost:3000,http://localhost:3001
    depends_on: [db]
  patient:
    build: ./patient-app
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
  admin:
    build: ./admin-app
    ports: ["3001:3001"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: tripro
    volumes: [pgdata:/var/lib/postgresql/data]
volumes:
  pgdata:
```

`backend/Dockerfile`, `patient-app/Dockerfile`, `admin-app/Dockerfile` 추가 필요.

받는 사람: `docker compose up` 1줄.

---

## 8. 비용 예상

| 구성 | 월 비용 | 트래픽 | cold start |
|---|---|---|---|
| Vercel(2개) + Render free | $0 | 100GB/월 | 30~50s |
| Vercel + Render Starter | $7 | 100GB | 없음 |
| Vercel + Render + Disk | $8 | 100GB | 없음 |
| VPS DigitalOcean $6 | $6 | 1TB | 없음 |
| Fly.io free | $0 | 적음 | 1~3s |

**POC 데모 1주~1개월 공유**: Render free + Vercel = $0 (cold start 양해)
**프리뷰 환경 상시 운영**: Render Starter $7/월

---

## 9. 운영 체크리스트

배포 후:
- [ ] `/api/health` 200 OK
- [ ] `/api/admin/dashboard` 5명 환자 반환
- [ ] 환자앱·어드민 화면 모두 렌더링
- [ ] CORS 에러 없음 (브라우저 콘솔)
- [ ] Web Push 구독·발송 왕복 OK
- [ ] LLM Free Talk 5종 가드레일 동작
- [ ] Web Vitals (선택) — Vercel Analytics 무료 티어
- [ ] 에러 알림 — Sentry 무료 티어 ($0, 5K events/월)
- [ ] DB 자동 백업 — Render Postgres 일별

---

## 10. 외부 공유 메시지 템플릿

```
안녕하세요,

TRI-PRO POC 시연 환경 공유드립니다.

🏥 의료진 어드민:  https://tri-pro-admin.vercel.app
📱 환자앱:        https://tri-pro-patient.vercel.app

데모 환자 5명 (C-1042, C-2103, C-3027, C-4581, C-5219)이 미리 준비돼 있어
바로 클릭해서 보실 수 있습니다.

주요 시연 포인트:
• 의료진 대시보드 → C-1042 Pre-Visit Report → 일별 PRO 응답
• PRO 도구 라이브러리 → 5종 도구 + 커스텀 세트 빌더
• 환자앱 → /pro/start → Full/Quick/NoChange 모드
• 어르신 모드 → 얼굴 척도
• Free Talk → 4종 가드레일 (응급/Out-of-Scope/Education/PII 마스킹)

* LLM은 Mock 모드입니다 (응답 결정론 템플릿).
* 첫 접속 시 백엔드 wake up에 30~40초 걸릴 수 있습니다.
* 합성 데이터입니다 — 실제 환자 정보 아님.

피드백은 언제든 환영입니다.
```

---

## 11. 중장기 (POC → MVP 전환 시)

| 항목 | POC | MVP |
|---|---|---|
| 인증 | 없음 / Basic Auth | OAuth + RBAC |
| DB | SQLite/Postgres | Postgres + 마이그레이션 (Alembic) |
| 푸시 | 자체 VAPID | FCM/APNs (모바일 네이티브) |
| 백엔드 | 단일 인스턴스 | 다중 워커 + Redis 세션 |
| LLM | Mock | 자체 모델 (vLLM·Ollama) 또는 Anthropic API |
| 모니터링 | 로그만 | Sentry + Datadog/Grafana |
| CI/CD | git push | GitHub Actions + 환경별 배포 |
| 인프라 | Render+Vercel | AWS ECS/EKS or Kubernetes |
| 컴플라이언스 | 합성 데이터 | HIPAA/GDPR (의료 데이터 시) |
| 백업 | 플랫폼 자동 | 다중 지역 복제 |
