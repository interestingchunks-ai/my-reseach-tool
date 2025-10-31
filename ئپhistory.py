import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from dateutil import parser
import pandas as pd

API_KEY = "AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc"  # ← اپنی API key یہاں ڈالیں

# -------------------------
# YouTube API Helper Functions
# -------------------------
def get_youtube_service():
    return build("youtube", "v3", developerKey=API_KEY)

def sixty_days_ago():
    return datetime.utcnow() - timedelta(days=60)

def get_trending_videos(youtube, region_code="US", max_results=50):
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results
        )
        response = request.execute()
        return response.get("items", [])
    except Exception as e:
        st.error(f"Error fetching trending videos: {e}")
        return []

def get_channel_details(youtube, channel_id):
    try:
        response = youtube.channels().list(
            part="snippet,statistics",
            id=channel_id
        ).execute()
        items = response.get("items", [])
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        stats = items[0].get("statistics", {})
        return {
            "channel_title": snippet.get("title", "Unknown"),
            "channel_created": snippet.get("publishedAt"),
            "subscribers": int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else 0
        }
    except Exception:
        return None

# -------------------------
# Process Videos (Safe Version)
# -------------------------
def process_videos(youtube, videos):
    data = []
    cutoff_date = sixty_days_ago()

    for v in videos:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})

        video_title = snippet.get("title", "No Title")
        video_description = snippet.get("description", "")[:200] + "..."
        video_id = v.get("id", "")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_views = int(stats.get("viewCount", 0))
        video_likes = int(stats.get("likeCount", 0)) if stats.get("likeCount") else 0
        video_comments = int(stats.get("commentCount", 0)) if stats.get("commentCount") else 0
        upload_time = snippet.get("publishedAt")
        channel_id = snippet.get("channelId", "")

        channel_info = get_channel_details(youtube, channel_id)
        if not channel_info:
            continue

        channel_created_str = channel_info.get("channel_created")
        channel_created_date = None
        if channel_created_str:
            try:
                channel_created_date = parser.isoparse(channel_created_str)
            except Exception:
                channel_created_date = None

        # 🔹 Fully safe checks
        if channel_created_date is None:
            continue
        if not isinstance(channel_created_date, datetime):
            continue
        if channel_created_date < cutoff_date:
            continue

        # Only videos with 1M+ views
        if video_views < 1_000_000:
            continue

        data.append({
            "Title": video_title,
            "Description": video_description,
            "URL": video_url,
            "Views": video_views,
            "Likes": video_likes,
            "Comments": video_comments,
            "Upload Time": upload_time,
            "Subscribers": channel_info.get("subscribers", 0),
            "Channel Creation Date": channel_created_str,
            "Channel": channel_info.get("channel_title", "Unknown")
        })

    return pd.DataFrame(data)

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="US New YouTube Channels", page_icon="📺", layout="wide")
st.title("🇺🇸 US YouTube Channels (Last 60 Days & 1M+ Views)")

st.markdown("یہ ایپ US کے چینلز دکھاتی ہے جو پچھلے 60 دن میں بنے اور جن کی ویڈیوز 1,000,000+ ویوز رکھتی ہیں۔")

if st.button("🚀 Fetch Latest Videos"):
    with st.spinner("Fetching data from YouTube..."):
        youtube = get_youtube_service()
        videos = get_trending_videos(youtube, region_code="US", max_results=100)
        df = process_videos(youtube, videos)

        if df.empty:
            st.warning("❗ کوئی چینل نہیں ملا جو criteria پورا کرتا ہو۔")
        else:
            st.success(f"🎉 {len(df)} ویڈیوز ملی ہیں۔")
            for _, row in df.iterrows():
                st.markdown(f"## 🎬 [{row['Title']}]({row['URL']})")
                st.write(f"**Description:** {row['Description']}")
                st.write(f"**Views:** {row['Views']:,} | 👍 {row['Likes']:,} | 💬 {row['Comments']:,}")
                st.write(f"**Upload Time:** {row['Upload Time']}")
                st.write(f"**Channel:** {row['Channel']}")
                st.write(f"**Subscribers:** {row['Subscribers']:,}")
                st.write(f"**Channel Created:** {row['Channel Creation Date']}")
                st.divider()

st.caption("Data Source: YouTube Data API v3 | Developed with ❤️ using Streamlit")
