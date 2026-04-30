#!/bin/bash
# 모든 서비스 종료 (8000 / 3000 / 3001 포트)
exec "$(dirname "$0")/restart.sh" stop
