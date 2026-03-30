# BioPoem Gallery

A public gallery of poems generated from plant sensor data, with community rating functionality.

## Live Site

Coming soon: [GitHub Pages URL]

## Local Development

See [docs/README.md](docs/README.md) for setup instructions.

## Quick Start

```bash
# Generate gallery data
python3 generate_gallery_data.py

# Test locally
cd docs
python3 -m http.server 8000
# Visit http://localhost:8000
```

## Features

- Grid gallery of all poems with rendered images
- Filter by moisture theme (thirsting, enduring, sustained, sated, recovering)
- Community rating system (like/dislike)
- Detailed poem view with sensor data, AI prompts, and multiple renders
- Mobile-responsive design
- Stats dashboard

## Tech Stack

- Pure HTML/CSS/JavaScript (no build step required)
- GitHub Pages hosting
- localStorage for ratings (upgradeable to backend)

## Project Structure

```
docs/               # GitHub Pages site
├── index.html      # Main gallery
├── poem.html       # Detail page
├── styles.css      # Styling
├── app.js          # Gallery logic
├── poem.js         # Detail logic
├── poems.json      # Generated data
└── images/         # Poem renders
```
