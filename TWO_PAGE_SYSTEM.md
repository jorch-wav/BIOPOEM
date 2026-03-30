# BioPoem Two-Page System

You now have **two gallery pages** that work together:

## 🛠 DEV PAGE (Local - Full Functionality)
**URL:** http://192.168.0.242:8080

**Features:**
- ✅ Rate poems with 👍 👎
- ✅ Leave comments (required)
- ✅ Feedback saved to database
- ✅ Used for testing and exhibitions
- ✅ Shows all 261 poems

**When to use:**
- Personal testing and feedback
- Physical exhibitions where visitors connect to your network
- Collecting community feedback for the poetry engine

**Already running:**
```bash
# Gallery (already running on port 8080)
cd /home/biopoem/docs && python3 -m http.server 8080

# Backend (already running on port 5000)
python3 /home/biopoem/gallery_backend.py
```

---

## 🌐 PUBLIC PAGE (GitHub Pages - Display Only)
**URL:** https://YOUR_USERNAME.github.io/biopoem/ (after deployment)

**Features:**
- ✅ Beautiful gallery display
- ✅ Shows all 261 poems
- ✅ View images and poem details
- ⚠️ **NO ratings/comments** (no backend server)

**When to use:**
- Portfolio showcase
- Sharing with people outside your network
- Public display without community feedback

**Purpose:** Show the world your work without needing to run servers

---

## 📊 Current Status

**Gallery:**
- 261 poems loaded (Nov 2025 - Mar 2026)
- All images found and linked
- Organized by theme (Dry/Low/Comfortable/Wet/Bouncing Back)
- Dark mode renders

**Backend:**
- Database: `/home/biopoem/gallery_feedback.db`
- 0 ratings (cleared for fresh testing)
- API running on http://localhost:5000

---

## 🚀 Deploy to GitHub Pages (When Ready)

```bash
cd /home/biopoem

# 1. Commit your work
git add docs/
git commit -m "Add BioPoem gallery with 261 poems"

# 2. Create GitHub repo (go to https://github.com/new)
#    Name: biopoem
#    Make it public

# 3. Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/biopoem.git
git branch -M main
git push -u origin main

# 4. Enable GitHub Pages
#    Go to: Settings → Pages → Source: Deploy from /docs folder
#    Wait 1-2 minutes, then visit:
#    https://YOUR_USERNAME.github.io/biopoem/
```

---

## 🎯 Testing Workflow

### Phase 1: Rate poems on DEV page
1. Open http://192.168.0.242:8080
2. Rate 10-15 poems with specific feedback:
   - "Too long, hard to read" (3-4 poems)
   - "Repetitive language" (2-3 poems)
   - "Love the imagery" (3-4 poems)
3. Check "Rated" filter tab to see your ratings

### Phase 2: Analyze feedback
```bash
cd /home/biopoem
python3 analyze_feedback.py
```
This creates `feedback_analysis.json` with your feedback patterns

### Phase 3: Generate poem with feedback
```bash
# Press 'G' in your poetry engine
# It will read feedback_analysis.json and adjust behavior
```

### Phase 4: Deploy to GitHub (optional)
After local testing is complete, push to GitHub Pages for public display

---

## 🔧 If You Want Public Ratings Later

To make ratings work on GitHub Pages, you need a cloud backend:

**Option A: Railway (Recommended)**
- Free tier: 500 hours/month
- Deploy `gallery_backend.py` in 5 minutes
- Update `docs/app.js` with Railway URL

**Option B: Render**
- Free tier with limitations
- Good for small apps

**Option C: Supabase/Firebase**
- Requires rewriting backend
- Great free tier

---

## 📁 Important Files

- `docs/poems.json` - All 261 poems with images
- `docs/app.js` - Gallery frontend (works both locally and GitHub Pages)
- `gallery_backend.py` - Backend API (local only)
- `gallery_feedback.db` - Rating/comment database
- `analyze_feedback.py` - Weekly feedback analysis
- `regenerate_full_gallery.py` - Updates poems.json from instagram_posts

---

## 🎨 Poems by Month

- **2026-03:** 64 poems
- **2026-02:** 94 poems
- **2025-12:** 83 poems
- **2025-11:** 10 poems
- **2025-01:** 10 poems

**Total: 261 poems** 🎉
