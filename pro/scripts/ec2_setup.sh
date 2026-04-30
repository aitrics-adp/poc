#!/bin/bash
# EC2 첫 셋업 (Amazon Linux 2023 / Ubuntu 22.04 모두 가능)
# 1회만 실행
#
# 사용:
#   ssh ec2-user@<public-ip>
#   curl -fsSL https://raw.githubusercontent.com/<USER>/tri-pro-poc/main/scripts/ec2_setup.sh | bash
# 또는:
#   git clone <repo> tri-pro-poc && cd tri-pro-poc && bash scripts/ec2_setup.sh

set -e

echo "▸ 시스템 업데이트..."
if command -v dnf >/dev/null; then
  sudo dnf update -y
  sudo dnf install -y git docker
elif command -v apt >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y git ca-certificates curl
  # Docker 공식 설치 (Ubuntu)
  if ! command -v docker >/dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
      sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
fi

# Docker compose plugin 확인
if ! docker compose version >/dev/null 2>&1; then
  echo "▸ docker compose plugin 설치..."
  if command -v dnf >/dev/null; then
    sudo dnf install -y docker-compose-plugin || true
    # Amazon Linux는 별도 설치 필요할 수 있음
    if ! docker compose version >/dev/null 2>&1; then
      DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
      mkdir -p $DOCKER_CONFIG/cli-plugins
      curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
        -o $DOCKER_CONFIG/cli-plugins/docker-compose
      chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
    fi
  fi
fi

# 현재 사용자를 docker 그룹에
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

echo ""
echo "✅ EC2 셋업 완료"
echo ""
echo "다음 단계:"
echo "  1. (재로그인 필요) exit 후 다시 ssh"
echo "  2. cd ~/tri-pro-poc 후 cp .env.prod.example .env"
echo "  3. vim .env (도메인·VAPID 키 채움)"
echo "  4. python3 backend/scripts/gen_vapid.py 로 VAPID 생성"
echo "  5. ./scripts/deploy.sh 실행"
echo ""
