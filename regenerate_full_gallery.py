#!/usr/bin/env python3
"""
Regenerate gallery by scanning ALL instagram_posts folders
This will include older poems from 2025 that aren't in poem_history.json
"""

import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime

def parse_date_from_folder_path(folder_path):
    """
    Extract date from folder path
    Examples:
      instagram_posts/2026/mar/15/poem_title/ -> 2026-03-15
      instagram_posts/11_November/30/poem_title/ -> 2025-11-30
      instagram_posts/12_December/21/poem_title/ -> 2025-12-21
    """
    parts = folder_path.parts
    
    # New format: 2026/mar/15
    if len(parts) >= 3 and parts[0] == 'instagram_posts' and parts[1].isdigit():
        year = parts[1]
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month = month_map.get(parts[2].lower(), '01')
        day = parts[3] if len(parts) > 3 else '01'
        return f"{year}-{month}-{day.zfill(2)}"
    
    # Old format: 11_November/30 or 12_December/21
    if len(parts) >= 3 and parts[0] == 'instagram_posts':
        month_folder = parts[1]
        day = parts[2]
        
        # Extract month number from "11_November" or "12_December"
        month_match = re.match(r'(\d+)_', month_folder)
        if month_match:
            month = month_match.group(1).zfill(2)
            # Assume 2025 for old format
            year = '2025'
            return f"{year}-{month}-{day.zfill(2)}"
    
    return None

def extract_title_from_folder(folder_name):
    """Convert folder name to title"""
    # Remove _visual suffix if present
    name = folder_name.replace('_visual', '')
    # Split on underscores and capitalize
    words = name.split('_')
    title = ' '.join(word.capitalize() for word in words)
    return title

def guess_theme_from_title(title):
    """Try to guess theme from title keywords"""
    title_lower = title.lower()
    
    if any(word in title_lower for word in ['thirst', 'want', 'craving', 'need', 'dry']):
        return 'thirsting'
    elif any(word in title_lower for word in ['endur', 'persist', 'withstand']):
        return 'enduring'
    elif any(word in title_lower for word in ['sustain', 'maintain', 'steady', 'balance']):
        return 'sustained'
    elif any(word in title_lower for word in ['sated', 'full', 'overflow', 'abundance', 'wet']):
        return 'sated'
    elif any(word in title_lower for word in ['recover', 'heal', 'return', 'bounce']):
        return 'recovering'
    
    return 'sustained'  # default

def scan_instagram_posts():
    """Scan all folders in instagram_posts and generate gallery data"""
    
    poems_data = []
    base_path = Path('instagram_posts')
    
    if not base_path.exists():
        print("❌ instagram_posts folder not found")
        return []
    
    print("🔍 Scanning instagram_posts for all poems...")
    
    # Find all poem folders (deepest level directories)
    poem_folders = []
    for root, dirs, files in os.walk(base_path):
        # If this directory has image files, it's a poem folder
        if any(f.endswith('.jpg') or f.endswith('.png') for f in files):
            poem_folders.append(Path(root))
    
    print(f"Found {len(poem_folders)} poem folders")
    
    for folder in sorted(poem_folders):
        try:
            # Extract date
            date_str = parse_date_from_folder_path(folder)
            if not date_str:
                print(f"  ⚠ Couldn't parse date from: {folder}")
                continue
            
            # Extract title
            folder_name = folder.name
            title = extract_title_from_folder(folder_name)
            
            # Guess theme
            theme = guess_theme_from_title(title)
            
            # Find images in this folder
            images = list(folder.glob('*32pt*poem*dark.jpg'))
            if not images:
                images = list(folder.glob('*poem*dark.jpg'))
            if not images:
                images = list(folder.glob('*poem*.jpg'))
            
            if not images:
                print(f"  ⚠ No poem image found in: {folder}")
                continue
            
            primary_image = images[0]
            
            # Copy images to docs/images/ (maintaining folder structure)
            src_folder = folder
            dest_folder = Path('docs') / str(folder).replace('instagram_posts/', 'images/')
            dest_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy all images from src to dest
            for img_file in folder.glob('*.jpg'):
                dest_file = dest_folder / img_file.name
                if not dest_file.exists() or img_file.stat().st_mtime > dest_file.stat().st_mtime:
                    shutil.copy2(img_file, dest_file)
            
            # Get relative path for web
            primary_rel = str(primary_image).replace('instagram_posts/', 'images/')
            
            # Find additional renders
            additional = []
            
            # Footnote
            footnote = list(folder.glob('*footnote*dark.jpg'))
            if footnote:
                additional.append({
                    'src': str(footnote[0]).replace('instagram_posts/', 'images/'),
                    'label': 'Sensor Summary'
                })
            
            # Prompt
            prompt_img = list(folder.glob('*prompt*dark.jpg'))
            if prompt_img:
                additional.append({
                    'src': str(prompt_img[0]).replace('instagram_posts/', 'images/'),
                    'label': 'AI Prompt'
                })
            
            # Use folder modification time to get actual timestamp
            folder_mtime = folder.stat().st_mtime
            actual_datetime = datetime.fromtimestamp(folder_mtime)
            timestamp_str = actual_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Create poem entry
            slug = folder_name.replace('_visual', '')
            poem_entry = {
                'id': f"{timestamp_str}_{slug}",
                'title': title,
                'date': timestamp_str,
                'theme': theme,
                'influence': 'unknown',  # Can't determine from folders
                'image': primary_rel,
                'additional_renders': additional
            }
            
            poems_data.append(poem_entry)
            print(f"  ✓ {date_str}: {title}")
            
        except Exception as e:
            print(f"  ❌ Error processing {folder}: {e}")
            continue
    
    # Sort by date (newest first)
    poems_data.sort(key=lambda x: x['date'], reverse=True)
    
    return poems_data

def main():
    """Main execution"""
    
    # Scan all poems
    poems_data = scan_instagram_posts()
    
    if not poems_data:
        print("\n❌ No poems found!")
        return
    
    # Write to docs/poems.json
    output_path = Path('docs/poems.json')
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(poems_data, f, indent=2)
    
    print(f"\n✅ Generated gallery with {len(poems_data)} poems")
    print(f"   Saved to: {output_path}")
    
    # Show breakdown by year/month
    from collections import Counter
    dates = [p['date'][:7] for p in poems_data]  # YYYY-MM
    counts = Counter(dates)
    
    print("\n📅 Poems by month:")
    for date in sorted(counts.keys(), reverse=True):
        print(f"   {date}: {counts[date]} poems")

if __name__ == '__main__':
    main()
