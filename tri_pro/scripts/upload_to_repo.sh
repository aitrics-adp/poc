#!/bin/bash
# tri-pro-poc 코드를 github.com/aitrics-adp/poc 레포의 tri_pro/ 폴더로 업로드
#
# 동작:
#   1. 임시 폴더에 aitrics-adp/poc 클론
#   2. tri_pro/ 폴더를 깨끗이 비우고
#   3. 현재 tri-pro-poc 내용 복사 (venv·node_modules·캐시·DB·시크릿 제외)
#   4. commit + push
#
# 사전:
#   - GitHub 인증: SSH 키 등록되어 있거나, gh auth login, 또는 PAT 보유
#   - aitrics-adp/poc 리포에 쓰기 권한
#
# 사용:
#   ./scripts/upload_to_repo.sh                  # 기본 (https 사용)
#   ./scripts/upload_to_repo.sh --ssh            # SSH 사용
#   ./scripts/upload_to_repo.sh --message "..."  # 커밋 메시지 지정
#   ./scripts/upload_to_repo.sh --dry-run        # 푸시 직전까지만 (확인용)

set -e

REPO_URL_HTTPS="https://github.com/aitrics-adp/poc.git"
REPO_URL_SSH="git@github.com:aitrics-adp/poc.git"
TARGET_SUBDIR="tri_pro"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="${TMPDIR:-/tmp}/aitrics-adp-poc-upload-$$"

USE_SSH=false
DRY_RUN=false
COMMIT_MSG="feat(tri_pro): TRI-PRO POC 업로드

- 5명 합성 환자 시드 (C-1042/2103/3027/4581/5219)
- FSD 74개 기능 P0 모두 구현
- 백엔드 90/90 테스트 통과
- 환자별 PRO 도구 자동 추천 + 커스텀 세트 빌더
- LLM 4종 가드레일 (응급/OoS/Education/PII)
- 일별 PRO 응답 상세 + 변경 이력 가시화
- 자동 데모 스크립트 + EC2 배포 가이드"

while [ $# -gt 0 ]; do
  case "$1" in
    --ssh)      USE_SSH=true; shift ;;
    --dry-run)  DRY_RUN=true; shift ;;
    --message)  COMMIT_MSG="$2"; shift 2 ;;
    -m)         COMMIT_MSG="$2"; shift 2 ;;
    -h|--help)  head -22 "$0" | tail -20; exit 0 ;;
    *) echo "❌ 알 수 없는 옵션: $1"; exit 1 ;;
  esac
done

REPO_URL=$([ "$USE_SSH" = true ] && echo "$REPO_URL_SSH" || echo "$REPO_URL_HTTPS")

G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[34m"; N="\033[0m"
ok()    { echo -e "${G}✓${N} $1"; }
info()  { echo -e "${B}▸${N} $1"; }
warn()  { echo -e "${Y}⚠${N} $1"; }
err()   { echo -e "${R}✗${N} $1"; exit 1; }

# 사전 검증
[ -d "$SOURCE/backend" ]    || err "프로젝트 루트 X. tri-pro-poc 폴더 안에서 실행하세요."
[ -d "$SOURCE/admin-app" ]  || err "admin-app 폴더 X."
[ -d "$SOURCE/patient-app" ]|| err "patient-app 폴더 X."

command -v git >/dev/null   || err "git 미설치"
command -v rsync >/dev/null || err "rsync 미설치 (macOS는 기본 포함)"

info "소스: $SOURCE"
info "대상: $REPO_URL  →  $TARGET_SUBDIR/"
info "작업폴더: $WORKDIR"
echo ""

# 1) 클론
info "1) 레포 클론..."
mkdir -p "$WORKDIR"
git clone --depth 1 "$REPO_URL" "$WORKDIR" || err "클론 실패. 인증 또는 권한 확인."
cd "$WORKDIR"
ok "클론 완료"

# 2) 대상 폴더 비우기
info "2) $TARGET_SUBDIR/ 비우는 중..."
git rm -rf "$TARGET_SUBDIR" 2>/dev/null || true
rm -rf "$TARGET_SUBDIR"
mkdir -p "$TARGET_SUBDIR"

# 3) 복사 (불필요한 것 제외)
info "3) 소스 복사 (venv·node_modules·캐시·DB·시크릿 제외)..."
rsync -a \
  --exclude 'venv' \
  --exclude 'venv_old_*' \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '.next-build-cache' \
  --exclude '.turbo' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude 'dev.db' \
  --exclude 'dev.db-journal' \
  --exclude '.logs' \
  --exclude '.pids' \
  --exclude '.backup_*' \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude '.env.local' \
  --exclude '.env.*.local' \
  --exclude 'demo/screenshots' \
  --exclude 'demo/videos' \
  --exclude '.git' \
  "$SOURCE/" "$TARGET_SUBDIR/"
ok "복사 완료"

# 통계
SIZE=$(du -sh "$TARGET_SUBDIR" 2>/dev/null | cut -f1)
FILES=$(find "$TARGET_SUBDIR" -type f | wc -l | tr -d ' ')
ok "업로드 대상: $FILES files, $SIZE"

# 4) commit
info "4) 커밋 준비..."
git add "$TARGET_SUBDIR"
if git diff --cached --quiet; then
  warn "변경 사항 없음 — 푸시 생략"
  rm -rf "$WORKDIR"
  exit 0
fi

# 변경 통계 미리보기
echo ""
git diff --cached --stat | tail -10
echo ""

if [ "$DRY_RUN" = true ]; then
  warn "DRY-RUN — 여기서 중단. 워크폴더: $WORKDIR"
  exit 0
fi

git commit -m "$COMMIT_MSG"
ok "커밋 완료"

# 5) push
info "5) push..."
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git push origin "$BRANCH" || err "push 실패. 인증 또는 브랜치 권한 확인."
ok "push 완료 → https://github.com/aitrics-adp/poc/tree/$BRANCH/$TARGET_SUBDIR"

# 정리
cd "$SOURCE"
rm -rf "$WORKDIR"
ok "임시 폴더 정리 완료"

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ 업로드 완료"
echo "  https://github.com/aitrics-adp/poc/tree/main/tri_pro"
echo "═══════════════════════════════════════════════"
