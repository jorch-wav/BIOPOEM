# BioPoem Gallery - GitHub Pages Setup

This folder contains the static website for the BioPoem gallery, designed to be hosted on GitHub Pages.

## 🚀 Quick Setup

### 1. Generate Gallery Data

Run the Python script to create `poems.json` from your poem history:

```bash
cd /home/biopoem
python3 generate_gallery_data.py
```

This will:
- Read from `poem_history.json`
- Find corresponding images in `instagram_posts/`
- Generate `docs/poems.json` with all metadata

### 2. Copy Images to Web Directory

Create a symbolic link or copy images:

```bash
# Option A: Symbolic link (faster, but requires careful deployment)
ln -s ../instagram_posts docs/images

# Option B: Copy images (safer for GitHub Pages)
cp -r instagram_posts docs/images
```

### 3. Test Locally

Use Python's built-in server:

```bash
cd docs
python3 -m http.server 8000
```

Then visit: `http://localhost:8000`

### 4. Deploy to GitHub Pages

#### First-time setup:

1. Create a new GitHub repository or use existing one
2. Push this code:

```bash
cd /home/biopoem
git init
git add docs/
git commit -m "Add BioPoem gallery"
git remote add origin https://github.com/YOUR_USERNAME/biopoem.git
git push -u origin main
```

3. Enable GitHub Pages:
   - Go to repository Settings → Pages
   - Source: Deploy from branch
   - Branch: `main` → `/docs` folder
   - Save

#### Updating the gallery:

```bash
# Regenerate data
python3 generate_gallery_data.py

# Commit and push
git add docs/
git commit -m "Update gallery with new poems"
git push
```

GitHub Pages will automatically rebuild (takes 1-2 minutes).

## 📁 File Structure

```
docs/
├── index.html          # Main gallery grid
├── poem.html           # Individual poem detail page
├── styles.css          # Styling (matches your portfolio)
├── app.js              # Gallery functionality
├── poem.js             # Detail page functionality
├── poems.json          # Generated data file
└── images/             # Poem images (copied from instagram_posts/)
```

## 🎨 Design Notes

- **Typography**: IBM Plex Sans & Mono (clean, modern)
- **Layout**: Responsive grid, mobile-friendly
- **Colors**: Neutral palette that complements your portfolio
- **Interactions**: Smooth transitions, hover effects

## 🔧 Customization

### Update colors:

Edit `styles.css` `:root` variables:

```css
:root {
    --primary: #1a1a1a;      /* Main text */
    --secondary: #4a4a4a;    /* Secondary text */
    --accent: #2e7d32;       /* Accent color */
    --light: #f5f5f5;        /* Backgrounds */
}
```

### Change fonts:

Update the Google Fonts link in `index.html` and `poem.html`, then modify CSS:

```css
--font-sans: 'YourFont', sans-serif;
--font-mono: 'YourMonoFont', monospace;
```

## 📊 Features

- **Grid Gallery**: Responsive card layout
- **Theme Filtering**: Filter by moisture state
- **Rating System**: Like/dislike (stored in localStorage)
- **Stats Dashboard**: Total poems, days running, interactions
- **Detail Views**: Full metadata, sensor data, AI prompts
- **Multiple Renders**: Light/dark/footnote versions
- **Mobile Responsive**: Works on all devices

## 💾 Data Storage

Ratings are stored in browser localStorage:
- `biopoem_ratings`: Global rating counts
- `biopoem_user_ratings`: Individual user's ratings

To add backend storage later, modify `app.js` rating methods.

## 🔄 Automation Ideas

### Auto-update gallery nightly:

Add to cron (on your Raspberry Pi):

```bash
0 21 * * * cd /home/biopoem && python3 generate_gallery_data.py && git add docs/poems.json && git commit -m "Daily gallery update" && git push
```

This will automatically push new poems to the website each night after generation.

## 🌐 Custom Domain (Optional)

To use a custom domain:

1. Add `CNAME` file to docs/:
   ```
   biopoem.yourdomain.com
   ```

2. Configure DNS:
   - Add CNAME record pointing to `YOUR_USERNAME.github.io`

3. Update in GitHub Settings → Pages → Custom domain

## 🐛 Troubleshooting

**Images not loading?**
- Check `docs/images/` folder exists and has correct structure
- Verify paths in `poems.json` are relative: `images/2026/feb/...`

**Poems not showing?**
- Check browser console for errors
- Verify `poems.json` is valid JSON
- Make sure images paths match actual files

**GitHub Pages not updating?**
- Check Actions tab for build status
- Wait 2-3 minutes after push
- Hard refresh browser (Ctrl+Shift+R)

## 📝 License

Part of BioPoem project © 2024-2026 Jorge Arreola
