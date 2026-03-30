# How BioPoem Learns from Your Feedback

## 🧠 The Learning Loop

### 1. You Rate Poems (Dev Page)
- Click 👎 on poems you don't like
- Add specific comment: "too long" or "repetitive language"
- Comments go to database: `gallery_feedback.db`

### 2. Analysis Extracts Patterns (Weekly)
```bash
python3 analyze_feedback.py
```

**What it does:**
- Finds ALL poems with dislikes (your negative ratings)
- Extracts keywords from your comments ("long", "repetitive", "unclear")
- Counts how often each word appears
- Groups poems by theme/influence to find patterns

**Example from your feedback:**
- Found 15 poems you disliked
- Extracted keyword "long" appearing **16 times**
- Noticed 9 of 15 were "sustained" theme poems
- Created recommendation: **"KEEP POEMS SHORTER (aim for 10-15 lines max)"**

### 3. Writes Instructions (plant_voice.txt)

The analysis creates a file that the AI reads BEFORE generating each poem:

```
SPECIFIC ISSUES MENTIONED BY COMMUNITY:
- ⚠️ 'TOO LONG' mentioned 16 times - KEEP POEMS SHORTER (aim for 10-15 lines max)
- 'formatting' mentioned 2 times - review poem structure

PATTERNS TO AVOID:
- Reduce 'sustained' theme frequency - appears in 9 low-rated poems
```

### 4. Poetry Engine Reads Instructions

When you generate a new poem:
1. `poetry_engine.py` loads `plant_voice.txt`
2. Adds it to Claude's prompt: "Community says poems are TOO LONG - keep shorter"
3. Claude generates a **shorter poem** responding to feedback

## 📊 How It Knows Which Poems Are Too Long

**The system doesn't analyze poem LENGTH automatically.** Instead:

1. **You tell it directly** in comments: "this poem is too long"
2. It extracts the keyword **"long"** from your comment text
3. It counts: 16 comments mentioned "long"
4. It tells the AI: "Users said 'long' 16 times → make poems shorter"

**It's keyword-based learning:**
- You write: "too long, hard to read" → extracts "long"
- You write: "repetitive language" → extracts "repetitive"
- You write: "love the imagery" → extracts "love", "imagery"

## ✅ Is This the Right Learning Method?

**Yes, for your use case! Here's why:**

### Advantages:
1. ✅ **Human-in-the-loop**: You stay in control of what "good" means
2. ✅ **Transparent**: You can see exactly what feedback influenced the AI
3. ✅ **Qualitative**: Captures nuanced feedback ("not just long, but TOO long")
4. ✅ **Low-tech**: No machine learning models needed, runs on Raspberry Pi
5. ✅ **Exhibition-ready**: Visitors can shape the poetry in real-time

### How It's Different from ML:
- **Not automated**: Won't learn without you rating poems
- **Keyword-based**: Looks for words like "long", not actual line counts
- **Manual analysis**: You run `analyze_feedback.py` when you want updates
- **Prompt engineering**: Changes Claude's instructions, not training a model

### What It Can't Do:
- ❌ Can't automatically detect poem length (you must tell it)
- ❌ Won't learn unless you rate & run analysis
- ❌ Can't understand complex feedback like "too abstract for this mood"
- ❌ Doesn't track which specific lines/phrases are problematic

## 🎯 When to Run Analysis

```bash
# After rating 10-15 poems with varied feedback
python3 analyze_feedback.py
```

**Thresholds:**
- 1+ dislikes on a poem = flagged as "low-rated"
- 2+ mentions of same keyword = pattern detected
- Lower thresholds work because your COMMENTS provide rich context

## 🔄 Weekly Automation (Optional)

```bash
# Add to crontab: run every Sunday at 9am
crontab -e

# Add this line:
0 9 * * 0 cd /home/biopoem && python3 analyze_feedback.py
```

This creates a weekly feedback loop where community input continuously shapes the poetry.

## 🌱 Testing the Learning

1. **Rate 5 poems as "too long"**
2. Run `python3 analyze_feedback.py`
3. Check `plant_voice.txt` - should say "KEEP POEMS SHORTER"
4. Generate new poem (press G in poetry engine)
5. Compare: Is the new poem shorter?

If yes → The learning loop is working! 🎉

## 💡 Alternative: Automatic Length Detection

If you want the AI to **automatically detect** long poems without relying on keywords:

```python
# In analyze_feedback.py - you could add:
def analyze_poem_length(poem_text):
    lines = poem_text.strip().split('\n')
    return len(lines)

# Then flag poems with >20 lines automatically
```

**But this loses nuance:**
- Some long poems are good (epic narratives)
- Some short poems feel "too long" (dense, hard to read)
- Your comments capture *subjective experience* better than line counts

## 🎨 For Exhibitions

This system is **perfect for exhibitions** because:
- Visitors see their feedback instantly affect future poems
- Creates a dialogue between plant, AI, and community
- No complex ML black box - process is transparent
- Works on low-power hardware (Raspberry Pi)

---

**Bottom line:** You're training Claude through **prompt engineering** (changing instructions), not through **model training** (updating weights). Your comments are the training data, and `plant_voice.txt` is the trained model.
