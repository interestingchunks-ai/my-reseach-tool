import streamlit as st
import requests
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from datetime import datetime, timedelta
from dateutil import parser
from io import BytesIO

# -----------------------------
# Config
# -----------------------------
API_KEY = st.secrets.get("AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

st.title("📊 Viral New YouTube Channels Finder (Multi-Niche)")

# -----------------------------
# Inputs
# -----------------------------
recent_days = st.number_input("Channel age limit (days)", min_value=1, max_value=120, value=60)
min_total_views = st.number_input("Minimum channel total views", min_value=0, value=1_000_000)
min_video_views = st.number_input("Minimum single-video views", min_value=0, value=1_000_000)
max_channels_per_keyword = st.number_input("Max channels per keyword", min_value=1, max_value=50, value=10)
videos_to_check_per_channel = st.number_input("Videos to analyze per channel (latest N)", min_value=1, max_value=50, value=10)

# Allow user to add custom keywords
user_keywords = st.text_area(
    "Add extra keywords (comma-separated)",
    value="Astrology Urdu, Viral Motivation, Couple Advice, Supercar Review, Boeing 777, Deep Sea, Night Sky Photography, Mars Mission"
)

# -----------------------------
# Keywords (Multi-Niche defaults)
# -----------------------------
default_keywords = [
    # Astrology & Spirituality
    "Astrology", "Horoscope", "Zodiac Signs", "Palmistry", "Numerology", "Spiritual Guidance",
    "Planets Astrology", "Moon Signs", "Astrological Predictions",

    # Motivation & Self Help
    "Motivational Speech", "Self Improvement", "Success Stories", "Inspiration", "Personal Growth",
    "Life Coaching", "Positive Thinking", "Overcoming Failure",

    # Love & Relationships
    "Love Advice", "Relationship Tips", "Marriage Advice", "Dating Tips", "Breakup Recovery",
    "Love and Relationship Stories", "Couple Goals", "Romantic Advice",

    # Cars & Automobiles
    "Car Reviews", "Luxury Cars", "Electric Cars", "Car Modifications", "Supercars",
    "Classic Cars", "Car Racing", "Automobile Technology",

    # Airplanes & Aviation
    "Airplane Takeoff", "Airplane Landing", "Fighter Jets", "Commercial Aviation",
    "Airplane Technology", "Pilot Training", "Airbus vs Boeing",

    # Sea & Ocean
    "Sea Exploration", "Deep Sea Creatures", "Ocean Documentary", "Ships and Boats",
    "Navy Ships", "Submarines", "Marine Life", "Underwater World",

    # Sky & Space
    "Night Sky", "Astronomy", "Stars and Galaxies", "Milky Way", "Sky Watching",
    "Space Exploration", "NASA Discoveries", "Black Holes", "Universe Documentary",

    # Planets & Solar System
    "Planets Documentary", "Mars Exploration", "Moon Landing", "Saturn Rings",
    "Jupiter Storms", "Solar System", "Exoplanets", "Space Science"
]

# Merge defaults + user keywords
extra = [k.strip() for k in user_keywords.split(",") if k.strip()]
keywords = list(dict.fromkeys(default_keywords + extra))  # dedupe while preserving order

# -----------------------------
# Helpers
# -----------------------------
def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def parse_iso(dt_str):
    try:
        return parser.isoparse(dt_str)
    except Exception:
        # Fallback trim microseconds if present
        try:
            clean = dt_str.split(".")[0] + "Z"
            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return None

def engagement_rate(likes, comments, views):
    return round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0

def viral_score(total_views, avg_er, avg_views_video):
    # Balanced channel momentum score
    return round((total_views / 1_000_000) * 1.0 + avg_er * 2.0 + (avg_views_video / 1000) * 1.0, 2)

def est_earning_usd(views, cpm=3.5):
    # Simple CPM-based estimate
    return round((views / 1000.0) * cpm, 2)

def bytes_excel(df, sheet="Channels"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet)
    output.seek(0)
    return output

# -----------------------------
# Fetch helpers
# -----------------------------
def search_new_channels(keyword, published_after_iso, max_results):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "channel",
        "order": "date",  # newest first
        "publishedAfter": published_after_iso,
        "maxResults": max_results,
        "key": API_KEY,
    }
    r = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=30)
    return r.json().get("items", [])

def get_channel_details(channel_ids):
    if not channel_ids:
        return []
    params = {
        "part": "statistics,snippet,contentDetails",
        "id": ",".join(channel_ids),
        "key": API_KEY,
    }
    r = requests.get(YOUTUBE_CHANNEL_URL, params=params, timeout=30)
    return r.json().get("items", [])

def get_latest_upload_ids(uploads_playlist_id, max_results):
    if not uploads_playlist_id:
        return []
    params = {
        "part": "snippet",
        "playlistId": uploads_playlist_id,
        "maxResults": max_results,
        "key": API_KEY,
    }
    r = requests.get(YOUTUBE_PLAYLIST_ITEMS_URL, params=params, timeout=30).json()
    items = r.get("items", [])
    vids = []
    for it in items:
        vid = it.get("snippet", {}).get("resourceId", {}).get("videoId")
        if vid:
            vids.append(vid)
    return vids

def get_videos_stats(video_ids):
    if not video_ids:
        return []
    params = {
        "part": "statistics,snippet",
        "id": ",".join(video_ids),
        "key": API_KEY,
    }
    r = requests.get(YOUTUBE_VIDEO_URL, params=params, timeout=30)
    return r.json().get("items", [])

# -----------------------------
# Main logic
# -----------------------------
if st.button("Fetch Channels"):
    try:
        cutoff_dt = datetime.utcnow() - timedelta(days=int(recent_days))
        cutoff_iso = cutoff_dt.isoformat("T") + "Z"

        rows = []
        seen_channels = set()

        for kw in keywords:
            st.write(f"🔎 Searching: {kw}")
            found = search_new_channels(kw, cutoff_iso, max_results=int(max_channels_per_keyword))
            if not found:
                continue

            channel_ids = []
            for it in found:
                cid = it.get("id", {}).get("channelId") or it.get("snippet", {}).get("channelId")
                if cid:
                    channel_ids.append(cid)
            channel_ids = list(dict.fromkeys(channel_ids))

            details = get_channel_details(channel_ids)
            for ch in details:
                ch_id = ch.get("id")
                if not ch_id or ch_id in seen_channels:
                    continue

                c_snip = ch.get("snippet", {})
                c_stats = ch.get("statistics", {})
                c_det = ch.get("contentDetails", {})

                created_dt = parse_iso(c_snip.get("publishedAt", ""))
                if not created_dt or created_dt <= cutoff_dt:
                    continue

                subs = safe_int(c_stats.get("subscriberCount"))
                total_views = safe_int(c_stats.get("viewCount"))
                total_videos = safe_int(c_stats.get("videoCount"))

                uploads_id = c_det.get("relatedPlaylists", {}).get("uploads")
                latest_ids = get_latest_upload_ids(uploads_id, int(videos_to_check_per_channel))
                videos = get_videos_stats(latest_ids) if latest_ids else []

                sum_views = 0
                sum_er = 0.0
                max_views = 0
                viral_examples = []

                for vi in videos:
                    vs = vi.get("statistics", {})
                    sn = vi.get("snippet", {})

                    v_views = safe_int(vs.get("viewCount"))
                    v_likes = safe_int(vs.get("likeCount"))
                    v_comments = safe_int(vs.get("commentCount"))
                    er = engagement_rate(v_likes, v_comments, v_views)

                    sum_views += v_views
                    sum_er += er
                    max_views = max(max_views, v_views)

                    if v_views >= int(min_video_views):
                        v_id = vi.get("id")
                        v_title = sn.get("title", "N/A")
                        v_url = f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                        viral_examples.append(f"{v_title} ({v_views} views) → {v_url}")

                n_vids = max(len(videos), 1)
                avg_views_video = round(sum_views / n_vids, 2)
                avg_er = round(sum_er / n_vids, 2)

                # Core filter: total views OR any single recent video is viral
                if total_views < int(min_total_views) and max_views < int(min_video_views):
                    continue

                score = viral_score(total_views, avg_er, avg_views_video)
                est_monthly = est_earning_usd(avg_views_video * 30)

                rows.append({
                    "Keyword": kw,
                    "Channel Title": c_snip.get("title", "N/A"),
                    "Channel URL": f"https://www.youtube.com/channel/{ch_id}",
                    "Channel Description": (c_snip.get("description") or "")[:400],
                    "Subscribers": subs,
                    "Total Views": total_views,
                    "Total Videos": total_videos,
                    "Channel Created": created_dt.isoformat(),
                    "Avg Views/Video (latest)": avg_views_video,
                    "Avg Engagement Rate (%)": avg_er,
                    "Max Video Views (latest)": max_views,
                    "Viral Examples": " | ".join(viral_examples),
                    "Viral Score": score,
                    "Est. Monthly Earning ($)": est_monthly,
                })
                seen_channels.add(ch_id)

        if not rows:
            st.warning("No new viral channels found for current thresholds. Try lowering minimum views or increasing videos-to-check.")
            st.stop()

        df = pd.DataFrame(rows)
        st.success(f"✅ Found {len(df)} new viral channels created within last {recent_days} days!")

        # -----------------------------
        # Display
        # -----------------------------
        st.dataframe(df)

        # -----------------------------
        # Exports
        # -----------------------------
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", data=csv_bytes, file_name="channels.csv", mime="text/csv")

        xls_bytes = bytes_excel(df, sheet="Channels")
        st.download_button("📊 Download Excel (XLSX)", data=xls_bytes,
                           file_name="channels.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        json_str = df.to_json(orient="records")
        st.download_button("🗂 Download JSON", data=json_str, file_name="channels.json", mime="application/json")

        # -----------------------------
        # WordCloud (Channel titles)
        # -----------------------------
        st.subheader("☁️ Keyword cloud (channel titles)")
        text_blob = " ".join(df["Channel Title"].astype(str).tolist())
        if text_blob.strip():
            wc = WordCloud(width=900, height=400, background_color="white").generate(text_blob)
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.info("No channel titles available to generate word cloud.")

        # -----------------------------
        # Visual insights
        # -----------------------------
        st.subheader("📊 Visual insights")

        chart1 = alt.Chart(df).mark_circle(size=90).encode(
            x=alt.X("Total Views:Q", title="Total Channel Views"),
            y=alt.Y("Avg Engagement Rate (%):Q", title="Avg ER (%)"),
            color=alt.Color("Viral Score:Q", scale=alt.Scale(scheme="plasma")),
            tooltip=["Channel Title", "Keyword", "Subscribers", "Total Views", "Avg Views/Video (latest)", "Avg Engagement Rate (%)", "Viral Score"]
        ).interactive()
        st.altair_chart(chart1, use_container_width=True)

        chart2 = alt.Chart(df).mark_bar().encode(
            x=alt.X("Channel Title:N", sort="-y", title="Channel"),
            y=alt.Y("Max Video Views (latest):Q", title="Max views among latest videos"),
            color=alt.Color("Subscribers:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["Channel Title", "Max Video Views (latest)", "Subscribers"]
        ).properties(width=900).interactive()
        st.altair_chart(chart2, use_container_width=True)

        chart3 = alt.Chart(df).mark_circle(size=110).encode(
            x=alt.X("Subscribers:Q", title="Subscribers"),
            y=alt.Y("Total Views:Q", title="Total Views"),
            size=alt.Size("Avg Engagement Rate (%):Q", title="Avg ER (%)"),
            color=alt.Color("Viral Score:Q", scale=alt.Scale(scheme="magma")),
            tooltip=["Channel Title", "Subscribers", "Total Views", "Avg Engagement Rate (%)", "Viral Score"]
        ).interactive()
        st.altair_chart(chart3, use_container_width=True)

        # -----------------------------
        # Auto report summary (Top 5)
        # -----------------------------
        st.subheader("📌 Top 5 by Viral Score")
        top5 = df.sort_values("Viral Score", ascending=False).head(5)
        for _, row in top5.iterrows():
            st.markdown(
                f"- **{row['Channel Title']}** ({row['Keyword']}) → Score: {row['Viral Score']} | Subs: {row['Subscribers']} | Total Views: {row['Total Views']} | Avg ER: {row['Avg Engagement Rate (%)']}%  \n"
                f"  {row['Channel URL']}"
            )

    except Exception as e:
        st.error(f"An error occurred: {e}")
