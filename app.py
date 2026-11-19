from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_PATH = Path(__file__).with_name("sales.csv")
MONTHS = list(range(1, 13))

st.set_page_config(page_title="월별 매출 목표 시뮬레이터", layout="wide")
st.title("월별 매출 목표 시뮬레이터")
st.caption("2026년 수업용 가상 매출 데이터 · 금액 단위 백만원")


@st.cache_data
def load_sales():
    return pd.read_csv(DATA_PATH)


try:
    sales = load_sales()
except FileNotFoundError:
    st.error("app.py와 같은 폴더에 sales.csv를 올려 주세요.")
    st.stop()

st.sidebar.header("목표 설정")
st.sidebar.caption("입력한 목표는 선택한 기간의 각 월에 적용됩니다.")

branches = sorted(sales["branch"].unique())
selected = st.sidebar.multiselect("조회할 지점", branches, default=branches)
quarter = st.sidebar.selectbox("기간", ["전체", "1분기", "2분기", "3분기", "4분기"])

if not selected:
    st.info("조회할 지점을 하나 이상 선택해 주세요.")
    st.stop()

targets = {}
for branch in selected:
    default_target = round(sales.loc[sales["branch"] == branch, "sales"].mean())
    targets[branch] = st.sidebar.number_input(
        f"{branch}지점 월 목표 (백만원)",
        min_value=1,
        value=max(1, default_target),
        step=5,
        key=f"target_{branch}",
    )

st.sidebar.caption("목표의 기본값은 각 지점의 연간 월평균 매출입니다.")

months = MONTHS
if quarter != "전체":
    start = (int(quarter[0]) - 1) * 3
    months = MONTHS[start:start + 3]

view = sales.loc[
    sales["branch"].isin(selected) & sales["month"].isin(months)
].copy()

if view.empty:
    st.info("선택한 기간에 매출 기록이 없습니다.")
    st.stop()

view = view.sort_values(["branch", "month"])
view["목표"] = view["branch"].map(targets)
view["달성률"] = 100 * view["sales"] / view["목표"]
view["부족액"] = (view["목표"] - view["sales"]).clip(lower=0)
missed = view.loc[view["부족액"] > 0]

left, middle, right = st.columns(3)
left.metric("기간 매출 달성률", f"{100 * view['sales'].sum() / view['목표'].sum():.1f}%")
middle.metric("목표 미달 건수", f"{len(missed)} / {len(view)}건")
right.metric("미달 건의 부족액 합계", f"{missed['부족액'].sum():,.0f} 백만원")
st.caption("기간 달성률은 매출 합계 ÷ 목표 합계입니다. 미달 건수는 지점·월별로 셉니다.")

st.subheader("어느 달에 목표를 달성했나")
coverage = view.pivot(
    index="branch", columns="month", values="달성률"
).reindex(columns=months)

heatmap = px.imshow(
    coverage,
    x=[f"{month}월" for month in months],
    y=[f"{branch}지점" for branch in coverage.index],
    labels={"x": "월", "y": "지점", "color": "달성률 (%)"},
    text_auto=".0f",
    aspect="auto",
    color_continuous_scale=["#c2410c", "#fff7ed", "#0369a1"],
    color_continuous_midpoint=100,
)
heatmap.update_layout(height=max(260, 70 * len(coverage.index) + 120))
st.plotly_chart(heatmap, width="stretch")

left, right = st.columns(2)

with left:
    st.subheader("실제 매출과 목표")
    comparison = view.rename(columns={"sales": "실제 매출"}).melt(
        id_vars=["month", "branch"],
        value_vars=["실제 매출", "목표"],
        var_name="구분",
        value_name="금액",
    )
    trend = px.line(
        comparison,
        x="month",
        y="금액",
        color="branch",
        line_dash="구분",
        labels={"month": "월", "branch": "지점", "금액": "금액 (백만원)"},
        color_discrete_sequence=["#0369a1", "#ea580c"],
    )
    trend.update_xaxes(tickvals=months, ticktext=[f"{month}월" for month in months])
    st.plotly_chart(trend, width="stretch")

with right:
    st.subheader("부족액이 큰 지점과 월")
    if missed.empty:
        st.success("선택한 기간의 모든 기록이 목표를 달성했습니다.")
    else:
        ranking = missed.nlargest(8, "부족액").assign(
            항목=lambda rows: rows["branch"] + "지점 " + rows["month"].astype(str) + "월"
        )
        gaps = px.bar(
            ranking,
            x="부족액",
            y="항목",
            orientation="h",
            text_auto=True,
            labels={"부족액": "부족액 (백만원)", "항목": ""},
        )
        gaps.update_traces(marker_color="#c2410c")
        gaps.update_yaxes(autorange="reversed")
        st.plotly_chart(gaps, width="stretch")

st.subheader("월별 실적 내려받기")
only_missed = st.toggle("목표 미달 건만 보기")
detail = (missed if only_missed else view).rename(
    columns={"month": "월", "branch": "지점", "sales": "실제 매출"}
)
detail = detail[["월", "지점", "실제 매출", "목표", "달성률", "부족액"]].round(
    {"달성률": 1}
)
st.dataframe(detail, hide_index=True, width="stretch")
st.download_button(
    "표를 CSV로 저장",
    data=detail.to_csv(index=False).encode("utf-8-sig"),
    file_name="sales_target_results.csv",
    mime="text/csv",
    disabled=detail.empty,
)
