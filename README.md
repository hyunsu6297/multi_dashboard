# Multi dashboard data pipeline

K-FROMS에서 통합 대시보드 원천 파일 3개를 내려받아 Supabase에 저장하고, DB 원천 데이터로 주식·채권·메자닌 대시보드를 생성합니다.

- `메자닌 기준가.xlsx`
- `전체펀드 매매현황.xlsx`
- `전체펀드 보유현황.xlsx`

다운로드 결과와 로그인 정보는 GitHub에 저장하지 않습니다. 일일 결과는 후속 적재 작업에서 Supabase로 전송합니다.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

실행 전에 `KFROM_ID`, `KFROM_PASSWORD` 환경변수를 설정합니다. 실제 값은 로컬 환경 또는 GitHub Actions Secrets에서만 관리합니다.

```powershell
$env:KFROM_ID = "<your id>"
$env:KFROM_PASSWORD = "<your password>"
python .\kfr_download.py
```

기본 기준일은 직전 영업일입니다. 거래내역도 시작일과 종료일을 같은 직전 영업일로 지정해 하루치만 내려받습니다. 명령행 인자로 기준일을 변경할 수 있습니다.

```powershell
python .\kfr_download.py --holding-date 2026-06-26 --trade-start-date 2026-06-19 --trade-end-date 2026-06-26
```

## Supabase upload

`supabase_upload.py`는 세 파일의 `Data` 시트를 읽어 기준일별 불변 스냅샷과 JSONB 행으로 저장합니다. 같은 파일을 다시 실행하면 SHA-256 중복 검사를 통해 재적재하지 않습니다.
매매현황은 KFR 파일에 더 긴 기간이 포함되더라도 `business_date`와 `기준일`이 일치하는 하루치 행만 적재합니다.

필요한 환경변수:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`: `sb_secret_...` 형식의 Secret key를 권장하며, 기존 JWT `service_role` 키도 지원합니다.

```powershell
python .\supabase_upload.py --input-dir . --business-date 2026-06-26
```

## Daily GitHub Actions

`.github/workflows/kfr-daily.yml`은 평일 오전 7시 30분(KST)에 실행됩니다. KFR 다운로드, Supabase 적재, DB 입력 복원, 키움 시세 조회, 주식·채권·메자닌 HTML 생성, Cloudflare Pages 배포를 순서대로 수행합니다.

- `KFROM_ID`
- `KFROM_PASSWORD`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `KIWOOM_APPKEY`
- `KIWOOM_SECRETKEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Secret key는 GitHub Actions에서만 사용하며 브라우저 코드나 일반 환경변수에 노출하면 안 됩니다.

Cloudflare Pages 프로젝트 이름은 `multi-dashboard`입니다. 최초 배포 전에 Cloudflare에서 같은 이름의 Pages 프로젝트를 만들고 API 토큰에 Pages 편집 권한을 부여합니다. Cloudflare Secret이 비어 있으면 HTML 생성과 artifact 업로드까지만 실행합니다.

## Repository layout

- `automation/kfr`: KFR 다운로드 및 Supabase 적재
- `apps/stock`: 주식 대시보드 빌더와 키움 REST 시세 수집기
- `apps/bond`: 채권형 대시보드 빌더
- `apps/mezzanine`: 메자닌 대시보드 빌더와 Supabase 실시간 시세 연결
- `scripts/restore_dashboard_inputs.py`: Supabase 원천·수기 데이터를 빌드 입력으로 복원
- `scripts/assemble_site.py`: 로그인 셸과 생성된 HTML을 `dist`로 조립
- `web`: Cloudflare Pages 정적 웹 셸


