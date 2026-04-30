# [요청] TRI-PRO POC 시연 환경 — AWS 인프라

| 항목 | 내용 |
|---|---|
| **요청자** | 정주용 (Agent Framework Lead, ADP) |
| **요청일** | 2026-04-30 |
| **프로젝트** | TRI-PRO POC (TRI-Agentic AI 표준 PRO 엔진) |
| **목적** | 내부 PI·임상 시연 + 외부 의료진 피드백 수집 |
| **사용 기간** | 2주 ~ 1개월 (POC 검증 종료 시 회수) |
| **참고 위키** | https://aitrics.atlassian.net/wiki/spaces/ADP/pages/1738637481 |

---

## 1. 한 줄 요약

> POC로 개발 완료된 환자앱·의료진 어드민·백엔드(FastAPI) 3개 서비스를
> AWS 단일 EC2 인스턴스(Docker Compose)에 배포해 외부 시연용 URL을 확보하고자 합니다.

---

## 2. 배경

- C-Rehab(외래 항암환자) PRO(Patient-Reported Outcome) 자동 수집 솔루션 POC.
- FSD 74개 기능 중 P0 모두 구현, 백엔드 90/90 단위테스트 통과.
- 합성 환자 5명·LLM Mock 모드로 동작 — **실제 환자 PII 없음**.
- 현재 로컬에서 검증 완료, 외부 의료진(임상 자문)에게 보여줄 환경 필요.

---

## 3. 필요 리소스 (요약)

| # | 리소스 | 사양·옵션 | 추정 비용/월 |
|---|---|---|---|
| 1 | EC2 인스턴스 | **t3.small** (2 vCPU, 2GB RAM) | ~$15 |
| 2 | EBS 스토리지 | 16GB gp3 | ~$1.5 |
| 3 | Elastic IP | 1개 (인스턴스에 연결 시 무료) | $0 |
| 4 | 보안 그룹 | 신규 1개 (`tri-pro-poc-sg`) | $0 |
| 5 | 키 페어 | 신규 1개 (`tri-pro-poc-key`) | $0 |
| 6 | 도메인·서브도메인 | (선택) 3개 — 6.2 참조 | 도메인 보유 시 $0 |
| **합계** |  |  | **~$17/월** |

> POC 종료 후(약 1개월) 즉시 회수 → 누적 비용 약 $17.

---

## 4. 상세 사양

### 4.1 EC2 인스턴스

| 항목 | 값 |
|---|---|
| 인스턴스 타입 | **t3.small** (Burstable, 2 vCPU, 2GiB RAM) |
| AMI | Amazon Linux 2023 (`al2023-ami-*-x86_64`) |
| 리전 | **ap-northeast-2 (서울)** |
| 가용영역 | 무관 (단일 AZ로 충분, POC) |
| 스토리지 | 16GB gp3 EBS (Boot) |
| 자동 시작 | 활성 |
| 모니터링 | CloudWatch Basic (무료 티어) |
| 태그 | `Project=TRI-PRO-POC`, `Owner=jy.jeong@aitrics.com`, `CostCenter=ADP-RnD`, `Environment=poc` |

**선택 근거**: 백엔드(FastAPI gunicorn 2 worker) + Next.js 2개(prod build) + Postgres + Caddy = 약 1.4GB RAM 사용. t3.micro(1GB)는 빌드 시 OOM 발생 확인됨.

### 4.2 EBS

- 16GB gp3 (3000 IOPS 기본, 충분)
- 종료 시 함께 삭제(Terminate on instance delete) — POC라 데이터 보존 불필요

### 4.3 보안 그룹 (신규)

| 이름 | `tri-pro-poc-sg` |
|---|---|
| 인바운드 | |
| - SSH (22) | **요청자 IP만** (`<jy.jeong 사무실/재택 IP>/32`) |
| - HTTP (80) | `0.0.0.0/0` (Caddy → HTTPS 자동 리다이렉트) |
| - HTTPS (443) | `0.0.0.0/0` |
| 아웃바운드 | All (기본) |

> SSH 22번을 절대 `0.0.0.0/0`으로 열지 않습니다.

### 4.4 Elastic IP

- 1개 할당 → 인스턴스에 즉시 연결
- 재시작해도 IP 고정 → 도메인 DNS 안정성

### 4.5 키 페어

- `tri-pro-poc-key.pem` 신규 발급 → 요청자에게 안전 채널(1Password / 사내 secure share)로 전달

### 4.6 도메인 (택1)

**옵션 A: 사내 도메인 사용 (권장)**
- `aitrics.com` 또는 보유 중인 도메인의 서브도메인 3개:
  - `tripro-patient.aitrics.com`  → 환자앱
  - `tripro-admin.aitrics.com`    → 의료진 어드민
  - `tripro-api.aitrics.com`      → 백엔드 API
- A 레코드를 Elastic IP로 가리키도록 Route 53 또는 사내 DNS 설정
- HTTPS 인증서: Caddy가 Let's Encrypt 자동 발급 (인프라팀 작업 X)

**옵션 B: 도메인 없이 진행**
- 별도 비용·DNS 작업 0건
- `nip.io` 활용: `<EIP>.nip.io` 형식으로 자동 라우팅
- 단점: URL이 IP 노출형이라 외부 발표용으론 미관 ↓

> 옵션 A가 가능하면 그쪽 권장. 안 되면 B로 진행 가능.

---

## 5. 보안·컴플라이언스

| 항목 | 내용 |
|---|---|
| 환자 데이터 | **합성 5명만 사용** — 실제 환자 PII·진료 정보 0건 |
| 인증 | POC 단계 — 별도 인증 미적용 (도메인 알아야 접근). MVP 진입 시 SSO 추가 |
| HTTPS | Caddy 자동 (Let's Encrypt) |
| 시크릿 | DB 패스워드·VAPID 키 등 모두 EC2 내 `.env`에 저장. AWS Secrets Manager 미사용 (POC) |
| 백업 | 불필요 (합성 데이터, POC) |
| 로그 | EC2 stdout → docker compose logs. CloudWatch 연동 미요청 |
| 외부 의존성 | 없음 (LLM Mock 모드, 외부 API 호출 0) |
| 감사 추적 | 백엔드 내부에 audit_log 테이블로 자체 기록 |

---

## 6. 운영·관리

| 항목 | 책임 |
|---|---|
| 배포·재배포 | 요청자 (스크립트로 1줄 실행) |
| 코드 변경 | 요청자 (git push → ssh → deploy.sh) |
| 모니터링 | 요청자 (CloudWatch Basic 충분) |
| 장애 대응 | 요청자 (POC, 야간 무대응 OK) |
| **회수 책임** | 요청자가 POC 종료 시 종료 신청 |

---

## 7. 일정

| 시점 | 작업 | 담당 |
|---|---|---|
| D-day | 인프라 준비 (EC2·EIP·SG·키페어·도메인) | **인프라팀** |
| D+0 | EC2 ssh 접속 + 배포 | 요청자 |
| D+0 | 시연 URL 외부 공유 | 요청자 |
| D+30 | POC 종료 — 인스턴스 종료 신청 | 요청자 |

---

## 8. 인프라팀 요청사항 — 체크리스트

```
[ ] 1. EC2 인스턴스 생성 (위 4.1 사양)
[ ] 2. EBS 16GB gp3 연결
[ ] 3. Elastic IP 할당 + 연결
[ ] 4. 보안 그룹 tri-pro-poc-sg 생성 + 위 4.3 규칙 적용
[ ] 5. 키 페어 tri-pro-poc-key.pem 발급 → 요청자 전달 (secure)
[ ] 6. (옵션 A 선택 시) 서브도메인 3개 A레코드 → Elastic IP
[ ] 7. 태그 4종 부착 (Project / Owner / CostCenter / Environment)
[ ] 8. 요청자에게 회신 (아래 9번 정보)
```

---

## 9. 회신 받을 정보

```
Public IP (Elastic IP):  ___________________________
Private IP:              ___________________________
인스턴스 ID:            i-_________________________
보안 그룹 ID:           sg-________________________
키 페어 전달 방식:       (1Password / 사내 share / 기타: ____)
도메인 옵션:             [ ] A (사내 도메인 + DNS 완료) — 도메인: __________________
                        [ ] B (도메인 없이, nip.io 사용)
회수 예정일:             ___________________________
담당 인프라 엔지니어:    ___________________________
```

회신 받는 즉시 EC2 ssh 접속 → 배포 스크립트 실행하여 같은 날 시연 URL 가동 가능.

---

## 10. 추후 (POC → MVP 전환 시) 변경 예정

POC 검증 후 MVP로 진화 시 다음 변경 예상 (현재 요청에는 미포함):

- RDS Postgres (현재 SQLite + 단일 컨테이너)
- ECS Fargate / EKS (현재 단일 EC2)
- Application Load Balancer + Auto Scaling
- AWS Secrets Manager
- CloudWatch Logs + Sentry
- WAF + CloudFront
- 다중 환경 (dev / staging / prod)
- IAM Identity Center (SSO)
- VPC 분리

---

## 11. 문의

- **요청자**: 정주용 (jy.jeong@aitrics.com)
- **Slack**: @jy.jeong
- **Wiki**: [TRI-PRO MVP 폴더](https://aitrics.atlassian.net/wiki/spaces/ADP/pages/1738637481)
- **레포**: https://github.com/aitrics-adp/poc/tree/main/tri_pro

---

> 본 요청은 **시연·검증용 POC** 환경이며, 1개월 이내 회수 예정입니다.
> 추가 인프라 권한·계정 분리·VPC 격리 등은 MVP 단계에서 별도 요청 드리겠습니다.
