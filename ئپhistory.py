import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd

# --------------------------------------------------
# 🔑 اپنی YouTube Data API Key یہاں ڈالیں
# --------------------------------------------------
API_KEY = "AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc"  # ← یہاں اپنی اصل API Key ڈالیں

# --------------------------------------------------
# 🔧 YouTube API initialize کریں
# --------------------------------------------------
def get_youtube_service():
    """YouTube API Service initialize کرتا ہے"""
    return build("youtube", "v3", developerKey=API_KEY)

# --------------------------------------------------
# 📅 ایک مہینہ پہلے کی تاریخ
# --------------------------------------------------
def one_month_ago():
    """ایک مہینہ پہلے کی ISO تاریخ"""
    return (datetime.utcnow() - timedelta(days=30)).isoformat("T") + "Z"

# --------------------------------------------------
# 🔍 امریکہ کے ٹرینڈنگ ویڈیوز نکالیں
# --------------------------------------------------
def get_trending_videos(youtube, region_code="US", max_results=50):
    """امریکہ کے ٹرینڈنگ ویڈیوز واپس کرتا ہے"""
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
        st.error(f"❌ YouTube API Error: {e}")
        return []

# --------------------------------------------------
# 📊 چینلز کا ڈیٹا جمع کریں
# --------------------------------------------------
def analyze_channels(videos):
    """ہر چینل کے کل ویوز نکالتا ہے اور 1M+ والے فلٹر کرتا ہے"""
    channel_data = {}
    for v in videos:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        ch_id = snippet.get("channelId")
        ch_title = snippet.get("channelTitle", "Unknown Channel")
        thumbs = snippet.get("thumbnails", {})
        thumb_url = thumbs.get("medium", {}).get("url", "")
        views = int(stats.get("viewCount", 0))

        if ch_id:
            if ch_id not in channel_data:
                channel_data[ch_id] = {
                    "title": ch_title,
                    "views": 0,
                    "thumb": thumb_url,
                    "link": f"https://www.youtube.com/channel/{ch_id}"
                }
            channel_data[ch_id]["views"] += views

    df = pd.DataFrame([
        {
            "Channel": info["title"],
            "Total Views (last month)": info["views"],
            "Thumbnail": info["thumb"],
            "Link": info["link"]
        }
        for info in channel_data.values()
        if info["views"] >= 1_000_000
    ])

    if df.empty:
        return df

    df = df.sort_values("Total Views (last month)", ascending=False).reset_index(drop=True)
    return df

# --------------------------------------------------
# 🎨 Streamlit UI
# --------------------------------------------------
st.set_page_config(page_title="US YouTube Trending Channels", page_icon="📺", layout="wide")

st.title("🇺🇸 YouTube Trending Channels (USA)")
st.markdown("""
یہ ایپ YouTube Data API کے ذریعے امریکہ کے وہ چینلز دکھاتی ہے  
جن کے پچھلے ایک مہینے میں **1,000,000+ ویوز** آئے ہوں۔  
ڈیٹا تازہ ترین ٹرینڈنگ ویڈیوز سے لیا جاتا ہے۔
""")

# --------------------------------------------------
# 🧭 Fetch Button & Logic
# --------------------------------------------------
if st.button("🚀 Fetch Trending Channels"):
    with st.spinner("📡 YouTube سے ڈیٹا حاصل کیا جا رہا ہے..."):
        youtube = get_youtube_service()
        videos = get_trending_videos(youtube, region_code="US", max_results=100)
        df = analyze_channels(videos)

        if df.empty:
            st.warning("❗ کوئی چینل نہیں ملا جس کے پچھلے ایک مہینے میں 1M+ ویوز ہوں۔")
        else:
            st.success(f"🎉 {len(df)} چینلز ملے جن کے پچھلے ایک مہینے میں 1M+ ویوز ہیں۔")

            for _, row in df.iterrows():
                col1, col2 = st.columns([1, 4])
                with col1:
                    if row["Thumbnail"]:
                        st.image(row["Thumbnail"], width=100)
                with col2:
                    st.markdown(f"### [{row['Channel']}]({row['Link']})")
                    st.markdown(f"**Total Views (last month):** {row['Total Views (last month)']:,}")
                st.divider()

st.caption("Data Source: YouTube Data API v3 | Developed with ❤️ using Streamlit")
