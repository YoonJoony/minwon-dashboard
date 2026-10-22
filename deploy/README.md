# 배포 (Oracle Cloud 서버)

시연용 공개 서버. 보는 사람은 로그인 없이 `http://서버IP/`로 접속합니다.

| 항목 | 값 |
|---|---|
| 서버 | Oracle Cloud, 오사카(Japan Central), Ubuntu 24.04, VM.Standard.E5.Flex (OCPU 2 = vCPU 4, 메모리 16GB) |
| 비용 | 무료 체험 크레딧 사용 (30일). 체험 계정은 크레딧·기간이 끝나면 서버가 멈출 뿐 카드로 청구되지 않음 |
| 실행 | Docker 컨테이너 `minwon` (이미지 `minwon-dashboard`), 80번 → 컨테이너 7860번, 재부팅 시 자동 시작 |
| 접속 키 | 로컬 `~/.ssh/oracle_minwon` (사용자 `ubuntu`) |

무료(Always Free) ARM 서버(A1)는 오사카에 자리가 없어("Out of capacity") 체험 크레딧으로 AMD 서버를 썼습니다.
Hugging Face 무료 계정은 Docker Space를 만들 수 없어(PRO 필요) 쓰지 않았습니다 (`hf_space_card.md`, `deploy.py --space`는 PRO일 때용).

## 다시 배포 (코드를 커밋한 뒤, 프로젝트 루트에서)

```bash
uv run --no-project python deploy/deploy.py --server ubuntu@129.225.152.209
```

커밋된 코드(`git archive HEAD`)와 계산에 필요한 데이터(약 75MB)를 서버에 올리고,
서버에서 이미지를 다시 만듭니다: 화면 빌드 → 파이썬 환경 → 사전 계산(`engine.build`, 리허설 대조 실패 시 중단) → 컨테이너 교체.

## 서버 처음 준비 (이미 한 일)

1. 콘솔에서 VCN 마법사 "Create VCN with Internet Connectivity"로 네트워크 생성 → 기본 Security List에 TCP 80 허용 추가
   (인스턴스 만들기 화면 안에서 새 VCN을 만들면 공개 IP 토글이 잠김)
2. 인스턴스 생성: Ubuntu 24.04, 공개 서브넷, 공개 IPv4 자동 할당, SSH 공개 키 `~/.ssh/oracle_minwon.pub`
3. 서버에서: 방화벽 80번 열기(`iptables` + `iptables-persistent`로 저장), `docker.io`·`docker-buildx`·`rsync` 설치

## 확인·정리

```bash
ssh -i ~/.ssh/oracle_minwon ubuntu@129.225.152.209 'sudo docker ps; sudo docker logs --tail 20 minwon'
```

시연이 끝나면 콘솔에서 인스턴스를 **Terminate**(부트 볼륨 삭제 포함)하면 비용이 더 나가지 않습니다.
