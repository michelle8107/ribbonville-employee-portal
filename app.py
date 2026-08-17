"""리본빌 직원 홈페이지 (Streamlit 웹앱)

기능:
  1. 스프레드시트 링크 모음
  2. 업무 달력
데이터는 구글 시트에 저장되어 여러 직원이 같이 보고 입력할 수 있다.
연차 신청/결재 시스템은 추후 추가 예정.
"""

import calendar
from datetime import date

import pandas as pd
import streamlit as st

import sheets_client as db

st.set_page_config(page_title="리본빌 직원 홈페이지", page_icon="🏠", layout="wide")

st.title("🏠 리본빌 직원 홈페이지")

if not db.has_credentials() or not st.secrets.get("SPREADSHEET_ID"):
    st.error(
        "구글 시트 연동이 설정되지 않았습니다.\n\n"
        "Streamlit Cloud > App settings > Secrets 에 `GCP_SERVICE_ACCOUNT_JSON`(서비스 계정 키 파일 "
        "내용 전체)과 `SPREADSHEET_ID`(구글 시트 ID)를 입력해주세요. 자세한 방법은 README를 참고하세요."
    )
    st.stop()

CATEGORIES = ["재고관리", "매출/정산", "마케팅", "거래처", "기타"]
STATUS_BADGE = {"예정": "🟡", "진행중": "🔵", "완료": "🟢"}

tab_links, tab_calendar = st.tabs(["📊 스프레드시트 링크", "📅 업무 달력"])

with tab_links:
    st.subheader("자주 쓰는 스프레드시트 링크")

    with st.expander("➕ 새 링크 추가"):
        with st.form("add_link_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("이름 *")
                link = st.text_input("링크(URL) *")
                category = st.selectbox("카테고리", CATEGORIES)
            with c2:
                owner = st.text_input("담당자")
                desc = st.text_area("설명", height=100)
            if st.form_submit_button("추가"):
                if not name or not link:
                    st.warning("이름과 링크는 필수입니다.")
                else:
                    db.add_link({"이름": name, "링크": link, "설명": desc, "카테고리": category, "담당자": owner})
                    st.success("추가했습니다.")
                    st.rerun()

    try:
        links_df = db.load_links()
    except Exception as e:
        st.error(f"구글 시트를 불러오지 못했습니다: {e}")
        links_df = pd.DataFrame(columns=["이름", "링크", "설명", "카테고리", "담당자"])

    if links_df.empty:
        st.info("등록된 링크가 없습니다. 위에서 추가해주세요.")
    else:
        selected_cats = st.multiselect("카테고리 필터", CATEGORIES)
        view_df = links_df if not selected_cats else links_df[links_df["카테고리"].isin(selected_cats)]

        for i, row in view_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"**[{row['이름']}]({row['링크']})**  ·  `{row['카테고리'] or '기타'}`  ·  담당: {row['담당자'] or '-'}")
                    if row["설명"]:
                        st.caption(row["설명"])
                with c2:
                    if st.button("삭제", key=f"del_link_{i}"):
                        db.delete_link(i)
                        st.rerun()

with tab_calendar:
    st.subheader("팀 업무 달력")

    with st.expander("➕ 새 일정 추가"):
        with st.form("add_event_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                title = st.text_input("제목 *")
                event_date = st.date_input("날짜 *", value=date.today())
                status = st.selectbox("상태", list(STATUS_BADGE.keys()))
            with c2:
                owner = st.text_input("담당자 ", key="event_owner")
                desc = st.text_area("설명 ", height=100, key="event_desc")
            if st.form_submit_button("추가"):
                if not title:
                    st.warning("제목은 필수입니다.")
                else:
                    db.add_event({
                        "제목": title, "날짜": event_date.isoformat(),
                        "담당자": owner, "설명": desc, "상태": status,
                    })
                    st.success("추가했습니다.")
                    st.rerun()

    try:
        cal_df = db.load_calendar()
    except Exception as e:
        st.error(f"구글 시트를 불러오지 못했습니다: {e}")
        cal_df = pd.DataFrame(columns=["제목", "날짜", "담당자", "설명", "상태"])

    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        year = st.number_input("연도", min_value=2020, max_value=2100, value=today.year, step=1)
    with c2:
        month = st.number_input("월", min_value=1, max_value=12, value=today.month, step=1)

    if not cal_df.empty:
        month_events = cal_df[cal_df["날짜"].apply(lambda d: isinstance(d, date) and d.year == year and d.month == month)]
    else:
        month_events = cal_df

    st.markdown(f"### {year}년 {month}월")
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)  # 일요일 시작
    header_cols = st.columns(7)
    for col, label in zip(header_cols, ["일", "월", "화", "수", "목", "금", "토"]):
        col.markdown(f"**{label}**")

    for week in weeks:
        cols = st.columns(7)
        for col, day in zip(cols, week):
            if day == 0:
                col.write("")
                continue
            day_events = month_events[month_events["날짜"].apply(lambda d: isinstance(d, date) and d.day == day)]
            with col.container(border=True):
                st.markdown(f"**{day}**")
                for _, ev in day_events.iterrows():
                    st.caption(f"{STATUS_BADGE.get(ev['상태'], '⚪')} {ev['제목']}")

    st.divider()
    st.markdown("#### 이번 달 일정 목록")
    if month_events.empty:
        st.info("이번 달 등록된 일정이 없습니다.")
    else:
        for i, row in month_events.sort_values("날짜").iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"{STATUS_BADGE.get(row['상태'], '⚪')} **{row['날짜']} · {row['제목']}**  ·  담당: {row['담당자'] or '-'}")
                    if row["설명"]:
                        st.caption(row["설명"])
                with c2:
                    if st.button("삭제", key=f"del_event_{i}"):
                        db.delete_event(i)
                        st.rerun()
