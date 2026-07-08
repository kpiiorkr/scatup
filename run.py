"""로컬 실행용 엔트리 (뼈대 단계).

`config`(루트)와 `scatup_agent`(src/) 를 함께 임포트할 수 있도록 경로를 잡아준다.
프로젝트 루트에서 `python run.py` 로 실행한다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))            # config 패키지
sys.path.insert(0, str(ROOT / "src"))    # scatup_agent 패키지

from scatup_agent.main import main  # noqa: E402

if __name__ == "__main__":
    main()
