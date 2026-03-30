# BioPoem Gallery

**A living houseplant generates daily poetry from sensor readings.**

View the gallery: **[https://jorch-wav.github.io/BIOPOEM/](https://jorch-wav.github.io/BIOPOEM/)**

---

## About

BioPoem is an AI poetry project where a *Peperomia magnoliifolia* houseplant generates poems based on its environmental conditions. The plant's sensor readings (soil moisture, temperature, light, humidity, atmospheric pressure) are translated into metaphorical language through a custom poetry engine with 250+ hand-crafted metaphors.

## Gallery Features

- **261 poems** generated from January 2025 to March 2026
- **Dark mode visual renders** optimized for display
- **Filter by theme**: Dry, Low, Comfortable, Wet, Bouncing Back
- **Sensor data & AI prompts** shown alongside each poem
- **Community feedback system** (dev version only)

## Technical Details

- **Frontend**: Vanilla JavaScript, CSS Grid, responsive design
- **Images**: Pre-rendered JPG files from Instagram post generator
- **Poetry Engine**: Python + Claude API (Anthropic)
- **Sensors**: ADS1115 ADC, BME280, DS18B20 temperature sensor
- **Hardware**: Raspberry Pi 4

## Repository Structure

```
docs/               # GitHub Pages gallery (public)
  ├── index.html    # Gallery page
  ├── app.js        # Frontend logic
  ├── styles.css    # Dark theme styling
  ├── poems.json    # All 261 poems with metadata
  └── images/       # Rendered poem images (symlink to instagram_posts)
```

## Local Development Version

The **dev version** includes a feedback system where visitors can rate poems and leave comments. This feedback is analyzed weekly to influence future poem generation:

- Backend: Flask + SQLite
- Analysis: Keyword extraction from comments
- Learning: Feedback is injected into AI prompts

See [TWO_PAGE_SYSTEM.md](TWO_PAGE_SYSTEM.md) and [HOW_AI_LEARNS_FROM_FEEDBACK.md](HOW_AI_LEARNS_FROM_FEEDBACK.md) for details.

## Credits

**Created by Jorge Arreola**  
An exercise in poetry and creative coding

---

© 2024-2026 Jorge Arreola
