import urllib.request
import urllib.parse
import json
import re
from datetime import datetime, timedelta
import random

def extract_username_or_id(url, platform):
    """Extracts a handle, username, or video ID from a profile/content URL."""
    url = url.split("?")[0].strip()
    
    if platform == "Reddit":
        # Check if it is a post
        if "/comments/" in url:
            match = re.search(r"/comments/([^/]+)", url)
            if match:
                return f"Reddit Post: {match.group(1)}"
        # Check if it is a user
        match = re.search(r"/user/([^/]+)", url)
        if match:
            return f"u/{match.group(1)}"
        # Check if it is a subreddit
        match = re.search(r"/r/([^/]+)", url)
        if match:
            return f"r/{match.group(1)}"
            
    elif platform == "YouTube":
        # Extract video ID
        video_pattern = r"(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=|\&v=)([^#\&\?]*)"
        match = re.search(video_pattern, url)
        if match:
            return match.group(1)
            
    elif platform == "Instagram":
        match = re.search(r"instagram\.com/([^/]+)", url)
        if match:
            return f"@{match.group(1)}"
            
    elif platform == "Twitter/X":
        match = re.search(r"(?:twitter|x)\.com/([^/]+)", url)
        if match:
            return f"@{match.group(1)}"
            
    elif platform == "TikTok":
        match = re.search(r"tiktok\.com/(@[^/]+)", url)
        if match:
            return match.group(1)
            
    # Generic fallback
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if path:
        parts = path.split("/")
        return parts[-1] if parts else "creator"
        
    return "creator"

def detect_platform(url):
    """Detects social platform from URL."""
    url_lower = url.lower()
    if "reddit.com" in url_lower:
        return "Reddit"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "instagram.com" in url_lower:
        return "Instagram"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "Twitter/X"
    elif "tiktok.com" in url_lower:
        return "TikTok"
    return "Other"

# --- REDDIT FETCH ENGINE ---

def fetch_reddit_comments(url):
    """Fetches comments from a Reddit thread URL using public JSON endpoint."""
    url = url.split("?")[0].strip()
    
    # Ensure URL ends in .json
    if not url.endswith(".json"):
        if url.endswith("/"):
            url = url[:-1] + ".json"
        else:
            url = url + ".json"
            
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        comments = []
        if isinstance(data, list) and len(data) > 1:
            comments_payload = data[1]["data"]["children"]
            
            # Extract creator title from the thread itself
            thread_title = "Reddit Thread"
            try:
                thread_title = data[0]["data"]["children"][0]["data"]["title"]
            except Exception:
                pass
                
            # Helper to recursively parse comment trees
            def parse_node(node):
                if node.get("kind") == "t1":  # t1 = Comment
                    c_data = node["data"]
                    author = c_data.get("author", "Anonymous")
                    body = c_data.get("body", "")
                    created_utc = c_data.get("created_utc", None)
                    
                    if body and body != "[deleted]" and body != "[removed]":
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if created_utc:
                            timestamp = datetime.fromtimestamp(created_utc).strftime("%Y-%m-%d %H:%M:%S")
                            
                        comments.append({
                            "author": f"u/{author}",
                            "text": body,
                            "timestamp": timestamp
                        })
                        
                    # Recurse replies
                    replies = c_data.get("replies")
                    if replies and isinstance(replies, dict):
                        for reply in replies.get("data", {}).get("children", []):
                            parse_node(reply)
                            
            for child in comments_payload:
                parse_node(child)
                
            return thread_title, comments[:150]  # Limit to first 150 comments
            
    except Exception as e:
        print(f"Error fetching Reddit comments: {e}")
        
    return "Reddit Thread", []

# --- YOUTUBE FETCH ENGINE ---

def fetch_youtube_comments(video_id, api_key):
    """Fetches comments from a YouTube video using YouTube Data API."""
    url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={video_id}&maxResults=100&key={api_key}"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    
    try:
        # First, fetch video title
        video_title = f"YouTube Video: {video_id}"
        try:
            info_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
            info_req = urllib.request.Request(info_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(info_req, timeout=5) as info_res:
                info_data = json.loads(info_res.read().decode())
                if info_data.get("items"):
                    video_title = info_data["items"][0]["snippet"]["title"]
        except Exception:
            pass
            
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        comments = []
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            author = snippet.get("authorDisplayName", "Anonymous")
            text = snippet.get("textDisplay", "")
            
            # Remove HTML tags (br, a, etc.) YouTube API returns
            text_clean = re.sub(r"<[^<]+?>", "", text)
            
            published_at = snippet.get("publishedAt", "")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if published_at:
                # Format 2026-06-21T12:00:00Z -> 2026-06-21 12:00:00
                timestamp = published_at.replace("T", " ").replace("Z", "")
                
            comments.append({
                "author": author,
                "text": text_clean,
                "timestamp": timestamp
            })
            
        return video_title, comments
        
    except Exception as e:
        print(f"Error fetching YouTube comments: {e}")
        raise RuntimeError(f"YouTube API call failed: {e}")

# --- HIGH FIDELITY SIMULATION ENGINE ---

def generate_simulated_comments(creator_name, platform):
    """
    Generates realistic platform-specific comments with controlled categories 
    (Proper, Toxic, Abusive, Harmful, Spam) for testing & demonstration.
    """
    # Dynamic handles
    author_pool = [
        "alex_g", "gamerguy99", "sarah_reads", "crypto_king", "tech_guru",
        "troll_face42", "john_smith", "fit_life_chloe", "justin_b", "meme_lord",
        "hater_vibe", "spambot_3000", "creative_mind", "friendly_ghost", "curious_cat"
    ]
    
    # Templates mapped to categories
    templates = {
        "Proper": [
            "This is such an amazing video! Keep up the good work {creator}!",
            "I really agree with the points you made here. Very helpful.",
            "Can you make a follow-up post about this topic?",
            "Thanks for sharing this, learned something new today.",
            "Honestly the best content I've seen all week.",
            "So wholesome. Loving your channel lately!",
            "Simple, clean, and well explained. Great work.",
            "I support this 100%. Very logical points.",
            "You are a legend, thanks for posting this!",
            "Does anyone know the track playing in the background? Nice vibe."
        ],
        "Spam": [
            "Hey guys, check out my profile for free skins and gift cards! Link in bio!",
            "Earn $500 a day working from home! WhatsApp me at +1 (555) 0199!",
            "Subscribe to my channel for daily giveaways! I post cool stuff!",
            "Join our discord server discord.gg/crypto-scam-promo for free tokens!",
            "Click here to claim your free reward: www.scampromolink.click",
            "I make cool beats, check out my soundcloud page link on my profile!",
            "Unbelievable profits! Invested $50 and made $1000 in one week!",
            "Check my latest post to win a brand new iPhone 16!",
            "Cheap followers and likes! DM me on Instagram for cheap rates!",
            "Amazing! Also check out my videos if you have some free time"
        ],
        "Toxic": [
            "This video is absolute shit. What a waste of time.",
            "What the fuck did I just watch? Completely useless.",
            "This is trash, honestly. Please delete this crap.",
            "Bullshit arguments. Get your facts straight, idiot.",
            "I pissed my pants laughing at how bad this is.",
            "Shut the fuck up, you don't know what you're talking about.",
            "What a boring ass post. Moving on.",
            "This makes zero sense. So damn stupid.",
            "Screw this, I am unsubscribing right now.",
            "This sucks majorly. Horrible style."
        ],
        "Abusive": [
            "You are a brainless idiot. Why do people even follow you?",
            "You look so ugly and fat. Seriously, get a life or go to the gym.",
            "Worst creator ever. You are pathetic, worthless, and a fraud.",
            "You are disgusting and a total joke. Go hide in a cave, scum.",
            "Seriously, you are so dumb, my dog could explain this better.",
            "Shut up, you coward. You're just a trash human being.",
            "You're a clown. Stop pretending to be smart when you're brainless.",
            "Look at this loser. Can't even talk properly. Absolute garbage.",
            "Everyone hates you, just give up and quit.",
            "You look like trash. Go eat some dirt, faggot."
        ],
        "Harmful": [
            "Kill yourself right now. Nobody wants you here.",
            "Go die in a hole, you useless piece of human waste.",
            "I am going to find your address, dox you, and come beat you up.",
            "I will murder you if I ever see you in public, watch your back.",
            "You deserve to be shot. Go hang yourself.",
            "I hope you get run over by a truck. KYS.",
            "I'm going to slit your throat, you absolute terrorist scum.",
            "Encouraging self-harm is bad, but you honestly should slit your wrists.",
            "Let's go burn down their house. I'll publish the coordinates.",
            "Go drink bleach and die. We will bomb your office."
        ]
    }
    
    comments = []
    now = datetime.now()
    
    # Generate a balanced/realistic distribution of comments
    # e.g., 60% Proper, 15% Spam, 10% Toxic, 10% Abusive, 5% Harmful
    distribution = (
        ["Proper"] * 18 +
        ["Spam"] * 5 +
        ["Toxic"] * 4 +
        ["Abusive"] * 4 +
        ["Harmful"] * 2
    )
    
    random.shuffle(distribution)
    
    for i, category in enumerate(distribution):
        author = random.choice(author_pool)
        if platform == "Reddit":
            author = f"u/{author}"
        elif platform in ["Instagram", "Twitter/X", "TikTok"]:
            author = f"@{author}"
            
        template = random.choice(templates[category])
        text = template.replace("{creator}", creator_name)
        
        # Stagger timestamps (e.g. comments from last 24 hours)
        delta_minutes = random.randint(5, 1440)
        timestamp = (now - timedelta(minutes=delta_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        
        comments.append({
            "author": author,
            "text": text,
            "timestamp": timestamp
        })
        
    # Sort comments by timestamp desc
    comments.sort(key=lambda x: x["timestamp"], reverse=True)
    return comments

# --- MAIN FETCHER WRAPPER ---

def fetch_creator_comments(url, youtube_api_key=None):
    """
    Parses a profile/content URL, detects the platform, and retrieves comments.
    Returns: (creator_name, platform, list of comment dicts, was_simulated_boolean)
    """
    platform = detect_platform(url)
    creator_name = extract_username_or_id(url, platform)
    
    comments = []
    was_simulated = False
    
    try:
        if platform == "Reddit":
            # Live Reddit comments fetching
            title, comments = fetch_reddit_comments(url)
            if comments:
                creator_name = title
            else:
                # Fallback to simulation if network fails or link invalid
                comments = generate_simulated_comments(creator_name, platform)
                was_simulated = True
                
        elif platform == "YouTube":
            video_id = creator_name
            if video_id and youtube_api_key:
                title, comments = fetch_youtube_comments(video_id, youtube_api_key)
                creator_name = title
            else:
                # Use video ID as name and generate simulated comments
                creator_name = f"YouTube Video: {video_id or 'Demo'}"
                comments = generate_simulated_comments(creator_name, platform)
                was_simulated = True
                
        else:
            # Instagram, Twitter/X, TikTok, and Others always run in Simulation Mode
            comments = generate_simulated_comments(creator_name, platform)
            was_simulated = True
            
    except Exception as e:
        print(f"Fetcher error for {url}: {e}")
        # Dynamic fallback
        comments = generate_simulated_comments(creator_name, platform)
        was_simulated = True
        
    return creator_name, platform, comments, was_simulated
