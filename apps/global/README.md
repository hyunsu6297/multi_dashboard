# 글로벌대시보드

글로벌 펀드의 보유현황과 매매현황을 ETF 분류정보와 결합해 시각화하는 로컬 대시보드입니다.

## 실행

```powershell
.\run_dashboard.ps1
```

브라우저에서 `http://127.0.0.1:8766`을 엽니다. Bloomberg 데이터 조회를 위해
Bloomberg Terminal 로그인 및 Desktop API(`localhost:8194`) 연결이 필요합니다.

## 주요 파일

- `build_global_dashboard.py`: 데이터 결합 및 정적 HTML 생성
- `index.html`: 생성된 글로벌대시보드
- `global_dashboard_server.py`: 대시보드 제공 및 Bloomberg Desktop API 중계
- `EMP보유현황.xlsx`: EMP1~4 원금 및 초기 보유 종목/수량
- `펀드정보.xlsx`: 글로벌 펀드 기준정보
- `ETF정보.xlsx`: ETF 분류 기준정보
- `전체펀드 보유현황.xlsx`: 임시 보유 원천데이터
- `전체펀드 매매현황.xlsx`: 임시 매매 원천데이터
- `EMP유니버스(260522).xlsx`: EMP 참고 유니버스

향후 보유현황·매매현황과 펀드·ETF 기준정보는 Supabase 데이터로 전환할 예정입니다.

리밸런싱 화면에서 변경한 보유수량·목표비중과 추가/삭제한 행은 `변경저장` 버튼을
누르면 현재 브라우저의 로컬 저장소에 저장됩니다. Excel 원본은 초기값으로 유지됩니다.
ETF DB 탭에서 활용 ETF의 Bloomberg 티커, 분류정보, EMP 라벨을 추가·수정·삭제할
수 있으며 변경 내용도 브라우저 로컬 저장소에 보관됩니다.
