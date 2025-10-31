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
API_KEY = st.secrets.get("YOUTUBE_API_KEY", "Enter your API Key here")
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

# -----------------------------
# Keywords (Multi-Niche)
# -----------------------------
keywords = [
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

# -----------------------------
# Helpers
# -----------------------------
def safe_int(x):
    try: return int(x)
    except: return 0

def parse_iso(dt_str):
    try: return parser.isoparse(dt_str)
    except: return None

def engagement_rate(likes, comments, views):
    return round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0

def viral_score(total_views, avg_er, avg_views_video):
    return round((total_views/1_000_000) + avg_er*2 + (avg_views_video/1000), 2)

def est_earning_usd(views, cpm=3.5):
    return round((views/1000.0)*cpm, 2)

def bytes_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Channels")
    output.seek(0)
    return output

# -----------------------------
# Main
# -----------------------------
if st.button("Fetch Channels"):
    cutoff_dt = datetime.utcnow() - timedelta(days=int(recent_days))
    cutoff_iso = cutoff_dt.isoformat("T") + "Z"

    all_channels = []
    seen_channels = set()

    for kw in keywords:
        st.write(f"🔎 Searching: {kw}")
        params = {
            "part": "snippet",
            "q": kw,
            "type": "channel",
            "order": "date",
            "publishedAfter": cutoff_iso,
            "maxResults": int(max_channels_per_keyword),
            "key": API_KEY,
        }
        r = requests.get(YOUTUBE_SEARCH_URL, params=params).json()
        items = r.get("items", [])
        channel_ids = [it.get("id", {}).get("channelId") for it in items if it.get("id", {}).get("channelId")]

        if not channel_ids: continue
        c_params = {"part": "statistics,snippet,contentDetails", "id": ",".join(channel_ids), "key": API_KEY}
        c_resp = requests.get(YOUTUBE_CHANNEL_URL, params=c_params).json()
        details = c_resp.get("items", [])

        for ch in details:
            ch_id = ch.get("id")
            if not ch_id or ch_id in seen_channels: continue
            seen_channels.add(ch_id)

            c_snip = ch.get("snippet", {})
            c_stats = ch.get("statistics", {})
            c_details = ch.get("contentDetails", {})

            created_dt = parse_iso(c_snip.get("publishedAt", ""))
            if not created_dt or created_dt <= cutoff_dt: continue

            subs = safe_int(c_stats.get("subscriberCount"))
            total_views = safe_int(c_stats.get("viewCount"))
            total_videos = safe_int(c_stats.get("videoCount"))

            uploads_id = c_details.get("relatedPlaylists", {}).get("uploads")
            v_ids = []
            if uploads_id:
                v_params = {"part": "snippet", "playlistId": uploads_id, "maxResults": int(videos_to_check_per_channel), "key": API_KEY}
                v_resp = requests.get(YOUTUBE_PLAYLIST_ITEMS_URL, params=v_params).json()
                v_ids = [it.get("snippet", {}).get("resourceId", {}).get("videoId") for it in v_resp.get("items", []) if it.get("snippet", {}).get("resourceId", {}).get("videoId")]

            v_stats = []
            if v_ids:
                vs_params = {"part": "statistics,snippet", "id": ",".join(v_ids), "key": API_KEY}
                vs_resp = requests.get(YOUTUBE_VIDEO_URL, params=vs_params).json()
                v_stats = vs_resp.get("items", [])

            sum_views, sum_er, max_views = 0, 0, 0
            for vi in v_stats:
                vs = vi.get("statistics", {})
                views = safe_int(vs.get("viewCount"))
                likes = safe_int(vs.get("likeCount"))
                comments = safe_int(vs.get("commentCount"))
                er = engagement_rate(likes, comments, views)
                sum_views += views
                sum_er += er
                max_views = max(max_views, views)

            n = max(len(v_stats), 1)
            avg_views_video = round(sum_views/n, 2)
            avg_er = round(sum_er/n, 2)

            if total_views < min_total_views and max_views < min_video_views:
                continue

            score = viral_score(total_views, avg_er, avg_views_video)
            earning = est_earning_usd(avg_views_video*30)

            all_channels.append({
                "Channel Title": c_snip.get("title", "N/A"),
                "Channel URL": f"https://www.youtube.com/channel/{ch_id}",
                "Subscribers": subs,
                "Total Views": total_views,
                "Total Videos": total_videos,
                "Channel Created": created_dt.isoformat(),
                "Avg Views/Video": avg_views_video,
                "Avg Engagement Rate (%)": avg_er,
                "Max Video Views": max_views,
                "Viral Score": score,
                "Est. Monthly Earning ($)": earning,
            })

    if not all_channels:
        st.warning("No new viral channels found.")
    else:
        df = pd.DataFrame(all_channels)
        st.success(f"
