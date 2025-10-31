import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd

# --------------------------------------------------
# 🔑 اپنی YouTube Data API Key یہاں ڈالیں
# --------------------------------------------------
API_KEY = "AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc"

# --------------------------------------------------
# 🔧 YouTube API initialize کریں
# --------------------------------------------------
def get_youtube_service():
    return build("youtube", "v3", developerKey=API_KEY)

# --------------------------------------------------
# 📅 پچھلے ایک مہینے کی تاریخ
# --------------------------------------------------
def one_month_ago():
    return (datetime.now() - timedelta(days=30)).isoformat("T") + "Z"

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
# 📊 چینلز کا ڈیٹا جمع کریں
# --------------------------------------------------
def analyze_channels(videos):
    channel_data = {}
    for v in videos:
        snippet = v["snippet"]
        stats = v["statistics"]
        ch_id = snippet["channelId"]
        ch_title = snippet["channelTitle"]
        thumb = snippet["thumbnails"]["medium"]["url"]
        views = int(stats.get("viewCount", 0))

        if ch_id not in channel_data:
            channel_data[ch_id] = {
                "title": ch_title,
                "views": 0,
                "thumb": thumb,
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
        if info["views"] > 1_000_000
    ])
    return df.sort_values("Total Views (last month)", ascending=False)

# --------------------------------------------------
# 🎨 Streamlit UI
# --------------------------------------------------
st.set_page_config(page_title="US YouTube Trending Channels", page_icon="📺", layout="wide")

st.title("🇺🇸 YouTube Trending Channels (USA)")
st.markdown("""
یہ ایپ YouTube Data API کے ذریعے امریکہ کے وہ چینلز دکھاتی ہے جن کے پچھلے ایک مہینے میں **1,000,000+ ویوز** آئے ہوں۔  
ڈیٹا تازہ ترین ٹرینڈنگ ویڈیوز سے لیا جاتا ہے۔
""")

# --------------------------------------------------
# 🧭 بٹن اور ایکشن
# --------------------------------------------------
if st.button("🚀 Fetch Trending Channels"):
    with st.spinner("Fetching trending data from YouTube..."):
        youtube = get_youtube_service()
        videos = get_trending_videos(youtube, region_code="US")
        df = analyze_channels(videos)

        if df.empty:
            st.warning("کوئی چینل نہیں ملا جس کے پچھلے ایک مہینے میں 1M+ ویوز ہوں۔")
        else:
            st.success(f"🎉 {len(df)} چینلز ملے جن کے پچھلے ایک مہینے میں 1M+ ویوز ہیں۔")

            for _, row in df.iterrows():
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.image(row["Thumbnail"], width=100)
                with col2:
                    st.markdown(f"### [{row['Channel']}]({row['Link']})")
                    st.markdown(f"**Total Views (last month):** {row['Total Views (last month)']:,}")
                st.divider()

st.caption("Data Source: YouTube Data API v3 | Developed with ❤️ using Streamlit")
