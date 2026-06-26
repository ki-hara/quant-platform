# Oracle Cloud Always Free 배포 가이드

이 문서는 소규모 테스트 비용을 0원에 가깝게 유지하기 위한 Oracle Cloud Always Free 배포 절차입니다.

## 선택 기준

- VM: Ampere A1 Arm 인스턴스 권장
- OS: Ubuntu 22.04 또는 24.04
- Shape: 1 OCPU / 6GB RAM 정도면 충분
- Boot volume: 기본 50GB
- App: Docker 단일 컨테이너
- DB: VM 디스크의 SQLite 파일 `/opt/quant-platform/data/quant_platform.db`

Oracle 공식 Free Tier는 Always Free 서비스로 Compute, Arm-based Ampere A1 Compute, Block Volume 등을 안내합니다. Oracle Help Center는 Always Free Block Volume 총 200GB와 기본 boot volume 50GB 기준도 안내합니다.

## 1. Oracle Cloud 계정 생성

1. Oracle Cloud Free Tier에 가입합니다.
2. 홈 리전을 선택합니다.
3. 결제 수단을 등록합니다.
4. 콘솔에 로그인합니다.

주의: 무료 조건을 벗어나는 리소스를 만들지 않도록 VM 생성 화면에서 `Always Free eligible` 표시를 확인합니다.

## 2. VM 생성

1. Compute > Instances > Create instance
2. Image: Ubuntu 22.04 또는 24.04
3. Shape: Ampere A1
4. OCPU: 1
5. Memory: 6GB
6. Boot volume: 기본 50GB
7. SSH public key 등록
8. Create

## 3. 네트워크 포트 열기

VCN 보안 목록 또는 Network Security Group에서 Ingress Rule을 추가합니다.

- TCP 22: SSH
- TCP 80: 웹 접속

HTTPS까지 직접 처리하려면 TCP 443도 엽니다. 초기 테스트는 80만으로 충분합니다.

Ubuntu 방화벽을 사용하는 경우:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw reload
```

## 4. 서버 접속

```bash
ssh ubuntu@SERVER_PUBLIC_IP
```

Oracle Linux 이미지를 선택했다면 기본 사용자가 `opc`일 수 있습니다.

## 5. 소스 배치

서버에서:

```bash
sudo mkdir -p /opt/quant-platform
sudo chown -R "$USER:$USER" /opt/quant-platform
cd /opt/quant-platform
git clone YOUR_REPOSITORY_URL app
```

아직 원격 Git 저장소가 없다면 로컬에서 압축 파일로 복사해도 됩니다.

## 6. Docker 설치 및 앱 실행

```bash
cd /opt/quant-platform/app
sudo bash deploy/oci/setup-ubuntu.sh
```

첫 배포 전 `deploy/oci/docker-compose.yml`의 `QUANT_AUTH_SECRET`와 `QUANT_DEFAULT_OWNER_PIN`은 원하는 값으로 바꾸는 것을 권장합니다.

상태 확인:

```bash
docker ps
curl http://127.0.0.1/api/health
```

브라우저 접속:

```text
http://SERVER_PUBLIC_IP
```

## 7. 업데이트

```bash
cd /opt/quant-platform/app
git pull
cd deploy/oci
sudo docker compose up -d --build
```

## 8. SQLite 백업

앱 화면의 `DB 백업` 버튼으로 다운로드할 수 있습니다.

서버에서도 직접 백업할 수 있습니다.

```bash
cd /opt/quant-platform/app
bash deploy/oci/backup-sqlite.sh
```

백업 파일 위치:

```text
/opt/quant-platform/backups
```

## 9. 무료 운영 주의사항

- Always Free 표시가 없는 리소스는 만들지 않습니다.
- Load Balancer, 큰 Block Volume, 유료 DB는 사용하지 않습니다.
- SQLite 파일은 `/opt/quant-platform/data`에 남습니다.
- 정기적으로 앱의 `DB 백업` 버튼 또는 `backup-sqlite.sh`로 백업합니다.
- Oracle 리전 자원이 부족하면 Ampere A1 인스턴스 생성이 실패할 수 있습니다. 이 경우 다른 시간대에 다시 시도합니다.
