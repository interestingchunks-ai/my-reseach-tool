import streamlit as st
import requests
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from datetime import datetime, timedelta
import json

# YouTube API Key
API_KEY = "AIzaSyC9blOG4-9SFwmJDF29md8qX9QUBztRnWc"

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title
st.title("📊 YouTube American History Viral Research Dashboard")

# Input Fields
days = st.number_input("7):", min_value=1, max_value=60, value=30)

# Keywords for American History niche
keywords = [
    "American History", "US History Documentary", "Civil War History",
    "Founding Fathers", "American Revolution", "Native American History",
    "World War 2 USA", "Cold War America", "Presidents of USA History", "European History"
]

if st.button("Fetch Data"):
    try:
        start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
        two_months_ago = datetime.utcnow() - timedelta(days=60)

        all_results = []

        for keyword in keywords:
            st.write(f"🔍 Searching for keyword: {keyword}")

            search_params = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "publishedAfter": start_date,
                "maxResults": 5,
                "key": API_KEY,
            }

            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            data = response.json()

            if "items" not in data or not data["items"]:
                continue

            videos = data["items"]
            video_ids = [video["id"]["videoId"] for video in videos]
            channel_ids = [video["snippet"]["channelId"] for video in videos]

            if not video_ids or not channel_ids:
                continue

            stats_params = {"part": "statistics,snippet", "id": ",".join(video_ids), "key": API_KEY}
            stats_response = requests.get(YOUTUBE_VIDEO_URL, params=stats_params)
            stats_data = stats_response.json()

            channel_params = {"part": "statistics,snippet,contentDetails", "id": ",".join(channel_ids), "key": API_KEY}
            channel_response = requests.get(YOUTUBE_CHANNEL_URL, params=channel_params)
            channel_data = channel_response.json()

            if "items" not in stats_data or "items" not in channel_data:
                continue

            stats = stats_data["items"]
            channels = channel_data["items"]

            for video, stat, channel in zip(videos, stats, channels):
                title = video["snippet"].get("title", "N/A")
                description = video["snippet"].get("description", "")[:200]
                video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"

                views = int(stat["statistics"].get("viewCount", 0))
                likes = int(stat["statistics"].get("likeCount", 0))
                comments = int(stat["statistics"].get("commentCount", 0))
                upload_time = stat["snippet"].get("publishedAt", "N/A")

                subs = int(channel["statistics"].get("subscriberCount", 0))
                total_views = int(channel["statistics"].get("viewCount", 0))
                total_videos = int(channel["statistics"].get("videoCount", 0))
                channel_creation = channel["snippet"].get("publishedAt", "N/A")
                channel_creation_date = datetime.strptime(channel_creation, "%Y-%m-%dT%H:%M:%SZ")

                # Engagement Metrics
                engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
                like_ratio = round((likes / views) * 100, 2) if views > 0 else 0
                comment_ratio = round((comments / views) * 100, 2) if views > 0 else 0

                # Channel Insights
                avg_views = round(total_views / total_videos, 2) if total_videos > 0 else 0
                upload_freq = round(total_videos / ((datetime.utcnow() - channel_creation_date).days / 7), 2) if total_videos > 0 else 0

                # Viral Score (weighted)
                viral_score = round((views/100000 + engagement_rate*2 + like_ratio + comment_ratio + avg_views/1000), 2)

                # Monetization Estimate (CPM $2-$5)
                est_earning = round((views/1000) * 3.5, 2)

                if channel_creation_date > two_months_ago and views >= 1000000:
                    all_results.append({
                        "Title": title,
                        "Description": description,
                        "URL": video_url,
                        "Views": views,
                        "Likes": likes,
                        "Comments": comments,
                        "Engagement Rate (%)": engagement_rate,
                        "Like/View Ratio (%)": like_ratio,
                        "Comment/View Ratio (%)": comment_ratio,
                        "Upload Time": upload_time,
                        "Subscribers": subs,
                        "Channel Created": channel_creation,
                        "Avg Views/Video": avg_views,
                        "Upload Freq (videos/week)": upload_freq,
                        "Viral Score": viral_score,
                        "Est. Earning ($)": est_earning
                    })

        if all_results:
            df = pd.DataFrame(all_results)
            st.success(f"✅ Found {len(all_results)} viral American History videos!")

            # Display results
            st.dataframe(df)

            # Export Options
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, "results.csv", "text/csv")

            excel = df.to_excel("results.xlsx", index=False)
            st.download_button("📊 Download Excel", csv, "results.xlsx")

            json_data = df.to_json(orient="records")
            st.download_button("🗂 Download JSON", json_data, "results.json")

            # Auto Report Summary
            st.subheader("📌 Auto Report Summary")
            top_channels = df.sort_values("Viral Score", ascending=False).head(3)
            for i, row in top_channels.iterrows():
                st.markdown(f"**{row['Title']}** → Viral Score: {row['Viral Score']} | Views: {row['Views']} | Subs: {row['Subscribers']}")

            # Word Cloud (SEO Keywords)
            st.subheader("☁️ Keyword Cloud")
            text = " ".join(df["Description"].tolist())
            wordcloud = WordCloud(width=800, height=400, background_color="white").generate(text)
            plt.imshow(wordcloud, interpolation="bilinear")
            plt.axis("off")
            st.pyplot(plt)

            # Graphs
            st.subheader("📊 Visual Insights")

            chart1 = alt.Chart(df).mark_circle(size=80).encode(
                x="Views", y="Engagement Rate (%)", color="Viral Score",
                tooltip=["Title", "Views", "Likes", "Comments", "Engagement Rate (%)", "Viral Score"]
            ).interactive()
            st.altair_chart(chart1, use_container_width=True)

            chart2 = alt.Chart(df).mark_bar().encode(
                x="Title", y="Views", color="Subscribers",
                tooltip=["Title", "Views", "Subscribers"]
            ).properties(width=700).interactive()
            st.altair_chart(chart2, use_container_width=True)

            chart3 = alt.Chart(df).mark_circle(size=100).encode(
                x="Subscribers", y="Views", size="Engagement Rate (%)", color="Viral Score",
                tooltip=["Title", "Subscribers", "Views", "Engagement Rate (%)", "Viral Score"]
            ).interactive()
            st.altair_chart(chart3, use_container_width=True)

        else:
            st.warning("No viral American History channels found in the last 2 months.")

    except Exception as e:
        st.error(f"An error occurred: {e}")
