"""API 명세(OpenAPI)를 파일로 저장합니다. 프런트엔드 타입 생성에 씁니다 (frontend: npm run gen:api)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.main import app

out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"저장: {out}")
