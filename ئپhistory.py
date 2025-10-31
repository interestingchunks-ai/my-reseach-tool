import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd

# --------------------------------------------------
# 🔑 اپنی YouTube Data API Key یہاں ڈالیں
# --------------------------------------------------
API_KEY = "AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc"  # ← اپنی اصل API key یہاں ڈالیں

# --------------------------------------------------
# 🔧 YouTube API initialize کریں
# --------------------------------------------------
def get_youtube_service():
    return build("youtube", "v3", developerKey=API_KEY)

# --------------------------------------------------
# 📅 60 دن پہلے کی تاریخ
# --------------------------------------------------
def sixty_days_ago():
    return (datetime.utcnow() - timedelta(days=60)).isoformat("T") + "Z"

# --------------------------------------------------
# 🔍 امریکہ کے ٹرینڈنگ ویڈیوز نکالیں
# --------------------------------------------------
def get_trending_videos(youtube, region_code="US", max_results=50):
    request = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=max_results
    )
    response = request.execute()
    return response.get("items", [])

# --------------------------------------------------
# 📊 چینل کا ڈیٹا لائیں
# --------------------------------------------------
def get_channel_details(youtube, channel_id):
    request = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    )
    response = request.execute()
    if not response.get("items"):
        return None
    item = response["items"][0]
    snippet = item["snippet"]
    stats = item["statistics"]

    return {
        "channel_title": snippet.get("title"),
        "channel_created": snippet.get("publishedAt"),
        "subscribers": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0))
    }

# --------------------------------------------------
# 📈 ویڈیوز کو فلٹر کریں اور مکمل ڈیٹا بنائیں
# --------------------------------------------------
def process_videos(youtube, videos):
    data = []
    cutoff_date = datetime.utcnow() - timedelta(days=60)

    for v in videos:
        snippet = v["snippet"]
        stats = v["statistics"]

        video_title = snippet["title"]
        video_description = snippet.get("description", "")[:200] + "..."
        video_url = f"https://www.youtube.com/watch?v={v['id']}"
        video_views = int(stats.get("viewCount", 0))
        video_likes = int(stats.get("likeCount", 0)) if "likeCount" in stats else 0
        video_comments = int(stats.get("commentCount", 0)) if "commentCount" in stats else 0
        upload_time = snippet.get("publishedAt")
        channel_id = snippet["channelId"]

        # چینل ڈیٹا نکالنا
        channel_info = get_channel_details(youtube, channel_id)
        if not channel_info:
            continue

        channel_created_date = datetime.strptime(channel_info["channel_created"], "%Y-%m-%dT%H:%M:%SZ")
        if channel_created_date < cutoff_date:
            continue  # صرف وہی چینلز رہیں جو 60 دن میں بنے ہوں

        # فلٹر: لاکھوں ویوز
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
            "Subscribers": channel_info["subscribers"],
            "Channel Creation Date": channel_info["channel_created"],
            "Channel": channel_info["channel_title"]
        })

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.sort_values("Views", ascending=False).reset_index(drop=True)
    return df

# --------------------------------------------------
# 🎨 Streamlit UI
# --------------------------------------------------
st.set_page_config(page_title="New US YouTube Channels (Last 60 Days)", page_icon="📺", layout="wide")

st.title("🇺🇸 YouTube Channels (Last 60 Days & 1M+ Views)")
st.markdown("""
یہ ایپ YouTube Data API کے ذریعے امریکہ کے وہ چینلز دکھاتی ہے  
جو **پچھلے 60 دن** میں بنے ہوں اور جن کی ویڈیوز کے ویوز **1,000,000+** ہوں۔  
نیچے آپ کو ہر ویڈیو کی تفصیلی معلومات ملے گی۔
""")

if st.button("🚀 Fetch Trending Videos"):
    with st.spinner("📡 YouTube سے ڈیٹا حاصل کیا جا رہا ہے..."):
        youtube = get_youtube_service()
        videos = get_trending_videos(youtube, region_code="US", max_results=100)
        df = process_videos(youtube, videos)

        if df.empty:
            st.warning("❗ کوئی نیا چینل نہیں ملا جس کی ویڈیو کے ویوز 1M+ ہوں۔")
        else:
            st.success(f"🎉 {len(df)} ویڈیوز ملی ہیں جو شرائط پوری کرتی ہیں۔")

            for _, row in df.iterrows():
                st.markdown(f"## 🎬 [{row['Title']}]({row['URL']})")
                st.write(f"**Description:** {row['Description']}")
                st.write(f"**Views:** {row['Views']:,} | 👍 **Likes:** {row['Likes']:,} | 💬 **Comments:** {row['Comments']:,}")
                st.write(f"**Upload Time:** {row['Upload Time']}")
                st.write(f"**Channel:** {row['Channel']}")
                st.write(f"**Subscribers:** {row['Subscribers']:,}")
                st.write(f"**Channel Created:** {row['Channel Creation Date']}")
                st.divider()

st.caption("Data Source: YouTube Data API v3 | Developed with ❤️ using Streamlit")
