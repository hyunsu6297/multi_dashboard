"""
Download fund data from KFR K-FROMS.

Setup once:
  python -m pip install playwright
  python -m playwright install chromium

Credentials are read from environment variables so they are not stored in this
file:
  set KFROM_ID=<your id>
  set KFROM_PASSWORD=<your password>

Run:
  python kfr_download.py

The downloaded Excel files are saved locally, by default under:
  ./전체펀드 보유현황.xlsx
  ./전체펀드 매매현황.xlsx
  ./메자닌 기준가.xlsx
"""

from __future__ import annotations

import argparse
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent
HOLDINGS_DOWNLOAD_NAME = "전체펀드 보유현황.xlsx"
TRADES_DOWNLOAD_NAME = "전체펀드 매매현황.xlsx"
MEZZANINE_DOWNLOAD_NAME = "메자닌 기준가.xlsx"
SITE_URL = "https://kfroms.kfr.co.kr/home"
DEBUG_TEXT = BASE_DIR / "kfroms_holdings_debug_text.txt"
DEBUG_SCREENSHOT = BASE_DIR / "kfroms_holdings_debug_screen.png"
DEBUG_HTML = BASE_DIR / "kfroms_holdings_debug.html"


def previous_business_day(today: date | None = None) -> date:
    current = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    current -= timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def business_days_before(base_day: date, days: int) -> date:
    current = base_day
    remaining = days
    while remaining:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def normalize_date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")


def env_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"환경변수 {name}가 설정되어 있지 않습니다.")
    return value


def first_visible(page, selectors: list[str], timeout: int = 2500):
    last_error = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception as exc:  # noqa: BLE001 - selector fallback
            last_error = exc
    raise RuntimeError(f"화면 요소를 찾지 못했습니다: {selectors}") from last_error


def click_text(page, text: str, timeout: int = 8000) -> None:
    candidates = [
        f"role=button[name='{text}']",
        f"role=link[name='{text}']",
        f"text={text}",
        f"xpath=//*[normalize-space()='{text}']",
    ]
    first_visible(page, candidates, timeout=timeout).click()


def visible_text_box(page, text: str):
    return page.evaluate(
        """
        (text) => {
            const nodes = Array.from(document.querySelectorAll('body *'));
            for (const node of nodes) {
                if ((node.textContent || '').trim() !== text) continue;
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                if (
                    style.visibility === 'hidden' ||
                    style.display === 'none' ||
                    rect.width === 0 ||
                    rect.height === 0
                ) continue;
                return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
            }
            return null;
        }
        """,
        text,
    )


def is_text_visible(page, text: str) -> bool:
    return visible_text_box(page, text) is not None


def click_visible_text(page, text: str, right_offset: float = 0, timeout: int = 8000) -> None:
    deadline = datetime.now().timestamp() + timeout / 1000
    box = visible_text_box(page, text)
    while box is None and datetime.now().timestamp() < deadline:
        page.wait_for_timeout(200)
        box = visible_text_box(page, text)
    if box is None:
        raise RuntimeError(f"화면 요소를 찾지 못했습니다: {text}")
    page.mouse.click(box["x"] + box["width"] / 2 + right_offset, box["y"] + box["height"] / 2)


def click_visible_menu_anchor(page, text: str, timeout: int = 8000) -> None:
    deadline = datetime.now().timestamp() + timeout / 1000
    clicked = False
    while not clicked and datetime.now().timestamp() < deadline:
        clicked = page.evaluate(
            """
            (text) => {
                const nodes = Array.from(document.querySelectorAll('body *'));
                for (const node of nodes) {
                    if ((node.textContent || '').trim() !== text) continue;
                    const style = window.getComputedStyle(node);
                    const rect = node.getBoundingClientRect();
                    if (
                        style.visibility === 'hidden' ||
                        style.display === 'none' ||
                        rect.width === 0 ||
                        rect.height === 0
                    ) continue;
                    const anchor = node.closest('a');
                    if (!anchor) continue;
                    anchor.click();
                    return true;
                }
                return false;
            }
            """,
            text,
        )
        if not clicked:
            page.wait_for_timeout(200)
    if not clicked:
        raise RuntimeError(f"화면 요소를 찾지 못했습니다: {text}")


def click_excel_download_menu(page, timeout: int = 8000) -> None:
    targets = ["엑셀다운로드", "엑셀 다운로드", "Excel 다운로드", "Excel Export", "Export to Excel", "엑셀"]
    for text in targets:
        try:
            click_text(page, text, timeout=1200)
            return
        except Exception:
            continue

    deadline = datetime.now().timestamp() + timeout / 1000
    while datetime.now().timestamp() < deadline:
        box = page.evaluate(
            """
            (targets) => {
                const normalize = (value) => (value || '').replace(/\\s+/g, '').toLowerCase();
                const wanted = targets.map(normalize);
                const nodes = Array.from(document.querySelectorAll('body *'));
                const candidates = [];

                for (const node of nodes) {
                    const normalizedText = normalize(node.textContent);
                    if (!normalizedText || !wanted.some((text) => normalizedText.includes(text))) {
                        continue;
                    }

                    const style = window.getComputedStyle(node);
                    const rect = node.getBoundingClientRect();
                    if (
                        style.visibility === 'hidden' ||
                        style.display === 'none' ||
                        rect.width === 0 ||
                        rect.height === 0
                    ) {
                        continue;
                    }

                    candidates.push({
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height,
                        area: rect.width * rect.height,
                    });
                }

                if (!candidates.length) return null;
                candidates.sort((a, b) => a.area - b.area);
                const rect = candidates[0];
                return {
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                };
            }
            """,
            targets,
        )
        if box:
            page.mouse.click(box["x"], box["y"])
            return
        page.wait_for_timeout(200)

    raise RuntimeError("우클릭 메뉴에서 엑셀다운로드 항목을 찾지 못했습니다.")


def fill_date(page, label_text: str, value: str) -> None:
    filled = page.evaluate(
        """
        ({ labelText, value }) => {
            const visibleRect = (node) => {
                if (!node) return null;
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                if (
                    style.visibility === 'hidden' ||
                    style.display === 'none' ||
                    rect.width === 0 ||
                    rect.height === 0
                ) return null;
                return rect;
            };

            const setValue = (input) => {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    'value'
                ).set;
                setter.call(input, value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.blur();
                return true;
            };

            const labels = Array.from(document.querySelectorAll('label'))
                .filter((label) => (label.textContent || '').trim().includes(labelText))
                .filter(visibleRect);

            for (const label of labels) {
                const id = label.getAttribute('for');
                const byId = id ? document.getElementById(id) : null;
                if (byId && byId.matches('input') && visibleRect(byId)) return setValue(byId);

                const wrapper = label.closest('.MuiFormControl-root, form, div');
                const wrappedInput = wrapper?.querySelector('input');
                if (wrappedInput && visibleRect(wrappedInput)) return setValue(wrappedInput);
            }

            return false;
        }
        """,
        {"labelText": label_text, "value": value},
    )
    if filled:
        page.wait_for_timeout(200)
        return

    candidates = [
        f"input[aria-label*='{label_text}']",
        f"input[placeholder*='{label_text}']",
        f"xpath=//*[contains(normalize-space(), '{label_text}')]/following::input[1]",
        "input[type='date']",
        "input[placeholder*='yyyy']",
        "input[placeholder*='YYYY']",
        "input[placeholder*='날짜']",
        "input[class*='date']",
        "input[id*='date']",
        "input[name*='date']",
    ]
    field = first_visible(page, candidates)
    field.click()
    field.press("Control+A")
    field.fill(value)


def save_downloaded_file(downloaded: Path, output_dir: Path, download_name: str) -> Path:
    output = output_dir / download_name
    if output.exists():
        output.unlink()
    shutil.move(str(downloaded), str(output))
    return output


def login(page, user_id: str, password: str) -> None:
    id_field = first_visible(
        page,
        [
            "input[name='id']",
            "input[name='userId']",
            "input[name='loginId']",
            "input[type='text']",
            "input:not([type])",
        ],
        timeout=10000,
    )
    id_field.fill(user_id)

    password_field = first_visible(
        page,
        [
            "input[name='password']",
            "input[name='passwd']",
            "input[name='pwd']",
            "input[type='password']",
        ],
    )
    password_field.fill(password)

    for text in ["로그인", "Login", "LOGIN"]:
        try:
            click_text(page, text, timeout=2500)
            return
        except Exception:
            continue
    password_field.press("Enter")


def write_debug_artifacts(page) -> None:
    DEBUG_TEXT.write_text(page.locator("body").inner_text(timeout=5000), encoding="utf-8")
    DEBUG_HTML.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=DEBUG_SCREENSHOT, full_page=True)


def navigate_to_report(page, report_name: str) -> None:
    try:
        if not is_text_visible(page, "하나은행"):
            click_text(page, "위탁평가")
            page.wait_for_timeout(700)
        if not is_text_visible(page, report_name):
            click_visible_text(page, "하나은행", right_offset=135)
            page.wait_for_timeout(1000)
        click_visible_menu_anchor(page, report_name)
        page.wait_for_timeout(700)
    except Exception:
        write_debug_artifacts(page)
        raise


def results_table_box(page, headers: list[str], min_matches: int = 4, timeout: int = 20000):
    deadline = datetime.now().timestamp() + timeout / 1000
    while datetime.now().timestamp() < deadline:
        box = page.evaluate(
            """
            ({ headers, minMatches }) => {
                const normalize = (value) => (value || '').replace(/\\s+/g, '').trim();
                const visibleRect = (node) => {
                    if (!node) return null;
                    const style = window.getComputedStyle(node);
                    const rect = node.getBoundingClientRect();
                    if (
                        style.visibility === 'hidden' ||
                        style.display === 'none' ||
                        rect.width === 0 ||
                        rect.height === 0
                    ) return null;
                    return rect;
                };

                const matches = [];
                const nodes = Array.from(document.querySelectorAll('body *'));
                for (const header of headers) {
                    const node = nodes.find((candidate) => {
                        const text = normalize(candidate.textContent);
                        return text === header && visibleRect(candidate);
                    });
                    if (!node) continue;

                    const grid = node.closest(
                        '.tui-grid-container, .tui-grid-rside-area, .ag-root, [role="grid"], table, [class*="Grid"], [class*="grid"]'
                    );
                    const rect = visibleRect(grid || node);
                    if (rect) {
                        matches.push({
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            right: rect.right,
                            bottom: rect.bottom
                        });
                    }
                }

                if (matches.length < minMatches) return null;

                const largest = matches
                    .slice()
                    .sort((a, b) => (b.width * b.height) - (a.width * a.height))[0];
                if (largest.width > 250 && largest.height > 80) return largest;

                const left = Math.min(...matches.map((rect) => rect.x));
                const top = Math.min(...matches.map((rect) => rect.y));
                const right = Math.max(...matches.map((rect) => rect.right));
                const bottom = Math.max(...matches.map((rect) => rect.bottom));
                return { x: left, y: top, width: right - left, height: Math.max(120, bottom - top) };
            }
            """,
            {"headers": headers, "minMatches": min_matches},
        )
        if box:
            return box
        page.wait_for_timeout(300)
    return None


def right_click_results_table(
    page,
    headers: list[str],
    error_message: str,
    cell_selectors: list[str] | None = None,
    min_matches: int = 4,
) -> None:
    table_box = results_table_box(page, headers=headers, min_matches=min_matches)
    if not table_box:
        write_debug_artifacts(page)
        raise RuntimeError(error_message)

    selectors = cell_selectors or [
        "td[data-column-name*='FUND']",
        ".tui-grid-cell",
        ".ag-cell",
        "[role='gridcell']",
    ]
    for selector in selectors:
        try:
            cell = first_visible(page, [selector], timeout=1200)
            cell.click(button="right")
            page.wait_for_timeout(500)
            return
        except Exception:
            continue

    page.mouse.click(
        table_box["x"] + min(table_box["width"] / 2, 320),
        table_box["y"] + min(table_box["height"] / 2, 120),
        button="right",
    )
    page.wait_for_timeout(500)


def open_context_menu_excel_download(
    page,
    download_dir: Path,
    download_name: str,
    headers: list[str],
    error_message: str,
    cell_selectors: list[str] | None = None,
    min_matches: int = 4,
) -> Path:
    right_click_results_table(
        page,
        headers=headers,
        error_message=error_message,
        cell_selectors=cell_selectors,
        min_matches=min_matches,
    )

    with page.expect_download(timeout=30000) as download_info:
        try:
            click_excel_download_menu(page)
        except Exception:
            write_debug_artifacts(page)
            raise

    download = download_info.value
    suggested_name = download.suggested_filename or download_name
    temp_path = download_dir / f"__download_{datetime.now():%Y%m%d_%H%M%S}_{suggested_name}"
    download.save_as(temp_path)
    return temp_path


def run(
    holding_date: str,
    trade_start_date: str,
    trade_end_date: str,
    output_dir: Path,
    headless: bool,
) -> list[Path]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "playwright가 설치되어 있지 않습니다. "
            "`python -m pip install playwright` 및 "
            "`python -m playwright install chromium`을 먼저 실행하세요."
        ) from exc

    user_id = env_required("KFROM_ID")
    password = env_required("KFROM_PASSWORD")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(SITE_URL, wait_until="domcontentloaded", timeout=60000)

            login(page, user_id, password)
            page.wait_for_load_state("networkidle", timeout=60000)

            navigate_to_report(page, "전체펀드 보유현황")
            fill_date(page, "기준일", holding_date)
            click_text(page, "검색")
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(1500)

            holdings_downloaded = open_context_menu_excel_download(
                page,
                download_dir=output_dir,
                download_name=HOLDINGS_DOWNLOAD_NAME,
                headers=["보유일", "유형", "예탁원코드", "협회펀드코드", "펀드명", "자산군", "시장구분", "종목코드"],
                error_message=(
                    "보유일/유형/예탁원 코드/협회펀드코드/펀드명/자산군/시장구분/종목코드 헤더가 있는 "
                    "결과 테이블을 찾지 못했습니다."
                ),
                cell_selectors=[
                    "td[data-column-name*='BUYDAY']",
                    "td[data-column-name*='FUNDKNAME']",
                    "td[data-column-name*='ITEMCODE']",
                    ".tui-grid-cell",
                    ".ag-cell",
                    "[role='gridcell']",
                ],
            )
            holdings_output = save_downloaded_file(holdings_downloaded, output_dir, HOLDINGS_DOWNLOAD_NAME)

            navigate_to_report(page, "전체펀드 매매현황")
            fill_date(page, "시작일", trade_start_date)
            fill_date(page, "종료일", trade_end_date)
            click_text(page, "검색")
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(1500)

            trades_downloaded = open_context_menu_excel_download(
                page,
                download_dir=output_dir,
                download_name=TRADES_DOWNLOAD_NAME,
                headers=["펀드명"],
                error_message="펀드명 헤더가 있는 전체펀드 매매현황 결과 테이블을 찾지 못했습니다.",
                cell_selectors=[
                    "td[data-column-name*='FUNDKNAME']",
                    "td[data-column-name*='FUND']",
                    ".tui-grid-cell",
                    ".ag-cell",
                    "[role='gridcell']",
                ],
                min_matches=1,
            )
            trades_output = save_downloaded_file(trades_downloaded, output_dir, TRADES_DOWNLOAD_NAME)

            navigate_to_report(page, "메자닌포트폴리오")
            fill_date(page, "기준일", holding_date)
            click_text(page, "검색")
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(1500)

            mezzanine_downloaded = open_context_menu_excel_download(
                page,
                download_dir=output_dir,
                download_name=MEZZANINE_DOWNLOAD_NAME,
                headers=["펀드명"],
                error_message="펀드명 헤더가 있는 메자닌포트폴리오 결과 테이블을 찾지 못했습니다.",
                cell_selectors=[
                    "td[data-column-name*='FUNDKNAME']",
                    "td[data-column-name*='FUND']",
                    ".tui-grid-cell",
                    ".ag-cell",
                    "[role='gridcell']",
                ],
                min_matches=1,
            )
            mezzanine_output = save_downloaded_file(mezzanine_downloaded, output_dir, MEZZANINE_DOWNLOAD_NAME)
        except Exception:
            write_debug_artifacts(page)
            raise
        finally:
            context.close()
            browser.close()

    return [holdings_output, trades_output, mezzanine_output]


def main() -> None:
    default_trade_end = previous_business_day()
    default_trade_start = business_days_before(default_trade_end, 5)

    parser = argparse.ArgumentParser()
    parser.add_argument("--holding-date", default=default_trade_end.strftime("%Y-%m-%d"))
    parser.add_argument("--trade-start-date", default=default_trade_start.strftime("%Y-%m-%d"))
    parser.add_argument("--trade-end-date", default=default_trade_end.strftime("%Y-%m-%d"))
    parser.add_argument("--output-dir", default=str(BASE_DIR))
    parser.add_argument("--headed", action="store_true", help="브라우저 화면을 보면서 실행합니다.")
    args = parser.parse_args()

    outputs = run(
        holding_date=normalize_date(args.holding_date),
        trade_start_date=normalize_date(args.trade_start_date),
        trade_end_date=normalize_date(args.trade_end_date),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        headless=not args.headed,
    )
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()

