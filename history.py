import streamlit as st
import requests
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from datetime import datetime, timedelta
from dateutil import parser
from io import BytesIO
import json

# -----------------------------
# Config
# -----------------------------
API_KEY = st.secrets.get("AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

st.title("📊 YouTube American History Viral Research Dashboard")

# -----------------------------
# Inputs
# -----------------------------
days = st.number_input("Enter days to search (1–60):", min_value=1, max_value=60, value=30)
min_views = st.number_input("Minimum views (e.g., 1000000):", min_value=0, value=1000000)
recent_channel_days = st.number_input("Channel age limit in days:", min_value=1, max_value=120, value=60)

keywords = [
    # Keywords for Global History niche
keywords = [
    # American History
    "American History", "US History Documentary", "Civil War History",
    "Founding Fathers", "American Revolution", "Native American History",
    "World War 2 USA", "Cold War America", "Presidents of USA History",

    # European History
    "French Revolution", "Napoleon Bonaparte", "World War 1 History",
    "World War 2 History", "Roman Empire", "Greek History",
    "Medieval Europe", "Renaissance History", "Industrial Revolution",

    # Asian History
    "Chinese Dynasties", "Great Wall of China", "Mughal Empire",
    "Indian Independence", "Japanese Samurai History", "Meiji Restoration",
    "Korean History", "Vietnam War History", "Mongol Empire",

    # Middle Eastern & Islamic History
    "Islamic Golden Age", "Ottoman Empire", "Abbasid Caliphate",
    "Umayyad Caliphate", "Persian Empire", "Arab History",
    "Crusades History", "Baghdad History", "Andalusian History",

    # African History
    "Ancient Egypt", "Pharaohs History", "Pyramids History",
    "Mali Empire", "Colonial Africa", "Zulu Kingdom",
    "Ethiopian Empire", "African Independence Movements",

    # Global/World History
    "Ancient Civilizations", "Mesopotamia History", "Mayan Civilization",
    "Aztec Empire", "Inca Empire", "Cold War History",
    "History of Colonialism", "History of Slavery", "History of Democracy",
    "World History Documentary", "History of Empires", "History of Wars"
]
]

# -----------------------------
# Helpers
# -----------------------------
def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def parse_iso(dt_str):
    # Robust ISO parsing (handles microseconds and no-microseconds)
    try:
        return parser.isoparse(dt_str)
    except Exception:
        # Last fallback: trim microseconds if present
        try:
            clean = dt_str.split(".")[0] + "Z"
            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return None

def engagement_rate(likes, comments, views):
    return round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0

def like_ratio(likes, views):
    return round((likes / views) * 100, 2) if views > 0 else 0.0

def comment_ratio(comments, views):
    return round((comments / views) * 100, 2) if views > 0 else 0.0

def viral_score(views, er, lr, cr, avg_views):
    # Balanced, interpretable scoring
    # Scale views and avg_views to avoid dominance
    return round((views / 100000) * 1.0 + er * 2.0 + lr * 0.8 + cr * 1.2 + (avg_views / 1000) * 0.5, 2)

def est_earning_usd(views, cpm=3.5):
    return round((views / 1000.0) * cpm, 2)

def bytes_excel(df, sheet_name="Results"):
    # Reliable Excel export in-memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

# -----------------------------
# Fetch and process
# -----------------------------
if st.button("Fetch data"):
    try:
        start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
        channel_age_cutoff = datetime.utcnow() - timedelta(days=int(recent_channel_days))

        all_rows = []
        seen_video_ids = set()

        for keyword in keywords:
            st.write(f"🔍 Searching: {keyword}")

            search_params = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "publishedAfter": start_date,
                "maxResults": 10,
                "key": API_KEY,
            }
            r = requests.get(YOUTUBE_SEARCH_URL, params=search_params, timeout=30)
            search_data = r.json()

            if not search_data.get("items"):
                continue

            videos = search_data["items"]
            video_ids = [v["id"]["videoId"] for v in videos if v.get("id", {}).get("videoId")]
            channel_ids = [v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")]

            if not video_ids or not channel_ids:
                continue

            # Fetch video stats + snippet
            v_params = {"part": "statistics,snippet", "id": ",".join(video_ids), "key": API_KEY}
            v_resp = requests.get(YOUTUBE_VIDEO_URL, params=v_params, timeout=30).json()
            v_items = v_resp.get("items", [])

            # Map video id -> full video data
            video_map = {vi.get("id"): vi for vi in v_items if vi.get("id")}

            # Fetch channel stats + snippet (contentDetails optional)
            c_params = {"part": "statistics,snippet", "id": ",".join(set(channel_ids)), "key": API_KEY}
            c_resp = requests.get(YOUTUBE_CHANNEL_URL, params=c_params, timeout=30).json()
            c_items = c_resp.get("items", [])

            # Map channel id -> full channel data
            channel_map = {ci.get("id"): ci for ci in c_items if ci.get("id")}

            for v in videos:
                vid = v.get("id", {}).get("videoId")
                ch_id = v.get("snippet", {}).get("channelId")
                if not vid or not ch_id or vid in seen_video_ids:
                    continue

                vi = video_map.get(vid)
                ci = channel_map.get(ch_id)
                if not vi or not ci:
                    continue

                # Video fields
                v_snippet = vi.get("snippet", {})
                v_stats = vi.get("statistics", {})
                title = v_snippet.get("title", "N/A")
                description = v_snippet.get("description", "") or ""
                description = description[:400]
                video_url = f"https://www.youtube.com/watch?v={vid}"

                views = safe_int(v_stats.get("viewCount"))
                likes = safe_int(v_stats.get("likeCount"))
                comments = safe_int(v_stats.get("commentCount"))
                upload_time_raw = v_snippet.get("publishedAt", "")
                upload_dt = parse_iso(upload_time_raw)
                upload_time = upload_dt.isoformat() if upload_dt else upload_time_raw or "N/A"

                # Channel fields
                c_snippet = ci.get("snippet", {})
                c_stats = ci.get("statistics", {})
                subs = safe_int(c_stats.get("subscriberCount"))
                total_views = safe_int(c_stats.get("viewCount"))
                total_videos = safe_int(c_stats.get("videoCount"))
                channel_created_raw = c_snippet.get("publishedAt", "")
                ch_created_dt = parse_iso(channel_created_raw)

                # Filters
                if views < min_views:
                    continue
                if ch_created_dt is None or ch_created_dt <= channel_age_cutoff:
                    continue

                # Insights
                er = engagement_rate(likes, comments, views)
                lr = like_ratio(likes, views)
                cr = comment_ratio(comments, views)
                avg_views = round(total_views / total_videos, 2) if total_videos > 0 else 0.0
                weeks_since_creation = max((datetime.utcnow() - ch_created_dt).days / 7.0, 0.0001) if ch_created_dt else 0.0001
                upload_freq = round(total_videos / weeks_since_creation, 2) if total_videos > 0 else 0.0
                score = viral_score(views, er, lr, cr, avg_views)
                earning = est_earning_usd(views, cpm=3.5)

                all_rows.append({
                    "Title": title,
                    "Description": description,
                    "URL": video_url,
                    "Views": views,
                    "Likes": likes,
                    "Comments": comments,
                    "Engagement Rate (%)": er,
                    "Like/View Ratio (%)": lr,
                    "Comment/View Ratio (%)": cr,
                    "Upload Time": upload_time,
                    "Subscribers": subs,
                    "Channel Created": ch_created_dt.isoformat() if ch_created_dt else channel_created_raw or "N/A",
                    "Avg Views/Video": avg_views,
                    "Upload Freq (videos/week)": upload_freq,
                    "Viral Score": score,
                    "Est. Earning ($)": earning,
                })
                seen_video_ids.add(vid)

        if not all_rows:
            st.warning("No matching results for current filters. Try increasing days or lowering min views.")
            st.stop()

        df = pd.DataFrame(all_rows)
        st.success(f"✅ Found {len(df)} viral American History videos from new channels!")

        # -----------------------------
        # Display
        # -----------------------------
        st.dataframe(df)

        # -----------------------------
        # Exports
        # -----------------------------
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", data=csv_bytes, file_name="results.csv", mime="text/csv")

        xls_bytes = bytes_excel(df)
        st.download_button("📊 Download Excel (XLSX)", data=xls_bytes, file_name="results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        json_str = df.to_json(orient="records")
        st.download_button("🗂 Download JSON", data=json_str, file_name="results.json", mime="application/json")

        # -----------------------------
        # Auto report summary (Top 3)
        # -----------------------------
        st.subheader("📌 Auto report summary")
        top3 = df.sort_values("Viral Score", ascending=False).head(3)
        for _, row in top3.iterrows():
            st.markdown(
                f"- **Title:** {row['Title']}  \n"
                f"  **Viral Score:** {row['Viral Score']} | **Views:** {row['Views']} | **Subs:** {row['Subscribers']} | **Engagement:** {row['Engagement Rate (%)']}%"
            )

        # -----------------------------
        # Keyword cloud (from descriptions)
        # -----------------------------
        st.subheader("☁️ Keyword cloud (descriptions)")
        text_blob = " ".join(df["Description"].astype(str).tolist())
        if text_blob.strip():
            wc = WordCloud(width=900, height=400, background_color="white").generate(text_blob)
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.info("No description text available to generate a word cloud.")

        # -----------------------------
        # Visual insights
        # -----------------------------
        st.subheader("📊 Visual insights")

        chart1 = alt.Chart(df).mark_circle(size=80).encode(
            x=alt.X("Views:Q", title="Views"),
            y=alt.Y("Engagement Rate (%):Q", title="Engagement Rate (%)"),
            color=alt.Color("Viral Score:Q", scale=alt.Scale(scheme="plasma")),
            tooltip=["Title", "Views", "Likes", "Comments", "Engagement Rate (%)", "Viral Score"]
        ).interactive()
        st.altair_chart(chart1, use_container_width=True)

        chart2 = alt.Chart(df).mark_bar().encode(
            x=alt.X("Title:N", sort="-y"),
            y=alt.Y("Views:Q"),
            color=alt.Color("Subscribers:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["Title", "Views", "Subscribers"]
        ).properties(width=800).interactive()
        st.altair_chart(chart2, use_container_width=True)

        chart3 = alt.Chart(df).mark_circle(size=100).encode(
            x=alt.X("Subscribers:Q"),
            y=alt.Y("Views:Q"),
            size=alt.Size("Engagement Rate (%):Q"),
            color=alt.Color("Viral Score:Q", scale=alt.Scale(scheme="magma")),
            tooltip=["Title", "Subscribers", "Views", "Engagement Rate (%)", "Viral Score"]
        ).interactive()
        st.altair_chart(chart3, use_container_width=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
