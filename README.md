# Multi dashboard data pipeline

KFR Partner API에서 일별 JSON 원천을 내려받아 Supabase에 그대로 저장하고, 기존 계산 로직이 기대하는 열 이름으로 빌드 시점에만 변환해 주식·채권·메자닌·글로벌 대시보드를 생성합니다.

## KFR API datasets

- `prices` → `fund_prices`
- `holdings` → `fund_holdings`
- `trades` → `fund_trades`
- `mezzanine-portfolio` → `mezzanine_price`

API 원문의 snake_case 필드는 `kfr_source_rows.payload` JSONB에 변경 없이 저장됩니다. `automation/kfr/kfr_api.py`가 대시보드 직전에 기존 한국어 열 이름으로 변환하므로 화면과 계산 로직은 유지됩니다.

## Local API download

필요한 환경변수는 `KFR_APP_KEY_ID`, `KFR_APP_KEY_SECRET`입니다. 로컬에서는 gitignore된 `.env.kfr_api`를 사용할 수 있습니다.

```powershell
python automation/kfr/kfr_partner_api_download.py `
  --date 2026-08-14 `
  --env-file automation/kfr/.env.kfr_api `
  --output-dir tmp/kfr
```

운영 기본 산출물은 JSON뿐입니다. 사람이 엑셀로 검수할 때만 `--write-csv`를 추가합니다.

## Supabase upload and restore

먼저 `supabase/migrations/202608240001_kfr_partner_api_json.sql`을 적용합니다.

```powershell
python automation/kfr/supabase_upload.py --input-dir tmp/kfr --business-date 2026-08-14
python scripts/restore_dashboard_inputs.py
```

복원된 KFR 파일은 `data/kfr/index.json`과 일별 API JSON입니다. 수기 관리 자료만 기존 Excel 형식으로 복원됩니다.

## Daily GitHub Actions

`.github/workflows/kfr-daily.yml`은 KFR API JSON 다운로드, Supabase 적재, JSON 복원, 키움 시세 갱신, 네 대시보드 생성과 배포를 수행합니다.

평일 07:30 KST에 기본 실행하고 10:00, 14:00 KST에 재확인합니다. 재확인 시 해당 기준일의 네 API 스냅샷에 대해 행 수, 저장 행, 필드 구조와 기준일을 검증하며, 누락되거나 비정상일 때만 KFR API를 다시 호출하고 Supabase에 재적재합니다. 데이터가 정상이더라도 앞선 빌드나 배포가 실패했다면 후속 실행에서 빌드와 배포를 다시 시도합니다.

필수 Secrets:

- `KFR_APP_KEY_ID`
- `KFR_APP_KEY_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `KIWOOM_APPKEY`
- `KIWOOM_SECRETKEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

## Repository layout

- `automation/kfr`: Partner API 다운로드, 스키마 변환, Supabase 적재
- `data/kfr`: 빌드에 사용하는 API JSON 복원 위치
- `apps/stock`: 주식 대시보드
- `apps/bond`: 채권 대시보드
- `apps/mezzanine`: 메자닌 대시보드
- `apps/global`: 글로벌 대시보드
- `scripts/restore_dashboard_inputs.py`: DB의 KFR JSON 및 수기 입력 복원
