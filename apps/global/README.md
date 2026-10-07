# 글로벌 수익증권 대시보드

웹판은 `build_global_dashboard.py`가 Supabase KFR 원천 보유·매매 데이터와
`manual_file_rows`의 `global` 도메인 펀드/ETF DB를 읽어 생성합니다.
주식·채권·메자닌 도메인 자료는 변경하지 않습니다.

## Bloomberg 웹 업데이트

1. 이 PC에서 Bloomberg Terminal에 로그인합니다.
2. 저장소 루트의 `run_global_bloomberg_web_receiver.cmd`를 실행하고 창을 열어 둡니다.
3. 웹 글로벌대시보드에서 `블룸버그 업데이트` 또는 `미등록 ETF 등록`을 누릅니다.

웹 브라우저는 로그인한 Supabase 세션으로 글로벌 요청 대기열에 등록합니다.
PC 수신기는 바깥 방향 HTTPS 연결로 요청을 가져와 Desktop API(`localhost:8194`)를
조회하고, 결과를 글로벌 공용 시세/ETF DB에 반영합니다. 외부에서 이 PC로 들어오는
포트는 필요하지 않습니다. `SUPABASE_SERVICE_ROLE_KEY`는 PC 수신기에서만 사용하고
웹 코드에는 넣지 않습니다. 웹의 마지막 Bloomberg 업데이트 시각은 공용 시세의
`updatedAt`을 표시합니다.

ETF/펀드 DB의 변경저장은 Supabase에 반영됩니다. 권한이 없는 사용자는 열람만 할
수 있습니다. KFR 보유·매매 원천은 일일 자동 빌드에서 갱신되며 웹의 Bloomberg
버튼은 원천 자료를 다시 조회하지 않습니다.

## 로컬판

기존 로컬 서버는 별도이며, 웹 수신기와 동시에 실행할 필요는 없습니다.
로컬판 브라우저 캐시를 최초 이전할 때만
`scripts/migrate_global_browser_cache.py`를 사용합니다. 마이그레이션은 기존 글로벌
DB 행을 백업한 뒤 글로벌 파일 키만 갱신합니다.
