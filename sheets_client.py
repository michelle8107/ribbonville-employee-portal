"""구글 시트 연동 (링크 모음 + 업무 달력 데이터 저장)

구글 시트를 간이 데이터베이스로 사용한다. 시트 안에 "링크", "달력" 워크시트가
없으면 자동으로 만들어준다.
"""

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

LINKS_SHEET = "링크"
LINKS_HEADER = ["이름", "링크", "설명", "카테고리", "담당자"]

CALENDAR_SHEET = "달력"
CALENDAR_HEADER = ["제목", "날짜", "담당자", "설명", "상태"]


def _client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def _open_spreadsheet():
    return _client().open_by_key(st.secrets["SPREADSHEET_ID"])


def _worksheet(name: str, header: list[str]):
    sheet = _open_spreadsheet()
    try:
        ws = sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=500, cols=len(header))
        ws.append_row(header)
        return ws
    if ws.row_values(1) != header:
        ws.update("A1", [header])
    return ws


@st.cache_data(ttl=60, show_spinner=False)
def load_links() -> pd.DataFrame:
    ws = _worksheet(LINKS_SHEET, LINKS_HEADER)
    records = ws.get_all_records()
    return pd.DataFrame(records, columns=LINKS_HEADER)


def add_link(row: dict) -> None:
    ws = _worksheet(LINKS_SHEET, LINKS_HEADER)
    ws.append_row([str(row.get(c, "")) for c in LINKS_HEADER])
    load_links.clear()


def delete_link(row_index: int) -> None:
    ws = _worksheet(LINKS_SHEET, LINKS_HEADER)
    ws.delete_rows(row_index + 2)  # +1 header, +1 1-indexed
    load_links.clear()


@st.cache_data(ttl=60, show_spinner=False)
def load_calendar() -> pd.DataFrame:
    ws = _worksheet(CALENDAR_SHEET, CALENDAR_HEADER)
    records = ws.get_all_records()
    df = pd.DataFrame(records, columns=CALENDAR_HEADER)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.date
    return df


def add_event(row: dict) -> None:
    ws = _worksheet(CALENDAR_SHEET, CALENDAR_HEADER)
    ws.append_row([str(row.get(c, "")) for c in CALENDAR_HEADER])
    load_calendar.clear()


def delete_event(row_index: int) -> None:
    ws = _worksheet(CALENDAR_SHEET, CALENDAR_HEADER)
    ws.delete_rows(row_index + 2)
    load_calendar.clear()
