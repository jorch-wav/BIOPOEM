# Gallery Setup Notes

## Header Image

The gallery is designed to display a houseplant image in the header. The HTML references `plant.jpg` in the docs folder.

**To add the image:**

1. Copy your plant image from your Mac to the Raspberry Pi:
   ```bash
   scp /Users/jorgearreola/portfolio-site/experiments/Biopoem/5.jpg biopoem@192.168.0.242:/home/biopoem/docs/plant.jpg
   ```

2. Or if you're on the Pi, you can add any square plant image as `docs/plant.jpg`

The image will be displayed as an 80x80px square with a green border in the header next to the title.

If the image is not found, it will be hidden automatically (onerror handler).

## Gallery Features

### Dark Mode
- All poems display using 32pt dark mode renders (matching the Raspberry Pi display)
- Dark theme throughout with green accents

### Rating System
- 👍 Thumbs up (like)
- 👎 Thumbs down (dislike)  
- 💬 Comment (opens text input with 280 character limit)

### Consistent Renders
Currently using: **32pt_poem_dark.jpg** for all primary poem displays

Additional renders shown on detail pages:
- 32pt_footnote_dark.jpg (Sensor Summary)
- prompt_dark.jpg (AI Prompt)

All renders use consistent 32pt font size and dark backgrounds.

## Local Testing

Access the gallery at:
```
http://192.168.0.242:8080
```

## Deployment

When ready to deploy to GitHub Pages:
```bash
cd /home/biopoem
./deploy_gallery.sh
```

This will:
1. Regenerate poems.json with latest poems
2. Copy any new images
3. Commit and push to GitHub

Then enable Pages in your GitHub repo settings (Settings → Pages → source: main branch, /docs folder).
