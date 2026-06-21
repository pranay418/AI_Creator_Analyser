import streamlit as st
import pandas as pd
import altair as alt
import time
import re
import urllib.parse
import database as db
import fetcher
import moderator

# Set page configuration - must be the first Streamlit command
st.set_page_config(
    page_title="AI Creator Safety & Content Moderator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize the database on startup
db.init_db()

# Premium dashboard styling CSS (dark theme, glassmorphic elements, status badges)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Title text gradient */
    .title-text {
        background: linear-gradient(90deg, #10B981 0%, #3B82F6 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    
    .subtitle-text {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Glassmorphic cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 16px;
        padding: 24px;
        border: 1px rgba(255, 255, 255, 0.08) solid;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }
    
    /* Custom metric panels */
    .metric-card {
        background: rgba(15, 23, 42, 0.3);
        border-radius: 12px;
        padding: 18px;
        border-left: 4px solid #3b82f6;
        border-top: 1px rgba(255, 255, 255, 0.05) solid;
        border-right: 1px rgba(255, 255, 255, 0.05) solid;
        border-bottom: 1px rgba(255, 255, 255, 0.05) solid;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 600;
        color: #ffffff;
        margin: 5px 0;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Status Badge styling */
    .badge {
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-proper { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-toxic { background: rgba(249, 115, 22, 0.15); color: #f97316; border: 1px solid rgba(249, 115, 22, 0.3); }
    .badge-abusive { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-harmful { background: rgba(127, 29, 29, 0.3); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-spam { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
    
    /* Highlighted text inside comments */
    .flagged-highlight {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        font-weight: 600;
        padding: 2px 4px;
        border-radius: 4px;
        border-bottom: 1px dashed #ef4444;
    }
    
    /* Custom button styling */
    .stButton>button {
        background: linear-gradient(135deg, #10B981 0%, #3B82F6 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
        background: linear-gradient(135deg, #059669 0%, #2563EB 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Helper to highlight flagged terms in text case-insensitively
def highlight_flagged_words(text, flagged_str):
    if not flagged_str:
        return text
    
    # Split flagged string into distinct tokens
    flagged_tokens = [w.strip() for w in flagged_str.split(",") if w.strip()]
    
    # Sort by length descending to prevent sub-string highlights overlapping
    flagged_tokens.sort(key=len, reverse=True)
    
    highlighted = text
    for token in flagged_tokens:
        # Ignore systemic tags
        if token in ["URL_LINK", "YELLING", "Excessive Emojis"]:
            continue
            
        try:
            # Escape regex characters
            escaped_token = re.escape(token)
            # Use regex to replace case-insensitively
            pattern = re.compile(f"({escaped_token})", re.IGNORECASE)
            highlighted = pattern.sub(r'<span class="flagged-highlight">\1</span>', highlighted)
        except Exception:
            pass
            
    return highlighted

# --- SIDEBAR CONTROLS ---

with st.sidebar:
    st.markdown("<h2 style='text-align: center; font-weight: 800; color: #10B981;'>🛡️ CREATOR SHIELD</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.85rem; margin-top: -10px; margin-bottom: 25px;'>AI Content Moderation Dashboard</p>", unsafe_allow_html=True)
    
    st.markdown("### Navigation")
    menu = st.radio(
        "Go To",
        ["🔍 Scan Creator Link", "📊 Creator Dashboard", "🛡️ Manage Flagged Content"],
        index=0
    )
    
    st.markdown("---")
    st.markdown("### API Configurations")
    
    # Load default keys from Streamlit secrets if available
    gemini_secrets_key = ""
    yt_secrets_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            gemini_secrets_key = st.secrets["GEMINI_API_KEY"]
        if "YOUTUBE_API_KEY" in st.secrets:
            yt_secrets_key = st.secrets["YOUTUBE_API_KEY"]
    except Exception:
        pass
    
    gemini_key = st.text_input(
        "Google Gemini API Key:",
        type="password",
        value=gemini_secrets_key,
        placeholder="AI-key...",
        help="Optional. Enter your Gemini API key to enable state-of-the-art LLM safety analysis."
    )
    
    youtube_key = st.text_input(
        "YouTube API Key:",
        type="password",
        value=yt_secrets_key,
        placeholder="AIzaSy...",
        help="Optional. Enter a YouTube Data API Key to fetch real live comments from YouTube links."
    )
    
    st.markdown("---")
    st.markdown("### System Tools")
    
    if st.button("Reset Dashboard Database", use_container_width=True):
        db.reset_db()
        st.success("Database reset complete!")
        time.sleep(0.5)
        st.rerun()

# --- HEADER BANNER ---
st.markdown("<div class='title-text'>Creator Shield</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-text'>Analyze profiles and comments to detect Abusive, Toxic, and Harmful social content.</div>", unsafe_allow_html=True)

# --- PAGE 1: SCAN CREATOR LINK ---
if menu == "🔍 Scan Creator Link":
    st.markdown("### ⚡ Fetch & Moderation Engine")
    
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        profile_url = st.text_input(
            "Paste Creator Profile, Video, or Thread URL:",
            placeholder="e.g., https://www.reddit.com/r/gaming/comments/..., https://www.youtube.com/watch?v=..., https://instagram.com/mrbeast"
        )
        
        st.markdown("""
        <small style="color: #94a3b8;">
            💡 Supported targets:<br>
            • <b>Reddit</b>: Any post URL (Full live comment parsing, no keys needed!)<br>
            • <b>YouTube</b>: Video link (Uses YouTube Key if provided, otherwise runs in simulation)<br>
            • <b>Instagram / Twitter / TikTok</b>: Profile page (Runs in simulation mode to model creator feeds)
        </small>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        scan_btn = st.button("🚀 Analyze Creator Content", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    if scan_btn:
        if not profile_url:
            st.error("Please enter a valid URL.")
        else:
            with st.spinner("📥 Step 1: Connecting to creator feed and fetching comments..."):
                try:
                    creator_name, platform, comments, was_simulated = fetcher.fetch_creator_comments(
                        profile_url, 
                        youtube_api_key=youtube_key if youtube_key.strip() else None
                    )
                except Exception as e:
                    st.error(f"Failed to fetch comments: {e}")
                    comments = []
                    
            if not comments:
                st.error("Could not retrieve any comments from this URL. Please verify the link is public and active.")
            else:
                st.info(f"Loaded {len(comments)} comments. Classifying now...")
                
                with st.spinner("🤖 Step 2: Moderating content using AI engine (Evaluating Safety & Spam)..."):
                    try:
                        # Perform moderation
                        moderated_comments = moderator.moderate_comments(
                            comments, 
                            gemini_api_key=gemini_key if gemini_key.strip() else None
                        )
                        
                        # Save results to SQLite
                        db.add_or_update_creator(profile_url, platform, creator_name)
                        avg_safety = db.save_comments(profile_url, moderated_comments)
                        
                        st.toast("🎉 Analysis finished successfully!")
                        st.success(f"### 🎉 Scan Completed for **{creator_name}**!")
                        
                        # Show notification if simulation was used
                        if was_simulated:
                            st.warning("""
                            ℹ️ **Note**: This platform (or missing YouTube Key) runs in **Simulation Mode**. 
                            We generated a realistic dataset representing typical creator comment activity to demonstrate 
                            toxicity, abuse, and spam detection features.
                            """)
                            
                        # Layout Summary
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"""
                            <div class="metric-card" style="border-left-color: #10B981;">
                                <div class="metric-label">Creator / Target</div>
                                <div class="metric-value" style="font-size: 1.5rem; line-height: 2.2rem; padding: 4px 0;">{creator_name}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"""
                            <div class="metric-card" style="border-left-color: #3b82f6;">
                                <div class="metric-label">Platform</div>
                                <div class="metric-value">{platform}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col3:
                            # Color coding safety score
                            safety_color = "#10b981"
                            if avg_safety < 50: safety_color = "#ef4444"
                            elif avg_safety < 80: safety_color = "#f59e0b"
                            
                            st.markdown(f"""
                            <div class="metric-card" style="border-left-color: {safety_color};">
                                <div class="metric-label">Community Safety Score</div>
                                <div class="metric-value" style="color: {safety_color};">{avg_safety}%</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("📊 View Creator Safety Dashboard"):
                            st.rerun() # Re-runs so dashboard tab detects the data
                            
                    except Exception as e:
                        st.error(f"Moderation Engine failure: {e}")

# --- PAGE 2: CREATOR DASHBOARD ---
elif menu == "📊 Creator Dashboard":
    st.markdown("### 📊 Creator Moderation Dashboard")
    
    creators_df = db.get_creators()
    
    if creators_df.empty:
        st.info("No scanned creator links found. Go to 'Scan Creator Link' to parse your first profile!")
    else:
        # Creator Selectbox
        creator_options = {row["profile_url"]: f"{row['creator_name']} ({row['platform']} - Safety: {row['safety_score']}%)" for _, row in creators_df.iterrows()}
        selected_url = st.selectbox(
            "Select Creator Profile to Inspect:",
            options=list(creator_options.keys()),
            format_func=lambda x: creator_options[x]
        )
        
        # Load Analytics data
        analytics = db.get_creator_analytics(selected_url)
        
        if analytics:
            # 1. Gauge Section / Safety Summary
            safety = analytics["safety_score"]
            
            # Determine color & text explanation
            if safety >= 90:
                safety_color = "#10b981"
                safety_text = "Extremely clean and friendly community environment. Very low risk."
                accent_card = "border-left-color: #10b981;"
            elif safety >= 70:
                safety_color = "#f59e0b"
                safety_text = "Generally healthy discussion with occasional toxicity or spam. Moderate safety."
                accent_card = "border-left-color: #f59e0b;"
            elif safety >= 50:
                safety_color = "#f97316"
                safety_text = "High toxicity/abuse detected. Community guidelines are frequently violated."
                accent_card = "border-left-color: #f97316;"
            else:
                safety_color = "#ef4444"
                safety_text = "Severely hostile community environment. Immediate moderation action required."
                accent_card = "border-left-color: #ef4444;"
                
            st.markdown(f"""
            <div class="glass-card" style="text-align: center; padding: 30px; {accent_card}">
                <h3 style="margin-top: 0; color: #94a3b8; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px;">Safety Index Rating</h3>
                <div style="font-size: 5rem; font-weight: 800; color: {safety_color}; margin: 10px 0; line-height: 1.1;">{safety}%</div>
                <p style="color: #cbd5e0; font-size: 1.1rem; max-width: 500px; margin: 10px auto 0 auto; font-weight: 400;">{safety_text}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 2. Main Metrics Row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: #3b82f6;">
                    <div class="metric-label">Platform</div>
                    <div class="metric-value" style="font-size: 1.8rem;">{analytics['platform']}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: #8b5cf6;">
                    <div class="metric-label">Total Comments</div>
                    <div class="metric-value">{analytics['total_comments']}</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                flagged_cnt = sum([analytics["class_counts"][c] for c in ["Toxic", "Abusive", "Harmful", "Spam"]])
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: #ef4444;">
                    <div class="metric-label">Flagged Issues</div>
                    <div class="metric-value">{flagged_cnt}</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                last_scanned_dt = pd.to_datetime(analytics['last_scanned']).strftime("%Y-%m-%d %H:%M")
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: #10B981;">
                    <div class="metric-label">Last Scanned</div>
                    <div class="metric-value" style="font-size: 1.5rem; padding: 5px 0;">{last_scanned_dt}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Chart Layout
            st.markdown("### 📊 Distribution of Content Safety")
            col_chart, col_leaderboard = st.columns([3, 2])
            
            with col_chart:
                # Convert counts dict to DataFrame
                chart_data = pd.DataFrame({
                    "Category": list(analytics["class_counts"].keys()),
                    "Count": list(analytics["class_counts"].values())
                })
                
                # Sort it to present cleanly
                cat_order = ["Proper", "Spam", "Toxic", "Abusive", "Harmful"]
                chart_data["order"] = chart_data["Category"].apply(lambda x: cat_order.index(x) if x in cat_order else 9)
                chart_data = chart_data.sort_values("order")
                
                # Map categories to premium hex colors
                color_scale = alt.Scale(
                    domain=["Proper", "Spam", "Toxic", "Abusive", "Harmful"],
                    range=["#10B981", "#F59E0B", "#F97316", "#EF4444", "#7F1D1D"]
                )
                
                bar_chart = alt.Chart(chart_data).mark_bar(
                    cornerRadiusTopRight=8,
                    cornerRadiusBottomRight=8
                ).encode(
                    x=alt.X("Count:Q", title="Number of Comments"),
                    y=alt.Y("Category:N", sort=cat_order, title=None),
                    color=alt.Color("Category:N", scale=color_scale, legend=None),
                    tooltip=["Category", "Count"]
                ).properties(height=250)
                
                st.altair_chart(bar_chart, use_container_width=True)
                
            with col_leaderboard:
                st.markdown("#### 🚫 Chronic Offenders (Top Flagged Users)")
                top_violators = analytics["top_abusive_users"]
                
                if top_violators.empty:
                    st.success("No offenders found! Community members are behaving properly.")
                else:
                    st.write("These users have posted multiple comments flagged as spam, toxic, or abusive:")
                    st.dataframe(
                        top_violators.rename(columns={
                            "author": "User Handle",
                            "violations_count": "Violating Comments"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                    st.markdown("""
                    <small style="color: #94a3b8;">
                        ⚠️ <b>Action Tip</b>: You can export these handles as a custom blocklist in the <i>Manage Flagged Content</i> tab.
                    </small>
                    """, unsafe_allow_html=True)
            
            # Simple creator cleanup option
            st.markdown("---")
            if st.button("🗑️ Delete Scan Records for this Creator"):
                db.delete_creator(selected_url)
                st.success("Creator records deleted.")
                time.sleep(0.5)
                st.rerun()

# --- PAGE 3: MANAGE FLAGGED CONTENT ---
elif menu == "🛡️ Manage Flagged Content":
    st.markdown("### 🛡️ Moderation & Blocklist Manager")
    
    creators_df = db.get_creators()
    
    if creators_df.empty:
        st.info("No scanned creator links found. Go to 'Scan Creator Link' to populate data first!")
    else:
        # Creator Selectbox
        creator_options = {row["profile_url"]: f"{row['creator_name']} ({row['platform']})" for _, row in creators_df.iterrows()}
        selected_url = st.selectbox(
            "Select Creator Feed to Manage:",
            options=list(creator_options.keys()),
            format_func=lambda x: creator_options[x]
        )
        
        # Load all comments for this creator
        comments_df = db.get_comments(selected_url)
        
        if comments_df.empty:
            st.info("No comments found in database for this creator.")
        else:
            # 1. Filters block
            st.markdown("#### ⚙️ Filtering Settings")
            col_f1, col_f2 = st.columns([1, 2])
            
            with col_f1:
                search_term = st.text_input("Search comments:", placeholder="Filter by text...")
            with col_f2:
                st.write("Show categories:")
                cats_cols = st.columns(5)
                show_proper = cats_cols[0].checkbox("Proper", value=False)
                show_spam = cats_cols[1].checkbox("Spam", value=True)
                show_toxic = cats_cols[2].checkbox("Toxic", value=True)
                show_abusive = cats_cols[3].checkbox("Abusive", value=True)
                show_harmful = cats_cols[4].checkbox("Harmful", value=True)
                
            # Compile selected filters
            selected_cats = []
            if show_proper: selected_cats.append("Proper")
            if show_spam: selected_cats.append("Spam")
            if show_toxic: selected_cats.append("Toxic")
            if show_abusive: selected_cats.append("Abusive")
            if show_harmful: selected_cats.append("Harmful")
            
            # Apply filters
            filtered_df = comments_df[comments_df["classification"].isin(selected_cats)]
            if search_term:
                filtered_df = filtered_df[filtered_df["text"].str.contains(search_term, case=False)]
                
            # 2. Blocklist Export Panel
            st.markdown("#### 📥 Export Centers")
            c_exp1, c_exp2 = st.columns(2)
            
            with c_exp1:
                # Export comments to CSV
                csv_comments = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Export Filtered Comments (CSV)",
                    data=csv_comments,
                    file_name="shield_moderated_comments.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with c_exp2:
                # Generate Blocklist (Abusive/Harmful/Spam authors)
                blocked_df = comments_df[comments_df["classification"].isin(["Abusive", "Harmful", "Spam"])]
                unique_blocked_users = blocked_df["author"].unique()
                blocklist_data = pd.DataFrame({"Username": unique_blocked_users})
                csv_blocklist = blocklist_data.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    "🚫 Export Blocklist Handles (CSV)",
                    data=csv_blocklist,
                    file_name="creator_shield_blocklist.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="CSV containing unique usernames of users flagged as Abusive, Harmful, or Spam. Upload directly to social platform blocklists."
                )
                
            st.markdown(f"**Filtered Results:** Showing `{len(filtered_df)}` comments.")
            st.markdown("---")
            
            # 3. Render Comments List
            if filtered_df.empty:
                st.info("No comments match your filter criteria.")
            else:
                for idx, row in filtered_df.iterrows():
                    cat = row["classification"]
                    badge_class = "badge-proper"
                    if cat == "Spam": badge_class = "badge-spam"
                    elif cat == "Toxic": badge_class = "badge-toxic"
                    elif cat == "Abusive": badge_class = "badge-abusive"
                    elif cat == "Harmful": badge_class = "badge-harmful"
                    
                    # Formatting severity percentage
                    sev_pct = int(row["severity_score"] * 100)
                    sev_badge = f"<span style='color:#a0aec0; margin-left: 10px; font-size: 0.85rem;'>Severity: {sev_pct}%</span>" if sev_pct > 0 else ""
                    
                    # Triggers block
                    triggers = f"<br><small style='color: #ef4444;'><b>Triggers:</b> {row['flagged_words']}</small>" if row["flagged_words"] else ""
                    
                    # Highlight words in body
                    highlighted_body = highlight_flagged_words(row["text"], row["flagged_words"])
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="glass-card" style="padding: 18px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <div>
                                    <strong style="color: #60a5fa; font-size: 1.05rem;">{row['author']}</strong>
                                    <span class="badge {badge_class}" style="margin-left: 10px;">{cat}</span>
                                    {sev_badge}
                                </div>
                                <div style="color: #94a3b8; font-size: 0.85rem;">
                                    {row['timestamp']}
                                </div>
                            </div>
                            <div style="color: #e2e8f0; line-height: 1.5; font-size: 0.95rem; word-break: break-word;">
                                {highlighted_body}
                            </div>
                            {triggers}
                        </div>
                        """, unsafe_allow_html=True)
