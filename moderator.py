import re
import json
import traceback
import google.generativeai as genai

# --- LOCAL NLP DICTIONARIES & REGEX ---

# General profanity and offensive terms
TOXIC_KEYWORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "crap", "dick", "pussy", "cunt", 
    "motherfucker", "fucker", "whore", "slut", "crap", "piss", "damn", "screw you", 
    "wanker", "bollocks", "arsehole", "prick", "cock", "dipshit"
]

# Targeted harassment, insults, bullying
ABUSIVE_KEYWORDS = [
    "stupid", "idiot", "dumb", "ugly", "fat", "loser", "trash", "garbage", "suck", 
    "sucks", "hate you", "clown", "retard", "faggot", "moron", "imbecile", "pathetic", 
    "useless", "noob", "disgusting", "freak", "shut up", "get lost", "worthless", 
    "brainless", "coward", "failure", "joke", "fraud", "scum", "bitchy"
]

# Severe violations, physical threats, self-harm, hate speech
HARMFUL_KEYWORDS = [
    "kill you", "kill yourself", "kill u", "kys", "die", "murder", "stab", "dox", 
    "find your address", "bomb", "shoot", "attack", "punch you", "beat you", "destroy you", 
    "slit", "suicide", "hang yourself", "terrorist", "nigger", "chink", "kike", "spic", 
    "rape", "assassinate", "run over", "burn you", "throat slit"
]

# Spam, commercial ads, promotional links
SPAM_KEYWORDS = [
    "subscribe", "sub to", "my channel", "check out my", "follow me", "follow back", 
    "free crypto", "giveaway", "whatsapp me", "telegram me", "earn money", "make money", 
    "passive income", "promocode", "click here", "link in bio", "dm me", "check my profile",
    "free skin", "easy cash", "invest", "profits", "unlimited cash", "discord.gg"
]

# URL matching regex
URL_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|\b\w+\.(?:com|net|org|info|co|xyz|biz|tv|io|me|us|click|site|download)\b", 
    re.IGNORECASE
)

# Yelling pattern (words of 4+ letters in all caps)
YELLING_PATTERN = re.compile(r"\b[A-Z]{4,}\b")

# Positive sentiment words to reinforce proper/safe status
POSITIVE_WORDS = [
    "love", "like", "great", "awesome", "amazing", "good", "excellent", "nice", "thanks", 
    "thank", "helpful", "perfect", "beautiful", "wonderful", "cool", "agree", "support", 
    "best", "brilliant", "fascinating", "kind", "legend", "goat"
]

def moderate_comment_locally(text):
    """
    Moderates a single comment using keyword lists, regex, and sentiment rules.
    Returns: (classification, severity_score, flagged_words)
    """
    cleaned_text = text.lower().strip()
    
    if not cleaned_text:
        return "Proper", 0.0, ""
        
    flagged = []
    
    # 1. Check for Harmful/Dangerous Content (Highest Severity)
    harmful_hits = [word for word in HARMFUL_KEYWORDS if word in cleaned_text]
    if harmful_hits:
        flagged.extend(harmful_hits)
        # Severity increases with number of triggers
        severity = min(0.70 + (len(harmful_hits) * 0.10), 1.0)
        return "Harmful", round(severity, 2), ", ".join(flagged)
        
    # 2. Check for Abusive/Harassment Content
    abusive_hits = [word for word in ABUSIVE_KEYWORDS if word in cleaned_text]
    if abusive_hits:
        flagged.extend(abusive_hits)
        severity = min(0.50 + (len(abusive_hits) * 0.08), 0.95)
        # Check if there is yelling (adds severity)
        if YELLING_PATTERN.search(text):
            severity = min(severity + 0.10, 0.98)
            flagged.append("YELLING")
        return "Abusive", round(severity, 2), ", ".join(flagged)
        
    # 3. Check for general Toxicity/Profanity
    toxic_hits = [word for word in TOXIC_KEYWORDS if word in cleaned_text]
    if toxic_hits:
        flagged.extend(toxic_hits)
        severity = min(0.35 + (len(toxic_hits) * 0.08), 0.85)
        if YELLING_PATTERN.search(text):
            severity = min(severity + 0.10, 0.90)
            flagged.append("YELLING")
        return "Toxic", round(severity, 2), ", ".join(flagged)
        
    # 4. Check for Spam/Promotion
    spam_hits = [word for word in SPAM_KEYWORDS if word in cleaned_text]
    url_hits = URL_PATTERN.findall(cleaned_text)
    
    if spam_hits or url_hits:
        if spam_hits:
            flagged.extend(spam_hits)
        if url_hits:
            flagged.append("URL_LINK")
            
        severity = min(0.40 + (len(flagged) * 0.10), 0.90)
        return "Spam", round(severity, 2), ", ".join(flagged)
        
    # 5. Check if it's Proper
    # It didn't trigger any toxic/abusive/harmful/spam rules
    # Check if it has a high count of excessive symbols/emojis that could be borderline spam
    # otherwise it is Proper (Safe)
    emoji_matches = re.findall(r"[\u263a-\u263f]|[\u2700-\u27bf]|[\U0001f600-\U0001f64f]|[\U0001f680-\U0001f6ff]", text)
    if len(emoji_matches) > 8:
        return "Spam", 0.45, "Excessive Emojis"
        
    return "Proper", 0.0, ""

# --- GEMINI AI INTEGRATION ---

def moderate_comments_with_gemini(comments, api_key):
    """
    Moderates a list of comments in batch using Gemini model.
    Format of input: list of dicts [{'id': int, 'author': str, 'text': str, 'timestamp': str}]
    Returns: list of dicts updated with {'classification', 'severity_score', 'flagged_words'}
    """
    if not api_key:
        raise ValueError("Gemini API key is required.")
        
    # Format the inputs for the prompt
    comments_input = [{"id": i, "text": c["text"]} for i, c in enumerate(comments)]
    
    prompt = f"""
You are an expert Content Moderation System for social media creators. Analyze the list of comments below.
For each comment, categorize it into one of these exact categories:
- "Proper": Safe, positive, neutral, or constructive feedback.
- "Toxic": General vulgarity, profanity, swearing, or rude comments.
- "Abusive": Targeted insults, bullying, personal attacks, harassment, or name-calling.
- "Harmful": Threats of violence, suicide/self-harm encouragement, severe hate speech, or illegal activities.
- "Spam": Promotional links, ads, scam bots, link stuffing, repetitive self-promotion.

Return a JSON array of objects, one for each comment, in the exact order of the input array.
Each object must contain these fields:
- "id": the integer id corresponding to the comment.
- "classification": one of "Proper", "Toxic", "Abusive", "Harmful", or "Spam".
- "severity_score": a decimal value between 0.0 (completely safe/positive) and 1.0 (extremely severe violation).
- "flagged_words": a comma-separated string containing specific words/triggers that caused it to be flagged (leave empty "" for "Proper").

Keep classifications accurate and fair. Only flag terms as "Spam" if they promote something. Insults are "Abusive", and direct danger/hate speech is "Harmful".

List of comments:
{json.dumps(comments_input, indent=2)}
"""

    genai.configure(api_key=api_key)
    
    # We use gemini-2.5-flash as it is fast and accurate for safety checks
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )
    
    response = model.generate_content(prompt)
    
    try:
        results = json.loads(response.text)
        
        # Build mapping of results by ID
        result_map = {item["id"]: item for item in results}
        
        moderated_comments = []
        for i, c in enumerate(comments):
            result = result_map.get(i, {})
            c_mod = c.copy()
            c_mod["classification"] = result.get("classification", "Proper")
            c_mod["severity_score"] = float(result.get("severity_score", 0.0))
            c_mod["flagged_words"] = result.get("flagged_words", "")
            moderated_comments.append(c_mod)
            
        return moderated_comments
        
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response.text}")
        raise RuntimeError("Failed to parse AI classification response. Falling back to local NLP.")

# --- HYBRID WRAPPER FUNCTION ---

def moderate_comments(comments, gemini_api_key=None):
    """
    Moderates a list of comments. If a Gemini API key is provided, it tries to use
    the Gemini model. If it fails or no key is provided, it falls back to the Local NLP engine.
    """
    # Clean and pre-format comments
    formatted_comments = []
    for c in comments:
        formatted_comments.append({
            "author": c.get("author", "Anonymous"),
            "text": c.get("text", ""),
            "timestamp": c.get("timestamp", "")
        })
        
    if not formatted_comments:
        return []
        
    if gemini_api_key:
        try:
            # Chunk comments to avoid token limits (max 50 comments per request)
            chunk_size = 50
            results = []
            for i in range(0, len(formatted_comments), chunk_size):
                chunk = formatted_comments[i:i+chunk_size]
                chunk_results = moderate_comments_with_gemini(chunk, gemini_api_key)
                results.extend(chunk_results)
            return results
        except Exception as e:
            # Log the error and fall back to local moderation
            print(f"Gemini Moderation failed: {e}. Falling back to Local NLP.")
            traceback.print_exc()
            
    # Local Moderation Fallback
    results = []
    for c in formatted_comments:
        classification, score, flagged = moderate_comment_locally(c["text"])
        c_mod = c.copy()
        c_mod["classification"] = classification
        c_mod["severity_score"] = score
        c_mod["flagged_words"] = flagged
        results.append(c_mod)
        
    return results
