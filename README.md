# KFR source data downloader

K-FROMS에서 통합 대시보드 원천 파일 3개를 내려받는 Playwright 자동화입니다.

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

필요한 환경변수:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`: `sb_secret_...` 형식의 Secret key를 권장하며, 기존 JWT `service_role` 키도 지원합니다.

```powershell
python .\supabase_upload.py --input-dir . --business-date 2026-06-26
```

## Daily GitHub Actions

`.github/workflows/kfr-daily.yml`은 평일 오전 8시 30분(KST)에 실행됩니다. 저장소 Actions secrets에 다음 값을 등록해야 합니다.

- `KFROM_ID`
- `KFROM_PASSWORD`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Secret key는 GitHub Actions에서만 사용하며 브라우저 코드나 일반 환경변수에 노출하면 안 됩니다.

