좋아! 여기서 이어서 고쳐줘. 2단계야.
- 받아온 댓글 전체를 단어로 나눠서, 자주 나온 단어 상위 20개를 세어줘.
  한 글자짜리 단어는 빼줘.
- 상위 20개를 plotly 가로 막대그래프로 보여줘. 많이 나온 단어가 위에 오게.
- requirements.txt에 plotly를 추가해줘.# -*- coding: utf-8 -*-
"""
유튜브 댓글 분석 앱 - 1단계
- 유튜브 영상 링크를 입력하면, YouTube Data API v3로 댓글을 최대 100개 가져옵니다.
- 좋아요가 많은 순(order=relevance)으로 요청해서, 좋아요 많은 순으로 정렬해 보여줍니다.
- 스트림릿 클라우드 배포를 기준으로 작성했습니다.
"""

import re                    # 유튜브 링크에서 영상 ID를 뽑아내기 위한 정규표현식 라이브러리
import requests               # 외부 API(YouTube Data API)에 요청을 보내기 위한 라이브러리
import pandas as pd           # 표 형태 데이터를 다루기 위한 라이브러리
import streamlit as st        # 웹 대시보드를 만드는 라이브러리


# -----------------------------
# 1) 기본 화면 설정
# -----------------------------
st.set_page_config(
    page_title="유튜브 댓글 분석기",
    page_icon="💬",
    layout="wide",  # 화면을 넓게 써서 표가 잘 보이도록 설정
)

st.title("💬 유튜브 댓글 분석기 (1단계)")
st.caption("유튜브 영상 링크를 넣으면, 좋아요가 많은 순으로 댓글을 최대 100개 가져옵니다.")


# -----------------------------
# 2) 예시 링크 정의
#    - 예시 버튼을 누르면 아래 링크가 입력창에 채워집니다.
# -----------------------------
EXAMPLE_1_URL = "https://youtu.be/d95J8yzvjbQ?si=LfL5DLwCL8Pk077r"  # 딥마인드 다큐 (영어 댓글)
EXAMPLE_2_URL = "https://youtu.be/I9vK5EVTt0U?si=NEZ8L7MRuNvrzINa"  # 2002 월드컵 추억 (한국어 댓글)

# 입력창의 값은 st.session_state에 "youtube_url"이라는 이름으로 저장해서 관리합니다.
# (이렇게 하면 예시 버튼을 눌렀을 때 입력창 내용을 코드에서 직접 바꿀 수 있습니다.)
if "youtube_url" not in st.session_state:
    st.session_state.youtube_url = EXAMPLE_1_URL  # 처음 화면을 열었을 때의 기본값


def use_example_1():
    """'예시 1' 버튼을 누르면 입력창을 예시1 링크로 채웁니다."""
    st.session_state.youtube_url = EXAMPLE_1_URL


def use_example_2():
    """'예시 2' 버튼을 누르면 입력창을 예시2 링크로 채웁니다."""
    st.session_state.youtube_url = EXAMPLE_2_URL


# -----------------------------
# 3) 예시 버튼 두 개를 나란히 배치
# -----------------------------
example_col1, example_col2 = st.columns(2)

with example_col1:
    st.button(
        "예시 1 · 딥마인드 다큐(영어 댓글)",
        on_click=use_example_1,
        use_container_width=True,
    )

with example_col2:
    st.button(
        "예시 2 · 2002 월드컵 추억(한국어 댓글)",
        on_click=use_example_2,
        use_container_width=True,
    )


# -----------------------------
# 4) 유튜브 링크 입력창
#    - key="youtube_url"로 지정해서 위 session_state 값과 자동으로 연결됩니다.
# -----------------------------
youtube_url = st.text_input(
    "유튜브 영상 링크를 붙여넣으세요",
    key="youtube_url",
)


# -----------------------------
# 5) 링크에서 영상 ID(11자리) 뽑아내기
#    - youtu.be/영상ID (짧은 링크)
#    - youtube.com/watch?v=영상ID (일반 링크)
#    - youtube.com/shorts/영상ID, youtube.com/embed/영상ID 도 함께 지원
#    - si=, t= 같이 뒤에 붙는 부가 값은 전부 무시합니다.
# -----------------------------
def extract_video_id(url: str):
    """유튜브 링크 문자열에서 11자리 영상 ID를 뽑아 반환합니다. 못 찾으면 None을 반환합니다."""
    if not url:
        return None

    url = url.strip()

    # 패턴 1: youtu.be/영상ID (짧은 링크)
    match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # 패턴 2: youtube.com/watch?v=영상ID (물음표 뒤 v= 파라미터)
    match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # 패턴 3: youtube.com/shorts/영상ID 또는 youtube.com/embed/영상ID
    match = re.search(r"youtube\.com/(?:shorts|embed)/([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)

    return None


video_id = extract_video_id(youtube_url)

if not video_id:
    # 링크 형식이 잘못되어 영상 ID를 못 찾은 경우, 여기서 안내하고 이후 로직은 실행하지 않음
    st.warning("😥 링크에서 영상 ID를 찾지 못했습니다. 유튜브 영상 링크가 맞는지 확인해 주세요.")
    st.stop()

st.caption(f"인식된 영상 ID: `{video_id}`")


# -----------------------------
# 6) YouTube API 키 불러오기 (secrets에서만 불러오고, 코드에는 절대 적지 않음)
# -----------------------------
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    # secrets.toml에 YOUTUBE_API_KEY가 없거나 스트림릿 클라우드 Secrets 설정을 안 한 경우
    st.error(
        "🔑 API 키(YOUTUBE_API_KEY)를 찾을 수 없습니다.\n\n"
        "스트림릿 클라우드의 'Settings > Secrets'에 아래와 같이 등록해 주세요.\n\n"
        "```\nYOUTUBE_API_KEY = \"발급받은_API_키\"\n```"
    )
    st.stop()


# -----------------------------
# 7) YouTube Data API v3 - commentThreads 호출 함수
# -----------------------------
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


@st.cache_data(ttl=3600)  # 같은 영상은 1시간 동안 재요청하지 않고 캐시를 사용 (API 사용량 절약)
def fetch_comments(api_key: str, video_id: str):
    """
    YouTube commentThreads API를 호출해 댓글을 최대 100개 가져옵니다.
    성공하면 (True, 댓글리스트) 를 반환하고,
    실패하면 (False, 에러메시지) 를 반환합니다.
    """
    params = {
        "part": "snippet",       # 댓글 내용(snippet)만 요청
        "videoId": video_id,     # 조회할 영상 ID
        "order": "relevance",    # 최신순이 아니라 '좋아요/관련도' 순으로 요청
        "maxResults": 100,       # 한 번에 받아올 수 있는 최대 개수
        "textFormat": "plainText",
        "key": api_key,
    }

    try:
        response = requests.get(YOUTUBE_COMMENTS_URL, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        # 인터넷 연결 문제, 타임아웃 등 요청 자체가 실패한 경우
        return False, f"YouTube 서버에 연결하는 중 문제가 발생했습니다. (상세: {e})"

    try:
        data = response.json()
    except ValueError:
        return False, "YouTube 서버 응답을 이해할 수 없습니다. (JSON 형식이 아닙니다)"

    # 요청이 실패한 경우 (잘못된 영상 ID, 댓글 사용 중지된 영상, API 키 오류 등)
    if response.status_code != 200:
        error_info = data.get("error", {})
        reason = ""
        if error_info.get("errors"):
            reason = error_info["errors"][0].get("reason", "")
        message = error_info.get("message", "알 수 없는 오류")

        # 댓글이 막혀 있는 영상인 경우, 조금 더 구체적으로 안내
        if reason == "commentsDisabled":
            return False, "이 영상은 댓글 기능이 꺼져 있어 댓글을 가져올 수 없습니다."
        # 영상 ID 자체가 존재하지 않는 경우
        if reason == "videoNotFound":
            return False, "해당 영상을 찾을 수 없습니다. 링크가 올바른지 확인해 주세요."

        return False, f"YouTube API에서 오류를 반환했습니다: {message}"

    items = data.get("items", [])

    if not items:
        return False, "가져올 수 있는 댓글이 없습니다. (댓글이 0개이거나 비공개 처리된 영상일 수 있습니다)"

    return True, items


# -----------------------------
# 8) 실제 댓글 요청
# -----------------------------
with st.spinner("YouTube에서 댓글을 불러오는 중입니다..."):
    ok, result = fetch_comments(YOUTUBE_API_KEY, video_id)

if not ok:
    # 요청 실패 시, 친절한 한국어 안내를 보여주고 종료
    st.error(f"😥 댓글을 가져오지 못했습니다.\n\n{result}")
    st.stop()

comment_items = result


# -----------------------------
# 9) 응답에서 필요한 값(댓글 원문, 좋아요 수 등)만 뽑아 DataFrame 구성
# -----------------------------
rows = []
for item in comment_items:
    top_comment = item["snippet"]["topLevelComment"]["snippet"]
    rows.append(
        {
            "댓글": top_comment.get("textOriginal", ""),
            "좋아요수": top_comment.get("likeCount", 0),
            "작성자": top_comment.get("authorDisplayName", ""),
        }
    )

df = pd.DataFrame(rows)

# 좋아요수는 숫자로 오지만, 혹시 모를 상황을 대비해 한 번 더 숫자형으로 변환
df["좋아요수"] = pd.to_numeric(df["좋아요수"], errors="coerce").fillna(0).astype(int)

# 좋아요가 많은 순으로 정렬
df = df.sort_values("좋아요수", ascending=False).reset_index(drop=True)


# -----------------------------
# 10) 가져온 댓글 개수를 지표 카드로 크게 보여주기
# -----------------------------
st.subheader("📊 요약")

col1, col2 = st.columns(2)
col1.metric("가져온 댓글 개수", f"{len(df):,}개")
col2.metric("가장 많은 좋아요 수", f"{df['좋아요수'].max():,}개")

st.divider()


# -----------------------------
# 11) 댓글 목록을 좋아요 수와 함께 표로 보여주기
# -----------------------------
st.subheader("📋 댓글 목록 (좋아요 많은 순)")

st.dataframe(
    df[["좋아요수", "댓글", "작성자"]],
    use_container_width=True,
    hide_index=True,
)

st.caption("자료 출처: YouTube Data API v3 (commentThreads)")
