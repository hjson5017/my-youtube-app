import re
from urllib.parse import urlparse, parse_qs

import requests
import streamlit as st
from openai import OpenAI

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="유튜브 댓글 AI 요약", page_icon="💬", layout="centered")

DEFAULT_URL_1 = "https://youtu.be/d95J8yzvjbQ?si=LfL5DLwCL8Pk077r"  # 예시 1: 딥마인드 다큐 (영어 댓글)
DEFAULT_URL_2 = "https://youtu.be/I9vK5EVTt0U?si=NEZ8L7MRuNvrzINa"  # 예시 2: 2002 월드컵 추억 (한국어 댓글)

# 세션 상태(streamlit이 새로고침돼도 값을 기억하게 해주는 저장소) 초기화
if "url_input" not in st.session_state:
    st.session_state.url_input = DEFAULT_URL_1
if "comments" not in st.session_state:
    st.session_state.comments = None  # 댓글 목록을 여기에 저장해둠
if "summary" not in st.session_state:
    st.session_state.summary = None  # AI 요약 결과를 여기에 저장해둠


def set_url(url: str):
    """예시 버튼을 눌렀을 때 입력창 값을 바꿔주는 함수"""
    st.session_state.url_input = url
    # 링크가 바뀌었으니 이전에 가져온 댓글/요약은 초기화
    st.session_state.comments = None
    st.session_state.summary = None


# =========================================================
# 유튜브 링크에서 영상 ID 뽑아내기
# =========================================================
def extract_video_id(url: str):
    """
    youtu.be/영상ID?si=... 형태와
    youtube.com/watch?v=영상ID&... 형태를 모두 처리해서
    순수한 영상 ID(11자리 문자열)만 뽑아냄.
    실패하면 None을 돌려줌.
    """
    if not url:
        return None

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    host = parsed.netloc.lower()

    # 1) youtu.be/영상ID  형태 (짧은 링크)
    if "youtu.be" in host:
        video_id = parsed.path.lstrip("/")
        # 혹시 뒤에 슬래시가 더 붙어있으면 첫 부분만 사용
        video_id = video_id.split("/")[0]
        return video_id if video_id else None

    # 2) youtube.com/watch?v=영상ID  형태 (일반 링크)
    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        if "v" in query and len(query["v"]) > 0:
            return query["v"][0]
        # /embed/영상ID, /shorts/영상ID 같은 형태도 대비
        path_parts = parsed.path.split("/")
        for part in path_parts:
            if len(part) == 11:  # 유튜브 영상 ID는 보통 11자리
                return part
        return None

    return None


# =========================================================
# 유튜브 댓글 가져오기 (YouTube Data API v3)
# =========================================================
def fetch_comments(video_id: str, api_key: str):
    """
    commentThreads API를 호출해서 댓글을 최대 100개 가져옴.
    성공하면 [{'text': 댓글내용, 'likes': 좋아요수}, ...] 형태의 리스트를 돌려주고,
    실패하면 None을 돌려줌 (에러 메시지는 별도로 st.error로 출력).
    """
    endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "order": "relevance",  # 최신순이 아니라 '좋아요 많은 순(관련도순)'
        "maxResults": 100,
        "textFormat": "plainText",
        "key": api_key,
    }

    response = requests.get(endpoint, params=params, timeout=15)

    if response.status_code != 200:
        # API 호출 자체가 실패한 경우 (키 오류, 댓글 사용 중지 등)
        return None

    data = response.json()
    items = data.get("items", [])

    comments = []
    for item in items:
        try:
            top_comment = item["snippet"]["topLevelComment"]["snippet"]
            text = top_comment.get("textOriginal", "")
            likes = top_comment.get("likeCount", 0)
            comments.append({"text": text, "likes": likes})
        except (KeyError, TypeError):
            continue  # 형식이 이상한 항목은 건너뜀

    if not comments:
        return None

    # 좋아요 많은 순으로 정렬
    comments.sort(key=lambda c: c["likes"], reverse=True)
    return comments


# =========================================================
# Solar API로 AI 세 줄 요약 만들기
# =========================================================
def summarize_comments(comments: list, api_key: str):
    """
    댓글 전체를 Solar API(solar-open2 모델)에 보내서
    '전체 반응 한국어 세 줄 요약 + 긍/부정 비율 추정'을 받아옴.
    성공하면 요약 문자열을, 실패하면 None을 돌려줌.
    """
    client = OpenAI(api_key=api_key, base_url="https://api.upstage.ai/v1")

    # 댓글들을 하나의 텍스트 덩어리로 합침
    comments_text = "\n".join(f"- ({c['likes']}개 좋아요) {c['text']}" for c in comments)

    prompt = (
        "다음은 하나의 유튜브 영상에 달린 댓글 목록입니다. "
        "이 댓글들을 읽고 시청자들의 전체 반응을 한국어로 정확히 세 줄로 요약해주세요. "
        "그리고 마지막 줄에는 댓글 전체 분위기를 바탕으로 긍정/부정 비율을 "
        "대략적인 백분율로 추정해서 함께 적어주세요. (예: 긍정 70% / 부정 30%)\n\n"
        f"댓글 목록:\n{comments_text}"
    )

    response = client.chat.completions.create(
        model="solar-open2",
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="none",  # 추론(생각) 기능 끄기
    )

    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError):
        return None


# =========================================================
# 화면 구성 (UI)
# =========================================================
st.title("💬 유튜브 댓글 AI 요약")
st.caption("유튜브 영상 링크를 넣으면 인기 댓글을 모아 AI가 세 줄로 요약해줍니다.")

# --- 예시 버튼 두 개 (나란히 배치) ---
col1, col2 = st.columns(2)
with col1:
    st.button(
        "예시 1 · 딥마인드 다큐(영어 댓글)",
        use_container_width=True,
        on_click=set_url,
        args=(DEFAULT_URL_1,),
    )
with col2:
    st.button(
        "예시 2 · 2002 월드컵 추억(한국어 댓글)",
        use_container_width=True,
        on_click=set_url,
        args=(DEFAULT_URL_2,),
    )

# --- 링크 입력창 ---
video_url = st.text_input("유튜브 영상 링크를 붙여넣으세요", key="url_input")

# --- 댓글 가져오기 버튼 ---
if st.button("댓글 가져오기", type="primary"):
    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("⚠️ 링크에서 영상 ID를 찾을 수 없어요. 유튜브 링크 형식을 다시 확인해주세요.")
    else:
        # secrets 금고에서 유튜브 API 키 불러오기
        youtube_api_key = st.secrets.get("YOUTUBE_API_KEY")
        if not youtube_api_key:
            st.error("⚠️ YOUTUBE_API_KEY가 설정되어 있지 않아요. 앱 설정의 secrets를 확인해주세요.")
        else:
            with st.spinner("댓글을 불러오는 중이에요..."):
                comments = fetch_comments(video_id, youtube_api_key)

            if comments is None:
                st.error(
                    "⚠️ 댓글을 가져오지 못했어요. 댓글 사용이 꺼져 있거나, "
                    "영상 링크 또는 API 키에 문제가 있을 수 있어요."
                )
                st.session_state.comments = None
            else:
                st.session_state.comments = comments
                st.session_state.summary = None  # 새로 가져왔으니 이전 요약은 초기화
                st.success(f"댓글 {len(comments)}개를 가져왔어요!")

# --- 댓글 결과 표시 ---
if st.session_state.comments:
    comments = st.session_state.comments

    st.metric("가져온 댓글 수", f"{len(comments)}개")

    # 표로 보여주기 (좋아요 수 + 댓글 내용)
    table_data = [{"좋아요": c["likes"], "댓글": c["text"]} for c in comments]
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    st.divider()

    # --- AI 세 줄 요약 버튼 ---
    if st.button("✨ AI 세 줄 요약"):
        solar_api_key = st.secrets.get("SOLAR_API_KEY")
        if not solar_api_key:
            st.error("⚠️ SOLAR_API_KEY가 설정되어 있지 않아요. 앱 설정의 secrets를 확인해주세요.")
        else:
            with st.spinner("AI가 댓글을 읽고 요약하는 중이에요..."):
                try:
                    summary = summarize_comments(comments, solar_api_key)
                except Exception:
                    summary = None

            if summary is None:
                st.error("⚠️ 요약을 만드는 데 실패했어요. 잠시 후 다시 시도해주세요.")
                st.session_state.summary = None
            else:
                st.session_state.summary = summary

    if st.session_state.summary:
        st.subheader("📝 AI 세 줄 요약")
        st.info(st.session_state.summary)
