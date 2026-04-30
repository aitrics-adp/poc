"""pytest 공통 설정 — backend 디렉토리를 import 경로에 추가."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
