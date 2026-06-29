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

기본 기준일은 직전 영업일이며 명령행 인자로 변경할 수 있습니다.

```powershell
python .\kfr_download.py --holding-date 2026-06-26 --trade-start-date 2026-06-19 --trade-end-date 2026-06-26
```

