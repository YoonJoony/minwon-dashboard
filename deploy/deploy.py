"""배포: 커밋된 코드 + 계산에 필요한 데이터만 묶어 서버(또는 Hugging Face Space)에 올립니다.

- 코드는 `git archive HEAD`로 가져옵니다 (커밋하지 않은 작업은 올라가지 않음).
- 데이터는 사전 계산·서버에 필요한 파일만 (약 75MB). 311 월별 원본(349MB)은 올리지 않습니다.
  data/는 GitHub에는 올리지 않고 배포 대상에만 올립니다.
- 대상에서 Docker 이미지를 만들며 화면 빌드 → 사전 계산(engine.build) → 서버 실행을 합니다 (deploy/Dockerfile).

실행 (프로젝트 루트에서):
    # SSH 서버 (Oracle Cloud 등, Docker 설치돼 있어야 함 — deploy/README.md)
    uv run --no-project python deploy/deploy.py --server ubuntu@129.225.152.209
    # 코드만 (서버에 있는 data/는 그대로 씀). GitHub Actions 자동 배포가 이 방식 (.github/workflows/deploy.yml)
    python deploy/deploy.py --server ubuntu@129.225.152.209 --code-only --key 키파일
    # Hugging Face Space (Docker Space는 PRO 구독 필요). 먼저 `uvx --from huggingface_hub hf auth login`
    uv run --no-project --with huggingface_hub python deploy/deploy.py --space 사용자명/minwon-dashboard
    # 묶기만
    uv run --no-project python deploy/deploy.py --stage-only 폴더
"""
import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent

# 커밋된 코드 중 이미지에 필요한 것
CODE = ["pyproject.toml", "uv.lock", "backend", "engine", "frontend", "analysis/results"]
# 사전 계산·서버가 읽는 데이터 (engine/data.py, backend/app/store.py)
DATA = [
    "data/processed/daily_agency_weather.csv",
    "data/processed/daily_issue_weather.csv",
    "data/processed/weather_features_daily.csv",
    "data/processed/complaint_features.parquet",
    "data/raw/weather/openmeteo_bronx_daily.csv",
    "data/raw/weather/openmeteo_bronx_hourly_obs.parquet",
    "data/raw/weather/openmeteo_bronx_hourly_forecast.parquet",
    "data/raw/nws/nws_alerts_bronx.csv",
]
# Space에 다시 올릴 때 지운 뒤 새로 채우는 폴더 (지운 파일이 남아 빌드를 깨지 않게. .gitattributes 등은 둠)
SYNC = ["backend/**", "engine/**", "frontend/**", "analysis/**", "data/**", "pyproject.toml", "uv.lock"]
# 화면 코드 중 이미지에 필요 없는 것 (시연 점검·결과물)
SKIP_PREFIX = ("frontend/e2e/", "frontend/e2e-screens/", "frontend/test-results/", "backend/tests/")

IMAGE, CONTAINER, REMOTE_DIR = "minwon-dashboard", "minwon", "minwon"


def stage(dst: Path, space_card: bool = False, with_data: bool = True) -> str:
    """배포 폴더를 만들고 커밋 해시를 돌려줍니다. with_data=False면 코드만 (데이터는 대상에 이미 있다고 봄)."""
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD", *CODE], cwd=ROOT, check=True,
                         capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        members = [m for m in t.getmembers() if not m.name.startswith(SKIP_PREFIX)]
        t.extractall(dst, members=members, filter="data")
    missing = [p for p in DATA if with_data and not (ROOT / p).exists()]
    if missing:
        sys.exit("데이터 파일이 없습니다 (pipelines/ 수집·병합을 먼저 하세요):\n  " + "\n  ".join(missing))
    for p in DATA if with_data else []:
        (dst / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / p, dst / p)
    shutil.copy2(HERE / "Dockerfile", dst / "Dockerfile")
    if space_card:
        shutil.copy2(HERE / "hf_space_card.md", dst / "README.md")
    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file()) / 1e6
    print(f"배포 폴더: {dst} (커밋 {commit}, {size:.0f}MB)", flush=True)
    return commit


def to_server(target: str, key: str, code_only: bool = False) -> None:
    """SSH 서버에 올리고 이미지를 다시 만든 뒤 컨테이너를 바꿔 띄웁니다 (80번 → 7860).
    code_only면 서버의 data/는 지우지도 덮어쓰지도 않고 그대로 씁니다."""
    ssh = ["ssh", "-i", str(Path(key).expanduser()), "-o", "IdentitiesOnly=yes"]
    keep = ["--exclude=/data/"] if code_only else []
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp), with_data=not code_only)
        subprocess.run(["rsync", "-az", "--delete", *keep, "-e", " ".join(ssh), f"{tmp}/", f"{target}:{REMOTE_DIR}/"],
                       check=True)
    remote = (f"cd {REMOTE_DIR} && sudo docker build -t {IMAGE} . "
              f"&& (sudo docker rm -f {CONTAINER} >/dev/null 2>&1 || true) "
              f"&& sudo docker run -d --name {CONTAINER} --restart unless-stopped -p 80:7860 {IMAGE} "
              f"&& sudo docker image prune -f >/dev/null")
    print("서버에서 이미지 빌드(화면 빌드 → 사전 계산)와 교체를 합니다. 몇 분 걸립니다.", flush=True)
    subprocess.run([*ssh, target, remote], check=True)
    print(f"완료: http://{target.split('@')[-1]}/")


def to_space(space: str) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    with tempfile.TemporaryDirectory() as tmp:
        commit = stage(Path(tmp), space_card=True)
        api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
        api.upload_folder(folder_path=tmp, repo_id=space, repo_type="space", delete_patterns=SYNC,
                          commit_message=f"minwon-dashboard {commit} 배포")
    print(f"올림: https://huggingface.co/spaces/{space}  (빌드에 10분 안팎 걸립니다)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="배포 (SSH 서버 또는 Hugging Face Space)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--server", help="SSH 대상 (예: ubuntu@129.225.152.209)")
    g.add_argument("--space", help="Hugging Face Space 이름 (예: 사용자명/minwon-dashboard)")
    g.add_argument("--stage-only", type=Path, help="이 폴더에 묶기만 하고 올리지 않음")
    p.add_argument("--key", default="~/.ssh/oracle_minwon", help="--server용 SSH 개인 키")
    p.add_argument("--code-only", action="store_true", help="--server: 코드만 올리고 서버의 data/는 그대로 씀")
    a = p.parse_args(argv)

    if a.stage_only:
        a.stage_only.mkdir(parents=True, exist_ok=True)
        stage(a.stage_only)
    elif a.server:
        to_server(a.server, a.key, a.code_only)
    else:
        to_space(a.space)
    return 0


if __name__ == "__main__":
    sys.exit(main())
