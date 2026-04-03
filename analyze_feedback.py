#!/usr/bin/env python3
"""
BioPoem Feedback Analysis Script
Analyzes community feedback to identify repetitive patterns and generate recommendations
Run weekly (automated via cron) to inform the poetry engine
"""

import sqlite3
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

DB_PATH = 'gallery_feedback.db'
POEMS_JSON = 'docs/poems.json'
OUTPUT_FILE = 'feedback_analysis.json'
VOICE_PROFILE = 'plant_voice.txt'

def load_poems():
    """Load poem metadata from gallery"""
    if not os.path.exists(POEMS_JSON):
        print(f"[ERROR] {POEMS_JSON} not found")
        return []
    
    with open(POEMS_JSON, 'r') as f:
        poems = json.load(f)
    
    return poems

def get_feedback_data():
    """Load feedback from database with comments"""
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database {DB_PATH} not found. Run gallery_backend.py first.")
        return [], []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get all poems with ratings
    query = '''
        SELECT 
            r.poem_id,
            r.likes,
            r.dislikes,
            COUNT(c.id) as comment_count
        FROM ratings r
        LEFT JOIN comments c ON r.poem_id = c.poem_id
        GROUP BY r.poem_id
    '''
    
    results = conn.execute(query).fetchall()
    feedback = [dict(row) for row in results]
    
    # Get all comments with poem context
    comment_query = '''
        SELECT 
            c.poem_id,
            c.text,
            c.user_id,
            c.timestamp,
            ur.rating_type
        FROM comments c
        LEFT JOIN user_ratings ur ON c.user_id = ur.user_id AND c.poem_id = ur.poem_id
        ORDER BY c.timestamp DESC
    '''
    
    comment_results = conn.execute(comment_query).fetchall()
    comments = [dict(row) for row in comment_results]
    
    conn.close()
    return feedback, comments

def extract_keywords(text):
    """Extract meaningful words from comment text"""
    # Convert to lowercase and split into words
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    
    # Common stopwords to ignore
    stopwords = {
        'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they',
        'about', 'would', 'could', 'should', 'their', 'there', 'these',
        'those', 'what', 'when', 'where', 'which', 'while', 'really',
        'just', 'very', 'more', 'some', 'than', 'into', 'also', 'much'
    }
    
    # Filter out stopwords
    keywords = [w for w in words if w not in stopwords]
    
    return keywords

def analyze_comment_sentiment(comments, rating_type):
    """Analyze comments for a specific rating type (like/dislike)"""
    filtered_comments = [c for c in comments if c.get('rating_type') == rating_type]
    
    if not filtered_comments:
        return Counter(), []
    
    # Extract keywords from all comments
    all_keywords = []
    for comment in filtered_comments:
        keywords = extract_keywords(comment['text'])
        all_keywords.extend(keywords)
    
    keyword_freq = Counter(all_keywords)
    
    return keyword_freq, filtered_comments

def analyze_feedback():
    """Main analysis function"""
    print("=" * 70)
    print("BIOPOEM FEEDBACK ANALYSIS")
    print("=" * 70)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Load data
    poems = load_poems()
    feedback, all_comments = get_feedback_data()
    
    if not poems:
        print("[ERROR] No poems found. Exiting.")
        return None
    
    if not feedback:
        print("[WARNING] No feedback data found. Gallery may not have received ratings yet.")
        return None
    
    print(f"Loaded {len(poems)} poems")
    print(f"Found feedback for {len(feedback)} poems")
    print(f"Total comments: {len(all_comments)}\n")
    
    # Create lookup dict for poem metadata
    poem_lookup = {p['id']: p for p in poems}
    
    # Merge feedback with poem metadata
    analyzed_poems = []
    for fb in feedback:
        poem_id = fb['poem_id']
        if poem_id not in poem_lookup:
            continue
        
        poem = poem_lookup[poem_id]
        analyzed_poems.append({
            'id': poem_id,
            'title': poem.get('title', 'Unknown'),
            'date': poem.get('date', ''),
            'theme': poem.get('theme', 'unknown'),
            'influence': poem.get('influence', 'unknown'),
            'likes': fb['likes'],
            'dislikes': fb['dislikes'],
            'comments': fb['comment_count'],
            'score': fb['likes'] - fb['dislikes']  # Net rating
        })
    
    # Sort by score (lowest first = most disliked)
    analyzed_poems.sort(key=lambda x: x['score'])
    
    # Identify low-rated poems (more dislikes than likes, minimum 1 dislike)
    # Lower threshold since comment text provides rich context
    low_rated = [p for p in analyzed_poems if p['dislikes'] > p['likes'] and p['dislikes'] >= 1]
    
    print(f"Low-rated poems (negative score, 1+ dislikes): {len(low_rated)}")
    if low_rated:
        print("\nLOW-RATED POEMS:")
        for poem in low_rated[:10]:  # Show top 10
            print(f"  • {poem['title'][:50]:50} | Theme: {poem['theme']:12} | Score: {poem['score']:+3}")
    
    # Analyze patterns in low-rated poems
    theme_counter = Counter()
    influence_counter = Counter()
    
    for poem in low_rated:
        theme_counter[poem['theme']] += 1
        influence_counter[poem['influence']] += 1
    
    # Analyze comment text for insights
    dislike_keywords, dislike_comments = analyze_comment_sentiment(all_comments, 'dislike')
    like_keywords, like_comments = analyze_comment_sentiment(all_comments, 'like')
    
    print(f"\n📝 Comment Analysis:")
    print(f"  Dislike comments: {len(dislike_comments)}")
    print(f"  Like comments: {len(like_comments)}")
    
    if dislike_keywords:
        print(f"\n  Common words in negative feedback:")
        for word, count in dislike_keywords.most_common(10):
            print(f"    • '{word}' ({count}x)")
    
    if like_keywords:
        print(f"\n  Common words in positive feedback:")
        for word, count in like_keywords.most_common(10):
            print(f"    • '{word}' ({count}x)")
    
    # Build recommendations with comment insights
    recommendations = []
    
    # Theme recommendations with comment evidence
    if theme_counter:
        top_theme, count = theme_counter.most_common(1)[0]
        if count >= 2:  # Lower threshold since we have comment text now
            # Find common words in comments about this theme's poems
            theme_poem_ids = [p['id'] for p in low_rated if p['theme'] == top_theme]
            theme_comments = [c for c in dislike_comments if c['poem_id'] in theme_poem_ids]
            theme_keywords = []
            for c in theme_comments:
                theme_keywords.extend(extract_keywords(c['text']))
            theme_keyword_freq = Counter(theme_keywords)
            
            # Get sample quotes
            sample_quotes = [c['text'][:80] + '...' if len(c['text']) > 80 else c['text'] 
                           for c in theme_comments[:3]]
            
            action = f"Reduce '{top_theme}' theme frequency - appears in {count} low-rated poems"
            if theme_keyword_freq:
                top_words = [w for w, _ in theme_keyword_freq.most_common(3)]
                action += f". Users mentioned: {', '.join(top_words)}"
            
            recommendations.append({
                'type': 'theme_reduction',
                'target': top_theme,
                'reason': f"Theme '{top_theme}' appears in {count} low-rated poems",
                'action': action,
                'user_feedback_samples': sample_quotes
            })
    
    # Influence recommendations with comment evidence
    if influence_counter:
        top_influence, count = influence_counter.most_common(1)[0]
        if count >= 2:
            influence_poem_ids = [p['id'] for p in low_rated if p['influence'] == top_influence]
            influence_comments = [c for c in dislike_comments if c['poem_id'] in influence_poem_ids]
            
            sample_quotes = [c['text'][:80] + '...' if len(c['text']) > 80 else c['text']
                           for c in influence_comments[:3]]
            
            recommendations.append({
                'type': 'influence_rotation',
                'target': top_influence,
                'reason': f"Influence '{top_influence}' appears in {count} low-rated poems",
                'action': f"Rotate away from '{top_influence}' influence temporarily",
                'user_feedback_samples': sample_quotes
            })
    
    # Identify successful patterns (high-rated poems)
    high_rated = [p for p in analyzed_poems if p['score'] >= 3][-10:]  # Top 10
    
    success_themes = Counter()
    success_influences = Counter()
    
    for poem in high_rated:
        success_themes[poem['theme']] += 1
        success_influences[poem['influence']] += 1
    
    # Build results
    results = {
        'analysis_date': datetime.now().isoformat(),
        'poems_analyzed': len(analyzed_poems),
        'total_ratings': sum(p['likes'] + p['dislikes'] for p in analyzed_poems),
        'total_comments': len(all_comments),
        'low_rated_count': len(low_rated),
        'high_rated_count': len(high_rated),
        'low_rated_poems': low_rated,
        'high_rated_poems': high_rated,
        'overused_themes': [
            {'theme': theme, 'disliked_count': count}
            for theme, count in theme_counter.most_common(3)
        ],
        'overused_influences': [
            {'influence': inf, 'disliked_count': count}
            for inf, count in influence_counter.most_common(3)
        ],
        'successful_themes': [
            {'theme': theme, 'liked_count': count}
            for theme, count in success_themes.most_common(3)
        ],
        'successful_influences': [
            {'influence': inf, 'liked_count': count}
            for inf, count in success_influences.most_common(3)
        ],
        'recommendations': recommendations,
        'negative_feedback_keywords': [
            {'word': word, 'count': count}
            for word, count in dislike_keywords.most_common(15)
        ],
        'positive_feedback_keywords': [
            {'word': word, 'count': count}
            for word, count in like_keywords.most_common(15)
        ]
    }
    
    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Analysis saved to {OUTPUT_FILE}")
    
    # Print recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS FOR POETRY ENGINE")
    print("=" * 70)
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['action']}")
            print(f"   Reason: {rec['reason']}")
            if 'user_feedback_samples' in rec and rec['user_feedback_samples']:
                print(f"   User feedback:")
                for quote in rec['user_feedback_samples'][:2]:  # Show max 2 quotes
                    print(f"     → \"{quote}\"")
    else:
        print("\n✅ No major repetition patterns detected!")
        print("   Community feedback is positive - keep current approach.")
    
    # Print keyword insights
    if dislike_keywords:
        print("\n" + "=" * 70)
        print("COMMON WORDS IN NEGATIVE FEEDBACK")
        print("=" * 70)
        top_negative = dislike_keywords.most_common(8)
        negative_words = ', '.join([f'"{w}"' for w, _ in top_negative])
        print(f"Users often mention: {negative_words}")
    
    if like_keywords:
        print("\n" + "=" * 70)
        print("COMMON WORDS IN POSITIVE FEEDBACK")
        print("=" * 70)
        top_positive = like_keywords.most_common(8)
        positive_words = ', '.join([f'"{w}"' for w, _ in top_positive])
        print(f"Users appreciate: {positive_words}")
    
    # Print successful patterns
    if high_rated:
        print("\n" + "=" * 70)
        print("SUCCESSFUL PATTERNS (Continue These)")
        print("=" * 70)
        if success_themes:
            print("\nThemes working well:")
            for theme, count in success_themes.most_common(3):
                print(f"  • {theme}: {count} high-rated poems")
        if success_influences:
            print("\nInfluences working well:")
            for inf, count in success_influences.most_common(3):
                print(f"  • {inf}: {count} high-rated poems")
    
    print("\n" + "=" * 70)
    
    return results

def generate_agent_handoff_report(results):
    """
    Generate AI-agent-ready handoff report with actionable recommendations
    Saved to /memories/session/ for easy access by Copilot agents
    """
    if not results:
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = f'/home/biopoem/.vscode-server/data/User/globalStorage/github.copilot-chat/memories/session/feedback-handoff-{timestamp}.md'
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # Build report content
    report = f"""# BioPoem Feedback Analysis - {datetime.now().strftime('%B %d, %Y')}
*AI Agent Implementation Guide*

## Executive Summary
- **{results['poems_analyzed']} poems** analyzed with **{results['total_ratings']} total ratings**
- **{results['low_rated_count']} poems** received negative feedback ({results['total_comments']} total comments)
- **{len(results['recommendations'])} critical issues** identified requiring code changes

---

"""
    
    # Priority issues
    priority_num = 1
    
    # Issue 1: Length complaints (if present)
    length_keywords = [kw for kw in results.get('negative_feedback_keywords', []) if kw['word'] == 'long']
    if length_keywords and length_keywords[0]['count'] >= 2:
        count = length_keywords[0]['count']
        report += f"""## ⚠️ Priority {priority_num}: Poems Too Long

**Evidence:**
- "Too long" mentioned **{count} times** in negative comments
- This is the #1 complaint from users

**Sample Comments:**
"""
        # Get all recommendations that have user feedback samples
        all_samples = []
        for rec in results.get('recommendations', []):
            if 'user_feedback_samples' in rec:
                all_samples.extend(rec['user_feedback_samples'])
        
        # Show first 3 unique samples
        for i, sample in enumerate(list(set(all_samples))[:3], 1):
            truncated = sample[:80] + '...' if len(sample) > 80 else sample
            report += f'{i}. "{truncated}"\n'
        
        report += """
**Code Location:**
- File: `poetry_engine.py`
- Function: `generate_poem()` (around line 3467-3500)
- Current: No hard line limit enforcement

**Recommended Fix:**
Add a line count validator that rejects poems exceeding the limit:

```python
def validate_poem_length(poem_text, max_lines=15):
    \"\"\"
    Validate poem doesn't exceed max line count
    Returns: (is_valid, message, line_count)
    \"\"\"
    lines = [l.strip() for l in poem_text.split('\\n') if l.strip()]
    line_count = len(lines)
    
    if line_count > max_lines:
        return False, f"Poem has {line_count} lines (max: {max_lines})", line_count
    
    return True, "OK", line_count

# In generate_poem(), after getting response from API:
is_valid, msg, line_count = validate_poem_length(poem_text)
if not is_valid:
    print(f"[VALIDATION] {msg} - regenerating...")
    # Retry with stricter prompt or reject
```

**Success Criteria:**
- Next 10 poems: **0 poems exceed 15 lines** (title + body)
- Average length drops to **12-14 lines**
- Zero "too long" complaints in next feedback cycle

---

"""
        priority_num += 1
    
    # Issue 2: Repetitive themes
    if results.get('overused_themes') and results['overused_themes'][0]['disliked_count'] >= 3:
        theme_data = results['overused_themes'][0]
        theme = theme_data['theme']
        count = theme_data['disliked_count']
        
        report += f"""## ⚠️ Priority {priority_num}: Theme "{theme}" Overused

**Evidence:**
- Theme "{theme}" appears in **{count} low-rated poems**
- Represents {int(count / results['low_rated_count'] * 100)}% of negative feedback

**Sample Comments:**
"""
        # Find comments about this theme's poems
        theme_poems = [p for p in results.get('low_rated_poems', []) if p.get('theme') == theme]
        for i, poem in enumerate(theme_poems[:3], 1):
            report += f'{i}. "{poem.get("title", "Untitled")}" - Score: {poem.get("score", 0)}\n'
        
        report += f"""
**Code Location:**
- File: `poetry_engine.py`
- Function: `select_theme()` (around line 2000-2019)
- Current: Theme selected purely by sensor data scores, no diversity tracking

**Recommended Fix:**
Add theme diversity governor to prevent overuse:

```python
class ThemeDiversityGovernor:
    \"\"\"Tracks theme usage and applies diversity penalties\"\"\"
    
    def __init__(self, history_window=30):
        self.history_window = history_window
    
    def get_theme_frequency(self, theme, recent_poems):
        \"\"\"Calculate how often theme appears in recent poems\"\"\"
        theme_count = sum(1 for p in recent_poems[-self.history_window:] 
                         if p.get('theme') == theme)
        return theme_count / min(len(recent_poems), self.history_window)
    
    def apply_diversity_penalty(self, theme_scores, recent_poems):
        \"\"\"Penalize overused themes\"\"\"
        for theme in theme_scores:
            freq = self.get_theme_frequency(theme, recent_poems)
            
            # Penalize if theme exceeds 30% of recent poems
            if freq > 0.30:
                penalty = freq - 0.30  # More overused = bigger penalty
                theme_scores[theme] *= (1 - penalty)
        
        return theme_scores
```

**Integration Point:**
In `select_theme()`, before final selection:
```python
# Apply diversity penalty
governor = ThemeDiversityGovernor()
theme_scores = governor.apply_diversity_penalty(theme_scores, recent_poems)
```

**Success Criteria:**
- "{theme}" theme appears in **<30%** of next 30 poems
- More balanced theme distribution across all 7 themes
- Reduction in "{theme}" complaints

---

"""
        priority_num += 1
    
    # Issue 3: Repetitive phrases
    repetition_keywords = [kw for kw in results.get('negative_feedback_keywords', []) 
                          if kw['word'] in ['repeating', 'repetitive', 'same', 'roots']]
    if repetition_keywords:
        report += f"""## ⚠️ Priority {priority_num}: Repetitive Phrases

**Evidence:**
- Users report repeated phrases: "my roots", specific metaphors
- Complaints about same language patterns appearing too often

**Sample Comments:**
"""
        # Get comments mentioning repetition
        all_comments = []
        for poem in results.get('low_rated_poems', []):
            if 'user_feedback_samples' in poem:
                all_comments.extend(poem.get('user_feedback_samples', []))
        
        # Find repetition-related comments
        rep_comments = [c for c in all_comments if any(word in c.lower() for word in ['repeat', 'same', 'roots', 'drenched', 'soaked'])]
        for i, comment in enumerate(rep_comments[:3], 1):
            report += f'{i}. "{comment}"\n'
        
        report += """
**Code Location:**
- File: `VOICE_CONSTRAINTS.py`
- Variable: `COOLDOWN_PHRASES` (around line 25-38)
- Missing: "I'm drenched", "I'm soaked", "I'm saturated"

**Recommended Fix:**
Add missing phrases to cooldown list:

```python
# In VOICE_CONSTRAINTS.py, add to COOLDOWN_PHRASES:
COOLDOWN_PHRASES = [
    "I am here",
    "I hold the",
    "I keep the",
    "this is what",
    "looks like",
    "river remembers its bed",
    "light as a hand",
    "light as visitor",
    "between fullness and",
    "my roots drinking",
    "evening settles",
    # NEW - Add these based on feedback:
    "I'm drenched",
    "I'm soaked", 
    "I'm saturated",
    "my roots hold",
    "my roots know",
]
```

**Also Needed:**
Rebuild `repetition_prevention.py` module (currently deleted):
- Track last 30 poems' phrases
- Flag poems using cooldown phrases
- Provide alternative suggestions

**Success Criteria:**
- Zero uses of flagged phrases in next 10 poems
- Greater variety in metaphors and language
- No "repetitive" complaints in next feedback cycle

---

"""
        priority_num += 1
    
    # Discussion points
    report += """## Discussion Points

Before implementing these changes, consider:

1. **Strictness Level:** Should constraints be **hard limits** (reject non-compliant poems) or **soft penalties** (discourage but allow occasionally)?
   - Recommendation: Hard limits for length, soft penalties for theme diversity
   
2. **Regeneration Strategy:** If a poem fails validation, should we:
   - Regenerate with stricter prompt (recommended)
   - Skip that generation cycle
   - Override with warning

3. **Monitoring:** After implementing, how should we track improvement?
   - Recommendation: Generate 10 test poems, collect feedback, re-run analysis

---

## Files Requiring Changes

### Modify Existing:
"""
    
    # List files to modify
    files_to_modify = []
    if length_keywords:
        files_to_modify.append("- **poetry_engine.py** - Add `validate_poem_length()` function, integrate after line ~3485")
    if results.get('overused_themes'):
        files_to_modify.append("- **poetry_engine.py** - Add `ThemeDiversityGovernor` class, integrate in `select_theme()` around line 2000")
    if repetition_keywords:
        files_to_modify.append("- **VOICE_CONSTRAINTS.py** - Add 5 missing cooldown phrases to line ~25")
    
    report += '\n'.join(files_to_modify)
    
    report += """

### Create New:
- **repetition_prevention.py** - RepetitionGovernor class for phrase tracking (restore from trash or rebuild)
- **test_constraints.py** - Test suite to verify fixes work

---

## Implementation Status Tracking

```json
{{
  "analysis_date": "{analysis_date}",
  "acted_on_date": null,
  "implementation_notes": "",
  "status": "pending"
}}
```

Update `acted_on_date` in feedback_analysis.json after implementing changes.

---

## Ready-to-Use Agent Prompt

Copy and paste this to start your agent session:

```
I've analyzed feedback on my BioPoem poetry generation system. The analysis 
identified {issue_count} priority issues that need code changes.

Please review the full report at:
{report_path}

Let's start with Priority 1 ({first_priority}). Can you help me implement 
the recommended fix? I'd like to discuss the approach first before making changes.
```

---

Generated: {timestamp}
Report location: {report_path}
""".format(
        analysis_date=results['analysis_date'],
        issue_count=priority_num - 1,
        first_priority="Poems Too Long" if length_keywords else "Theme Overuse",
        report_path=report_path,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    # Save report
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n✅ Agent handoff report generated: {report_path}")
    print(f"   {priority_num - 1} priority issues documented with code examples")
    
    return report_path

def update_plant_voice_profile(results):
    """
    Update plant_voice.txt with analysis insights
    This file is loaded into every prompt to guide poem generation
    """
    if not results:
        return
    
    voice_content = f"""PLANT VOICE PROFILE (Updated: {datetime.now().strftime('%Y-%m-%d')})

Based on community feedback analysis, this plant's voice is evolving:

COMMUNITY FEEDBACK SUMMARY:
- Analyzed {results['poems_analyzed']} poems with {results['total_ratings']} total ratings
- {results['low_rated_count']} poems received negative feedback
- {results['high_rated_count']} poems received strong positive feedback

"""
    
    # Add recommendations
    if results['recommendations']:
        voice_content += "PATTERNS TO AVOID (Based on Recent Feedback):\n"
        for rec in results['recommendations']:
            voice_content += f"- {rec['action']}: {rec['reason']}\n"
        voice_content += "\n"
    
    # Add successful patterns
    if results['successful_themes']:
        voice_content += "THEMES RESONATING WITH COMMUNITY:\n"
        for item in results['successful_themes']:
            voice_content += f"- {item['theme']}: {item['liked_count']} high-rated poems\n"
        voice_content += "\n"
    
    if results['successful_influences']:
        voice_content += "INFLUENCES WORKING WELL:\n"
        for item in results['successful_influences']:
            voice_content += f"- {item['influence']}: {item['liked_count']} high-rated poems\n"
        voice_content += "\n"
    
    # Add keyword insights from negative feedback
    if results.get('negative_feedback_keywords'):
        voice_content += "SPECIFIC ISSUES MENTIONED BY COMMUNITY:\n"
        top_negative = [kw for kw in results['negative_feedback_keywords'][:5] if kw['count'] >= 2]
        if top_negative:
            for kw in top_negative:
                if kw['word'] == 'long':
                    voice_content += f"- ⚠️ 'TOO LONG' mentioned {kw['count']} times - KEEP POEMS SHORTER (aim for 10-15 lines max)\n"
                elif kw['word'] in ['repetitive', 'repetition', 'same']:
                    voice_content += f"- ⚠️ 'REPETITIVE' mentioned {kw['count']} times - vary language and imagery more\n"
                elif kw['word'] in ['formatting', 'line', 'breaks']:
                    voice_content += f"- '{kw['word']}' mentioned {kw['count']} times - review poem structure\n"
                else:
                    voice_content += f"- '{kw['word']}' mentioned {kw['count']} times\n"
            voice_content += "\n"
    
    voice_content += f"""
GUIDANCE:
- Prefer direct, visceral language over abstract metaphors
- Use successful themes and influences as guidance
- Avoid patterns identified in negative feedback
- Aim for variety and fresh approaches

Last analysis: {results['analysis_date']}
"""
    
    with open(VOICE_PROFILE, 'w') as f:
        f.write(voice_content)
    
    print(f"\n✅ Plant voice profile updated: {VOICE_PROFILE}")
    print("   This file will be loaded into future poem prompts.")

if __name__ == '__main__':
    results = analyze_feedback()
    
    if results:
        # Update plant voice profile for next poem generation
        update_plant_voice_profile(results)
        
        # Generate agent handoff report
        report_path = generate_agent_handoff_report(results)
        
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Review feedback_analysis.json for detailed insights")
        print("2. Review agent handoff report: " + (report_path if report_path else "(not generated)"))
        print("3. Copy report and paste to AI agent to implement fixes")
        print("4. plant_voice.txt will be automatically loaded in next poem generation")
        print("5. Schedule this script to run weekly via cron:")
        print("   0 9 * * 0 cd /home/biopoem && python3 analyze_feedback.py")
        print("=" * 70 + "\n")
