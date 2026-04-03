#!/usr/bin/env python3
"""
BIOPOEM - Plant Poetry Generation System
VERSION: 2.0.0
Last Updated: 2025-12-06

A real-time plant monitoring system that generates daily and weekly poetry inspired by 
sensor data (voltage, moisture, temperature, light). Poems are automatically 
created (daily at 8pm, weekly on Sundays at 8am) using Claude AI and distributed via email.

NEW in V2.0: Poet Expansion & Tonal Rebalancing
- Expanded from 13 to 21 distinct poetic influences
- All influences now attributed to specific poets (Pizarnik, Oliver, Limón, Sabines, 
  Smith, Ak'abal, Borges, Issa, Paz, Glück, Diaz, plus original pseudocode style)
- Poems shortened to 6-10 lines (daily) and 10-14 lines (weekly) for Instagram
- Visual poetry patterns now forced every 3rd generation for variety
- Tonal rebalancing: Added joy/playful/curious modifiers to reduce somber bias
- Emotional translations updated to celebrate healthy conditions (vitality, confidence, delight)
- Enhanced vocabulary with positive expressions (exuberance, satisfaction, vigor)
- Cleaner footnotes (removed decorative dashes)

V1.5 Features:
- Repetition Prevention: Tracks themes, influences, phrases over 30-day window
- Diversity scoring boosts under-used themes
- Detects "safe mode" patterns and overused phrases
- Reports phrase/theme/influence usage statistics

Features:
- Live sensor dashboard with waveform visualization
- Historical data logging with session tracking
- Daily AI poem generation (Claude 3.5 Sonnet) - 8pm daily
- Weekly reflection poems - 8am Sundays
- Automatic Google Drive sync for Instagram posts
- Automatic Notion database integration with poem type tracking
- Email distribution system with daily/weekly/both preferences
- Interactive poem display with tap-to-toggle UI

Screens:
1. Dashboard - Live sensor readings with waveforms
2. Logger - Historical data visualization and analysis
3. Poem - Generated poetry display and generation controls

Key Controls:
- G: Generate daily poem manually (6-10 lines, 24hr data)
- W: Generate weekly poem manually (10-14 lines, 7-day reflection)
- E: Send test email (with confirmation)
- U: Upload current poem to Notion
- Screen navigation: "Scr" button or click screen number
"""

import os, time, csv, math, threading, subprocess
from collections import deque
from statistics import mean
from datetime import datetime, timedelta
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Poetry engine integration
import sys
debug_log = []
debug_log.append(f"Python executable: {sys.executable}")
debug_log.append(f"Python version: {sys.version}")
try:
    import pandas
    debug_log.append("Pandas import successful!")
except Exception as e:
    debug_log.append(f"Pandas import FAILED: {e}")
    
try:
    from poetry_engine import DailyPoetryGenerator
    from api_client import PoemAPIClient
    from instagram_renderer import InstagramRenderer
    POETRY_AVAILABLE = True
    debug_log.append("Poetry engine imports successful!")
except ImportError as e:
    POETRY_AVAILABLE = False
    debug_log.append(f"Poetry import failed: {e}")
except Exception as e:
    POETRY_AVAILABLE = False
    debug_log.append(f"Poetry import error: {e}")

# Write debug log to file
with open("import_debug.log", "w") as f:
    f.write("\n".join(debug_log))
    
for line in debug_log:
    print(f"[DEBUG] {line}")


# Notion integration
try:
    from notion_client import Client as NotionClient
    NOTION_AVAILABLE = True
    print("[DEBUG] Notion client available")
except ImportError:
    NOTION_AVAILABLE = False
    print("[DEBUG] Notion client not available")

# Poem generation logger
try:
    from poem_generation_logger import PoemGenerationLogger
    LOGGER_AVAILABLE = True
    print("[DEBUG] Poem generation logger available")
except ImportError:
    LOGGER_AVAILABLE = False
    print("[DEBUG] Poem generation logger not available")

load_dotenv()
import pygame

# ---------- Optional hardware libs (safe import) ----------
try:
    import board, busio
except Exception:
    board = busio = None

# ADS1115 (plant voltage)
try:
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except Exception:
    ADS = AnalogIn = None

# Seesaw (soil)
try:
    from adafruit_seesaw.seesaw import Seesaw
except Exception:
    Seesaw = None

# VEML6030 (lux) - PiicoDev sensor
try:
    from PiicoDev_VEML6030 import PiicoDev_VEML6030
except Exception:
    PiicoDev_VEML6030 = None

# BME280 (temp/humidity/pressure) - PiicoDev sensor
try:
    from PiicoDev_BME280 import PiicoDev_BME280
except Exception:
    PiicoDev_BME280 = None

# Grove ADC for capacitive soil sensor on A0
try:
    from grove.adc import ADC as GroveADC
except Exception:
    GroveADC = None

# RGB LED for poem generation indicator
try:
    from PiicoDev_RGB import PiicoDev_RGB
except Exception:
    PiicoDev_RGB = None

import pygame

APP_VERSION              = "V1.6.0"  # ECG removed, simplified sampling
CSV_PATH                 = "plant_soil_log.csv"
LOCATION_DEFAULT         = "office"

# Logging cadence
DEFAULT_LOG_INTERVAL_S   = 900.0     # 15 minutes
DEFAULT_BURST_SECONDS    = 1.0       # Quick 1-second burst (no voltage waveform)
BURST_HZ                 = 3         # 3 samples to average out noise
DASH_HZ                  = 1         # Reduced from 3Hz - less CPU, smoother display
DASH_KEEP_S              = 60        # Extended to 60s for better transpiration calc

# Time window & bounds
WINDOW_SECONDS_DEFAULT   = 6*60*60
MAX_BUFFER_SECONDS       = 365*24*60*60  # 1 year of data
SESSION_GAP_S            = 2*DEFAULT_LOG_INTERVAL_S

# Hardware settings (ADS1115 disabled but keeping config for reference)
ADS_ADDR   = 0x48
ADS_GAIN   = 1
ADS_SPS    = 16
ADS_CH     = 0
SOIL_ADDR  = 0x36  # STEMMA address (kept for reference, not used)
# Calibrated for Grove Capacitive Soil Moisture v2.0 on A0
# Sensor reads: 819 (air/dry) to 337 (water) - lower = wetter
# For plant soil: 700 (needs water) to 430 (well-watered)
SOIL_DRY_REF   = 700   # "Needs water" - 0% moisture
SOIL_WET_REF   = 430   # Just watered - 100% moisture
SOIL_AIR_REF   = 819   # Sensor in air (absolute dry)
SOIL_WATER_REF = 337   # Sensor in water (absolute wet)

# UI
FPS_UI             = 30
TOPBAR_H           = 60
PANEL_MARGIN       = 10
GRID_Y_STEPS       = 4
BG_COLOR           = (6,6,8)
AXIS_COLOR         = (35,35,35)
GRID_COLOR         = (50,50,50)
TEXT_COLOR         = (230,230,230)
LINE_COLOR         = (225,235,255)
BTN_BG             = (25,25,28)
BTN_FG             = (240,240,240)
BTN_ACTIVE         = (60,100,60)
BTN_WARN           = (130,60,60)
LIVE_HILITE        = (90,150,90)
ECG_SHARP          = (80,255,140)
ECG_GLOW           = (40,120,70)
SESSION_COLOR      = (70,80,120)

# Y-range helpers
Y_SMOOTH_ALPHA = 0.2
Y_MAX_STEP_FRAC= 0.18
WHEEL_ZOOM_FACTOR = 0.85
X_SPAN_MIN     = 60.0
X_SPAN_MAX     = MAX_BUFFER_SECONDS

# Clamps/spans
V_CLAMP_DEFAULT = (0.5, 3.5)
V_CLAMP_WIDE    = (0.0, 5.0)  # Wider range to see full waveform
V_MIN_SPAN      = 0.01
MP_CLAMP        = (0.0, 100.0)
MP_MIN_SPAN     = 1.0
TC_CLAMP        = (-10.0, 60.0)
TC_MIN_SPAN     = 0.5
LX_CLAMP        = (0.0, 10000.0)   # Wide range for various lighting conditions
LX_MIN_SPAN     = 50.0             # Reasonable span for indoor light
HU_CLAMP        = (0.0, 100.0)   # Humidity percentage
HU_MIN_SPAN     = 5.0
PR_CLAMP        = (950.0, 1050.0)  # Pressure in hPa (typical indoor range)
PR_MIN_SPAN     = 5.0

# Outlier guards
V_ABS_RANGE  = (-0.5, 5.5)
MP_ABS_RANGE = (-5.0, 105.0)
TC_ABS_RANGE = (-40.0, 85.0)
LX_ABS_RANGE = (-10.0, 50000.0)
HU_ABS_RANGE = (-5.0, 105.0)
PR_ABS_RANGE = (800.0, 1200.0)

CSV_HEADER = [
    "datetime","t_s","location",
    "plant_V_avg","plant_V_min","plant_V_max",
    "soil_raw_avg","soil_pct_avg",
    "temp_C_avg","humidity_pct_avg","pressure_hPa_avg",
    "lux_lx_avg",
    "event_mark","event_note"
]

# ---------- helpers ----------
def moisture_pct_from_raw(raw):
    """Convert capacitive soil sensor raw value to percentage.
    Capacitive sensor: lower raw = wetter (opposite of STEMMA)
    SOIL_DRY_REF (700) = 0%, SOIL_WET_REF (430) = 100%
    """
    if raw is None: return None
    span = max(1, SOIL_DRY_REF - SOIL_WET_REF)  # 700 - 430 = 270
    # Lower raw value = higher moisture percentage
    pct = 100.0 * (SOIL_DRY_REF - raw) / span
    return max(0.0, min(100.0, pct))

def fmt_hms(s):
    s = int(max(0, s)); h=s//3600; m=(s%3600)//60; sec=s%60
    return f"{h:02d}:{m:02d}:{sec:02d}"

def percentile(vals, p):
    xs = sorted(x for x in vals if x is not None)
    if not xs: return None
    if len(xs)==1: return xs[0]
    k = (len(xs)-1)*(p/100.0); f=math.floor(k); c=math.ceil(k)
    if f==c: return xs[int(k)]
    return xs[f] + (xs[c]-xs[f])*(k-f)

def adaptive_range(vals, default=(1.45,1.55), min_span=0.02, pad_frac=0.08, clamp=None):
    v = [x for x in vals if x is not None]
    if not v: lo,hi = default
    else:
        p10=percentile(v,10); p90=percentile(v,90)
        if p10 is None or p90 is None: lo,hi=default
        else:
            if p90-p10<min_span:
                mid=0.5*(p90+p10); lo,hi = mid-0.5*min_span, mid+0.5*min_span
            else: lo,hi = p10,p90
    pad=(hi-lo)*pad_frac; lo-=pad; hi+=pad
    if clamp:
        lo=max(clamp[0],lo); hi=min(clamp[1],hi)
        if hi-lo<min_span:
            mid=0.5*(hi+lo); lo=max(clamp[0],mid-0.5*min_span); hi=min(clamp[1],mid+0.5*min_span)
    return lo,hi,(hi-lo)

def nice_round(x):
    if x==0: return 1
    mag=10**int(math.floor(math.log10(abs(x)))); norm=x/mag
    if norm<1.5:step=1
    elif norm<3:step=2
    elif norm<7:step=5
    else:step=10
    return step*mag

def clampf(v,lo,hi): return max(lo,min(hi,v))
def is_outlier(v,r): return (v is not None) and (v<r[0] or v>r[1])

# ---------- Simple On-Screen Keyboard ----------
class SimpleKeyboard:
    """Simple on-screen keyboard for touchscreen input"""
    def __init__(self, screen, font):
        self.screen = screen
        self.font = font
        self.visible = False
        self.numeric_mode = False  # Flag for numeric-only keyboard
        
        # Full keyboard layout
        self.rows = [
            ['1','2','3','4','5','6','7','8','9','0'],
            ['q','w','e','r','t','y','u','i','o','p'],
            ['a','s','d','f','g','h','j','k','l','.'],
            ['z','x','c','v','b','n','m','_','-','@'],
            ['SPACE', 'BACKSPACE']
        ]
        
        # Numeric keyboard layout (for intervals/burst values)
        self.numeric_rows = [
            ['1','2','3'],
            ['4','5','6'],
            ['7','8','9'],
            ['.','0','CLEAR'],
            ['BACKSPACE']
        ]
        
        self.key_rects = {}
        self.build_layout()
    
    def build_layout(self):
        """Build keyboard layout with button rectangles"""
        sw, sh = self.screen.get_size()
        
        # Keyboard at bottom of screen
        kbd_h = 200
        kbd_y = sh - kbd_h
        
        rows_to_use = self.numeric_rows if self.numeric_mode else self.rows
        
        if self.numeric_mode:
            # Larger keys for numeric mode
            key_w = 100
            key_h = 35
        else:
            key_w = 70
            key_h = 35
        
        margin = 5
        
        self.key_rects.clear()
        y = kbd_y + 10
        
        for row_idx, row in enumerate(rows_to_use):
            # Center each row
            total_w = 0
            for key in row:
                if key == 'SPACE':
                    total_w += key_w * 4 + margin
                elif key == 'BACKSPACE':
                    total_w += key_w * 3 + margin if not self.numeric_mode else key_w * 3 + margin
                elif key == 'CLEAR':
                    total_w += key_w + margin
                else:
                    total_w += key_w + margin
            
            x_start = (sw - total_w) // 2
            x = x_start
            
            for key in row:
                if key == 'SPACE':
                    w = key_w * 4
                elif key == 'BACKSPACE':
                    w = key_w * 3
                elif key == 'CLEAR':
                    w = key_w
                else:
                    w = key_w
                
                self.key_rects[key] = pygame.Rect(x, y, w, key_h)
                x += w + margin
            
            y += key_h + margin
    
    def set_mode(self, numeric=False):
        """Set keyboard mode and rebuild layout"""
        self.numeric_mode = numeric
        self.build_layout()
    
    def draw(self):
        """Draw the keyboard"""
        if not self.visible:
            return
        
        # Semi-transparent background
        sw, sh = self.screen.get_size()
        overlay = pygame.Surface((sw, 200))
        overlay.set_alpha(240)
        overlay.fill((20, 20, 25))
        self.screen.blit(overlay, (0, sh - 200))
        
        # Draw keys
        for key, rect in self.key_rects.items():
            # Key background - different color for CLEAR
            if key == 'CLEAR':
                bg_color = (120, 60, 60)
                border_color = (160, 100, 100)
            else:
                bg_color = (60, 60, 70)
                border_color = (100, 100, 110)
            
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=5)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=5)
            
            # Key label
            if key == 'SPACE':
                label = 'Space'
            elif key == 'BACKSPACE':
                label = 'Del'
            elif key == 'CLEAR':
                label = 'Clear'
            else:
                label = key
            
            txt = self.font.render(label, True, (240, 240, 240))
            self.screen.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))
    
    def handle_click(self, pos):
        """Handle keyboard click, return the key pressed or None"""
        if not self.visible:
            return None
        
        for key, rect in self.key_rects.items():
            if rect.collidepoint(pos):
                if key == 'SPACE':
                    return ' '
                elif key == 'BACKSPACE':
                    return '\b'  # Backspace character
                elif key == 'CLEAR':
                    return '\x7f'  # DEL character (we'll use this as "clear all")
                else:
                    return key
        return None
    
    def toggle(self):
        """Toggle keyboard visibility"""
        self.visible = not self.visible
        if self.visible:
            self.build_layout()  # Rebuild in case mode changed
    
    def show(self):
        """Show keyboard"""
        self.visible = True
        self.build_layout()
    
    def hide(self):
        """Hide keyboard"""
        self.visible = False

# ---------- DataStore ----------
class DataStore:
    def __init__(self, max_s=MAX_BUFFER_SECONDS):
        self.t=deque(); self.v=deque(); self.vmin=deque(); self.vmax=deque()
        self.mr=deque(); self.mp=deque(); self.tc=deque(); self.lx=deque()
        self.hu=deque(); self.pr=deque()  # humidity and pressure from BME280
        self.mark=deque(); self.note=deque(); self.loc=deque()
        self.max_s=max_s; self.sessions=[]
    def push(self,t,v,vmin,vmax,mr,mp,tc,hu,pr,lx,mark,note,loc):
        self.t.append(t); self.v.append(v); self.vmin.append(vmin); self.vmax.append(vmax)
        self.mr.append(mr); self.mp.append(mp); self.tc.append(tc)
        self.hu.append(hu); self.pr.append(pr); self.lx.append(lx)
        self.mark.append(mark); self.note.append(note); self.loc.append(loc)
        self._trim(t); self.recompute_sessions()
    def _trim(self,now):
        ch=False
        while self.t and (now-self.t[0])>self.max_s:
            for q in (self.t,self.v,self.vmin,self.vmax,self.mr,self.mp,self.tc,self.hu,self.pr,self.lx,self.mark,self.note,self.loc):
                q.popleft()
            ch=True
        if ch: self.recompute_sessions()
    def window_indices(self, tmax, span):
        if not self.t: return 0,-1
        tmin=tmax-span
        li=0
        while li<len(self.t) and self.t[li]<tmin: li+=1
        ri=len(self.t)-1
        while ri>=0 and self.t[ri]>tmax: ri-=1
        return max(0,li-1), max(ri,-1)
    def recompute_sessions(self):
        self.sessions=[]
        if not self.t: return
        s=self.t[0]; prev=self.t[0]
        for i in range(1,len(self.t)):
            ti=self.t[i]
            if (ti-prev)>SESSION_GAP_S:
                self.sessions.append((s,prev)); s=ti
            prev=ti
        self.sessions.append((s,self.t[-1]))

# ---------- UI ----------
class Button:
    def __init__(self, rect, label):
        self.rect=pygame.Rect(rect); self.label=label
        self.is_toggle=False; self.toggled=False; self.active=False
        self.color_override=None  # Optional custom color
    def draw(self, surf, font, warn=False):
        # If color_override is set, use it
        if self.color_override:
            bg = self.color_override
        # If toggle button shows "Stop", make it red (warn color)
        elif self.is_toggle and self.toggled and self.label == "Stop":
            bg = BTN_WARN
        elif self.active:
            # Active tab - brighter background
            bg = (80, 100, 140)
        else:
            bg = BTN_ACTIVE if (self.is_toggle and self.toggled) else (BTN_WARN if warn else BTN_BG)
        
        # Border color - brighter for active
        border_color = (140, 160, 200) if self.active else (70, 70, 70)
        
        pygame.draw.rect(surf, bg, self.rect, border_radius=8)
        pygame.draw.rect(surf, border_color, self.rect, 2, border_radius=8)
        # Use smaller font for button text to prevent overflow
        txt=font.render(self.label,True, BTN_FG)
        # Scale down if text is too wide for button
        if txt.get_width() > self.rect.width - 8:
            # Truncate label if needed
            label = self.label
            while txt.get_width() > self.rect.width - 8 and len(label) > 3:
                label = label[:-1]
                txt = font.render(label, True, BTN_FG)
        surf.blit(txt,(self.rect.centerx-txt.get_width()/2, self.rect.centery-txt.get_height()/2))
    def contains(self, pos): return self.rect.collidepoint(pos)

def draw_grid(surf, rect, ylo, yhi, title, span_label, font, small):
    pygame.draw.rect(surf, AXIS_COLOR, rect, 1)
    rng=max(1e-9,yhi-ylo); step=nice_round(rng/GRID_Y_STEPS)
    yval=math.floor(ylo/step)*step
    while yval<=yhi+1e-9:
        y=rect.bottom-((yval-ylo)/rng)*rect.height
        pygame.draw.line(surf, GRID_COLOR, (rect.left,y),(rect.right,y),1)
        lab=small.render(f"{yval:.2f}",True,(160,160,160))
        surf.blit(lab,(rect.left+4,y-lab.get_height()/2))
        yval+=step
    cap=font.render(title,True,TEXT_COLOR); surf.blit(cap,(rect.left+6,rect.top+2))
    if span_label:
        sp=small.render(span_label,True,(170,170,190))
        surf.blit(sp,(rect.left+6+cap.get_width()+10,rect.top+2))

def draw_session_marks(surf, rect, times, tmin, tmax, color):
    if not times: return
    rngx=max(1e-9,tmax-tmin)
    for ts in times:
        if tmin<=ts<=tmax:
            x=rect.left+(ts-tmin)/rngx*rect.width
            pygame.draw.line(surf,color,(x,rect.top),(x,rect.bottom),1)

def plot_series(surf, rect, ts, ys, tmin, tmax, ymin, ymax, color, dot_color=None, marks=None, out_mask=None):
    if len(ts)<1: return
    rngx=max(1e-9,tmax-tmin); rngy=max(1e-9,ymax-ymin)
    last=None
    for i,(t,yv) in enumerate(zip(ts,ys)):
        if yv is None or not (tmin<=t<=tmax): continue
        x=rect.left+(t-tmin)/rngx*rect.width
        y=rect.bottom-((yv-ymin)/rngy)*rect.height
        # Guard against NaN or infinite values
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))): continue
        if x != x or y != y: continue  # NaN check
        bad = (out_mask[i] if (out_mask and i<len(out_mask)) else False)
        if last and not bad:
            pygame.draw.line(surf,color,last,(x,y),2)
        last=None if bad else (x,y)
    if dot_color is None: dot_color=color
    for i,(t,yv) in enumerate(zip(ts,ys)):
        if yv is None or not (tmin<=t<=tmax): continue
        x=rect.left+(t-tmin)/rngx*rect.width
        y=rect.bottom-((yv-ymin)/rngy)*rect.height
        # Guard against NaN or infinite values
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))): continue
        if x != x or y != y: continue  # NaN check
        bad = (out_mask[i] if (out_mask and i<len(out_mask)) else False)
        if marks and i<len(marks) and marks[i]:
            pygame.draw.line(surf,(120,80,40),(x,rect.top),(x,rect.bottom),1)
            pygame.draw.circle(surf,(255,150,70),(int(x),int(y)),5)
        else:
            pygame.draw.circle(surf,(200,220,255) if not bad else (130,130,130),(int(x),int(y)),3)

def draw_tag(surf, rect, text, bg, fg, font):
    pad=10; t=font.render(text,True,fg)
    w,h=t.get_width()+2*pad, t.get_height()+10
    r=pygame.Rect(rect.right-w-8, rect.top+8, w, h)
    pygame.draw.rect(surf,bg,r,border_radius=10)
    pygame.draw.rect(surf,(200,200,200),r,1,border_radius=10)
    surf.blit(t,(r.left+pad, r.top+5))

# ---------- CSV ----------
def ensure_csv_header(path):
    if (not os.path.exists(path)) or os.path.getsize(path)==0:
        with open(path,"w",newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)

def append_row(path,row):
    with open(path,"a",newline="") as f:
        csv.writer(f).writerow(row)

def load_csv(store,path,loc_default):
    if not os.path.exists(path): return 0,0
    n=0
    with open(path,"r",newline="") as f:
        rd=csv.reader(f); header=next(rd,None)
        if not header: return 0,0
        idx={h:i for i,h in enumerate(header)}
        for row in rd:
            if not row or len(row)<2: continue
            try: ts=float(row[idx.get("t_s",0)])
            except Exception: continue
            loc = row[idx.get("location",1)] if idx.get("location") is not None else loc_default
            def gv(name, conv=float):
                i=idx.get(name,None)
                if i is None or i>=len(row): return None
                s=row[i].strip()
                if s=="": return None
                try: return conv(s)
                except: return None
            vavg=gv("plant_V_avg"); vmin=gv("plant_V_min"); vmax=gv("plant_V_max")
            mraw=gv("soil_raw_avg",int); mp=gv("soil_pct_avg")
            if mp is None and mraw is not None: mp=moisture_pct_from_raw(mraw)
            tc=gv("temp_C_avg"); hu=gv("humidity_pct_avg"); pr=gv("pressure_hPa_avg")
            lx=gv("lux_lx_avg")
            mark=gv("event_mark",int); mark=bool(mark) if mark is not None else False
            note = row[idx["event_note"]] if ("event_note" in idx and idx["event_note"]<len(row)) else ""
            store.push(ts,vavg,vmin,vmax,mraw,mp,tc,hu,pr,lx,mark,note,loc); n+=1
    store.recompute_sessions(); return n, len(store.sessions)

# ---------- Sensors ----------

# LED colors based on moisture state
MOISTURE_LED_COLORS = {
    "thirsting": [255, 0, 0],      # RED - very dry (0-60%)
    "enduring": [255, 140, 0],     # ORANGE - dry (60-75%)
    "sustained": [255, 255, 0],    # YELLOW - moderate (75-85%)
    "sated": [0, 100, 255],        # BLUE - good moisture (85-92%)
    "recovering": [0, 255, 0],     # GREEN - healthy/optimal (92-100%)
}

class Sensors:
    def __init__(self):
        self.ok_ads=False; self.ok_soil=False; self.ok_lux=False
        self.ok_bme=False  # BME280 for temp/humidity/pressure
        self.ok_led=False  # RGB LED for poem generation
        self.soil_adc=None; self.veml=None; self.bme=None; self.led=None
        
        # LED pulsation state
        self._led_pulsing = False
        self._led_thread = None
        
        # PiicoDev sensors create their own I2C bus internally
        # Don't create busio.I2C here - it conflicts
        
        # ADS1115 (ECG/plant voltage) DISABLED
        self.ok_ads = False
        
        # Grove ADC for capacitive soil sensor on A0
        try:
            if GroveADC:
                self.soil_adc = GroveADC()
                self.ok_soil = True
        except Exception: 
            self.ok_soil = False
        
        # BME280 for temperature, humidity, pressure
        try:
            if PiicoDev_BME280:
                self.bme = PiicoDev_BME280()
                self.ok_bme = True
        except Exception: 
            self.ok_bme = False
            
        # VEML6030 for light
        try:
            if PiicoDev_VEML6030:
                self.veml = PiicoDev_VEML6030()
                try:
                    if hasattr(self.veml, 'setGain'):
                        self.veml.setGain(1)
                    if hasattr(self.veml, 'setIntegrationTime'):
                        self.veml.setIntegrationTime(100)
                except Exception:
                    pass
                self.ok_lux = True
        except Exception: 
            self.ok_lux = False
        
        # RGB LED for poem generation indicator
        try:
            import sys
            print(f"[DEBUG] PiicoDev_RGB available: {PiicoDev_RGB is not None}", flush=True)
            sys.stdout.flush()
            if PiicoDev_RGB:
                self.led = PiicoDev_RGB()
                print("[DEBUG] PiicoDev_RGB object created", flush=True)
                sys.stdout.flush()
                self.led.clear()
                self.led.show()
                self.ok_led = True
                print("[DEBUG] RGB LED initialized successfully", flush=True)
                sys.stdout.flush()
            else:
                self.ok_led = False
                print("[DEBUG] PiicoDev_RGB not available", flush=True)
                sys.stdout.flush()
        except Exception as e:
            self.ok_led = False
            print(f"[DEBUG] RGB LED init failed: {e}", flush=True)
            import sys
            sys.stdout.flush()
    
    def start_poem_pulsation(self):
        """Start slow pulsating LED during poem generation"""
        import sys
        print(f"[DEBUG] start_poem_pulsation called. ok_led={self.ok_led}", flush=True)
        sys.stdout.flush()
        
        if not self.ok_led:
            print("[DEBUG] LED not OK, returning", flush=True)
            sys.stdout.flush()
            return
        
        print(f"[DEBUG] Setting _led_pulsing=True", flush=True)
        sys.stdout.flush()
        self._led_pulsing = True
        
        print(f"[DEBUG] Creating thread", flush=True)
        sys.stdout.flush()
        self._led_thread = threading.Thread(target=self._pulsation_loop, daemon=True)
        
        print(f"[DEBUG] Starting thread", flush=True)
        sys.stdout.flush()
        self._led_thread.start()
        
        print(f"[DEBUG] Thread started", flush=True)
        sys.stdout.flush()
    
    def stop_poem_pulsation(self):
        """Stop LED pulsation"""
        self._led_pulsing = False
        if self._led_thread:
            self._led_thread.join(timeout=1.0)
        if self.ok_led:
            try:
                self.led.clear()
                self.led.show()
            except:
                pass
    
    def _get_moisture_state(self):
        """Determine moisture state based on current reading from CSV"""
        # Read the latest moisture value from the CSV file
        try:
            import pandas as pd
            df = pd.read_csv(CSV_PATH)
            if len(df) > 0:
                moisture = df['soil_pct_avg'].iloc[-1]
                if pd.isna(moisture):
                    # If percentage is missing, calculate from raw value
                    raw = df['soil_raw_avg'].iloc[-1]
                    if not pd.isna(raw):
                        moisture = moisture_pct_from_raw(int(raw))
                    else:
                        moisture = 50  # Default to middle
            else:
                moisture = 50  # Default if no data
        except Exception as e:
            print(f"[LED] Error reading moisture: {e}", flush=True)
            moisture = 50  # Default to middle
        
        if moisture < 60:
            return "thirsting"  # RED - very dry
        elif moisture < 75:
            return "enduring"   # ORANGE - dry
        elif moisture < 85:
            return "sustained"  # YELLOW - moderate
        elif moisture < 92:
            return "sated"      # BLUE - good moisture
        else:
            return "recovering" # GREEN - healthy/optimal
    
    def _pulsation_loop(self):
        """Pulsate in moisture-based color - slow breathing effect"""
        import sys
        import math
        print("[DEBUG] Pulsation loop started", flush=True)
        sys.stdout.flush()
        
        cycle_time = 0.0  # Track position in breathing cycle
        
        while self._led_pulsing:
            try:
                # Get color based on current moisture state
                moisture_state = self._get_moisture_state()
                base_color = MOISTURE_LED_COLORS[moisture_state]
                
                # Smooth breathing effect using sine wave (0.4 to 1.0 brightness)
                # Full cycle takes 4 seconds (slow breathing)
                brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(cycle_time))
                
                # Apply brightness to color
                r = int(base_color[0] * brightness)
                g = int(base_color[1] * brightness)
                b = int(base_color[2] * brightness)
                
                # Set all 3 LEDs to same color (breathing together)
                self.led.setPixel(0, [r, g, b])
                self.led.setPixel(1, [r, g, b])
                self.led.setPixel(2, [r, g, b])
                self.led.show()
                
                # Increment cycle time for smooth breathing (4 second cycle)
                cycle_time += 0.05  # Small increment
                if cycle_time >= 2 * math.pi:  # Reset after full cycle
                    cycle_time = 0.0
                
                time.sleep(0.05)  # 20 FPS for smooth animation
                
                time.sleep(0.02)  # 50fps for smooth pulsation
            except Exception as e:
                print(f"[LED] Pulsation error: {e}", flush=True)
                import sys, traceback
                traceback.print_exc()
                sys.stdout.flush()
                time.sleep(0.1)
    
    def read_v(self):
        # Voltage sensor disabled
        return None
    
    def read_mraw(self): 
        """Read capacitive soil sensor from Grove ADC A0"""
        try: 
            if not (self.ok_soil and self.soil_adc):
                return None
            # Take multiple samples for stability
            samples = []
            for _ in range(5):
                try:
                    samples.append(self.soil_adc.read(0))  # A0
                except:
                    pass
            if samples:
                samples.sort()
                return samples[len(samples)//2]  # median
            return None
        except (OSError, Exception): 
            return None
    
    def read_tc(self):  
        """Read temperature from BME280"""
        try: 
            if self.ok_bme and self.bme:
                temp, pressure, humidity = self.bme.values()
                return float(temp)
            return None
        except (OSError, Exception): 
            return None
    
    def read_hu(self):
        """Read humidity from BME280"""
        try:
            if self.ok_bme and self.bme:
                temp, pressure, humidity = self.bme.values()
                return float(humidity)
            return None
        except (OSError, Exception):
            return None
    
    def read_pr(self):
        """Read pressure from BME280 (returns hPa)"""
        try:
            if self.ok_bme and self.bme:
                temp, pressure, humidity = self.bme.values()
                return float(pressure) / 100.0  # Convert Pa to hPa
            return None
        except (OSError, Exception):
            return None
    
    def read_bme_all(self):
        """Read all BME280 values at once (more efficient)"""
        try:
            if self.ok_bme and self.bme:
                temp, pressure, humidity = self.bme.values()
                return float(temp), float(humidity), float(pressure) / 100.0
            return None, None, None
        except (OSError, Exception):
            return None, None, None
    
    def read_lx(self):  
        try: 
            if self.ok_lux and self.veml:
                if hasattr(self.veml, 'light'):
                    val = self.veml.light
                elif hasattr(self.veml, 'readLight'):
                    val = self.veml.readLight()
                elif hasattr(self.veml, 'read'):
                    val = self.veml.read()
                else:
                    return None
                return float(val)
            return None
        except (OSError, Exception):
            return None

# ---------- App ----------
class App:
    DASH, LOG, POEM = 1,2,3
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"Biopoem {APP_VERSION}")
        # Use DOUBLEBUF and HWSURFACE to prevent screen tearing/ghosting
        self.screen=pygame.display.set_mode((0,0), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
        self.sw,self.sh=self.screen.get_size()
        
        # Set screen brightness to 50% (16 out of 31)
        try:
            import subprocess
            subprocess.run(['sudo', 'tee', '/sys/class/backlight/11-0045/brightness'], 
                          input=b'16', check=False, capture_output=True)
        except:
            pass  # If brightness control fails, continue anyway
        self.fontS=pygame.font.SysFont('monospace',20)
        self.font =pygame.font.SysFont('monospace',24)
        self.big  =pygame.font.SysFont('monospace',32,bold=True)
        self.huge =pygame.font.SysFont('monospace',72,bold=True)

        # Panels: 3 vertical sections - top=voltage, middle=moisture+lux, bottom=temperature
        top = TOPBAR_H + 12
        avail = self.sh - top - PANEL_MARGIN
        p1_h = int(avail*0.35)  # plant voltage top
        p_temp_h = int(avail*0.25)  # temperature bottom
        p23_h = avail - p1_h - p_temp_h - 2*PANEL_MARGIN  # middle section for moisture + lux
        p2_w = (self.sw - 3*PANEL_MARGIN)//2
        
        self.p1 = pygame.Rect(PANEL_MARGIN, top, self.sw-2*PANEL_MARGIN, p1_h)
        self.p2 = pygame.Rect(PANEL_MARGIN, self.p1.bottom+PANEL_MARGIN, p2_w, p23_h)
        self.pLux = pygame.Rect(self.p2.right+PANEL_MARGIN, self.p2.top, p2_w, p23_h)
        self.pTemp = pygame.Rect(PANEL_MARGIN, self.p2.bottom+PANEL_MARGIN, self.sw-2*PANEL_MARGIN, p_temp_h)

        # Top navigation buttons - 3 screens + Start logging + Quit
        bx=PANEL_MARGIN; by=8; bh=TOPBAR_H-16
        btn_width = (self.sw - PANEL_MARGIN*2 - 8*5) // 5  # 5 buttons evenly spaced
        def mk(label,w=None):
            nonlocal bx
            width = w if w else btn_width
            r=pygame.Rect(bx,by,width,bh); bx+=width+8; b=Button(r,label); return b
        
        self.b_live  = mk("LIVE")   # Screen 1: Dashboard
        self.b_stats = mk("STATS")  # Screen 2: Logger
        self.b_poem  = mk("POEM")   # Screen 3: Poem display
        
        # Generate button on the right side (separated)
        gen_btn_width = 160
        gen_x = self.sw - PANEL_MARGIN - gen_btn_width
        self.b_generate = Button(pygame.Rect(gen_x, by, gen_btn_width, bh), "GENERATE")
        self.b_generate.color_override = (60, 150, 80)  # Light green
        
        # Zoom buttons (dashboard only) - position on right side
        zoom_bx = self.sw - PANEL_MARGIN - 60
        self.b_zoom_in = Button(pygame.Rect(zoom_bx, by, 50, bh), "+")
        self.b_zoom_out = Button(pygame.Rect(zoom_bx - 58, by, 50, bh), "-")

        # State
        self.screen_id=self.LOG; self._update_scr()
        self.store=DataStore(MAX_BUFFER_SECONDS)
        self.sensors=Sensors()
        self.location=LOCATION_DEFAULT
        ensure_csv_header(CSV_PATH)
        loaded,sess = load_csv(self.store, CSV_PATH, self.location)
        self.view_right = (self.store.t[-1] if self.store.t else time.time())
        self.view_span  = WINDOW_SECONDS_DEFAULT
        self.status = f"Loaded {loaded} rows, {sess} session(s)" if loaded else "New log"

        # zoom/pan
        self.drag=False; self.last_x=None
        self.y_zoom={"v":1.0,"mp":1.0,"lx":1.0,"tc":1.0,"hu":1.0,"pr":1.0}
        self.y_dyn ={"v":[None,None],"mp":[None,None],"lx":[None,None],"tc":[None,None],"hu":[None,None],"pr":[None,None]}
        
        # Dashboard Y-axis zoom (for live waveform)
        self.dash_y_zoom = 1.0  # 1.0 = auto-fit, >1 = zoom in, <1 = zoom out

        # Logging
        self.interval=DEFAULT_LOG_INTERVAL_S; self.burst=DEFAULT_BURST_SECONDS
        self.logging=False; self.next_burst=time.time()+self.interval
        self.log_t0=None; self.elapsed_pause=0
        self.stop_evt=threading.Event(); self.thread=None

        # Burst overlay - scrolling ECG
        self.ecg_window_s = 5.0  # Show last 5 seconds of ECG
        self.live_trace={"ts":deque(maxlen=int(BURST_HZ*10)),"v":deque(maxlen=int(BURST_HZ*10))}
        self.overlay_until=0
        self.burst_start_time=0  # Track when burst started for countdown
        self.burst_duration=0  # Duration of current burst
        self.ecg_zoom = 1.0  # Zoom level for ECG display

        # Dashboard live buffers
        self.dash_on=True; self.dash_enter=time.time()  # Start live immediately
        self.dash_next=time.time(); self.dash_dt=1.0/DASH_HZ
        self.dash = {
            "t": deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "v": deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "mp":deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "tc":deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "hu":deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "pr":deque(maxlen=DASH_HZ*DASH_KEEP_S),
            "lx":deque(maxlen=DASH_HZ*DASH_KEEP_S),
        }
        
        # Performance: flag to minimize redraws
        self.needs_redraw = True

        # On-screen keyboard
        self.keyboard = SimpleKeyboard(self.screen, self.font)
        
        # Track app start time (for auto-generation delay)
        self._app_started_at = time.time()
        
        # Poem generation state
        self.poem_gpt = None
        self.poem_claude = None  # Full version for screen 3 display (includes prompt)
        self.poem_for_render = None  # Clean version for Instagram/saving (no prompt)
        self.poem_prompt_data = None  # Store prompt_data for retroactive Notion uploads
        self.generating_poems = False
        self.generation_thread = None
        
        # Terminal typing effect for generation log
        self.log_char_index = []  # Track how many characters revealed per line
        self.log_typing_speed = 3  # Characters to reveal per frame
        
        # Poem screen UI visibility (tap to toggle)
        self.poem_ui_visible = True
        
        # Dark mode for poem screen (screen 3) - default to dark
        self.poem_dark_mode = True  # Manual toggle - default dark
        self.poem_auto_dark_mode = False  # Disabled - always dark unless toggled
        self.last_generation_dark_mode = True  # Track last mode for alternation
        
        # Poem scroll offset (for long poems)
        self.poem_scroll_offset = 0
        self.poem_scroll_start_y = None  # Touch scroll start position
        self.poem_last_scroll_time = 0  # Auto-reset timer
        self.poem_scroll_start_y = None  # Touch scroll start position
        self.poem_scroll_velocity = 0  # For smooth scrolling
        self.poem_last_scroll_time = 0  # Auto-reset timer
        
        # Poem screen carousel state (poem, prompt, footnote)
        self.poem_carousel_index = 0  # 0=poem, 1=prompt, 2=footnote
        self.poem_swipe_start_x = None  # Track horizontal swipe
        self.poem_swipe_start_time = 0
        self.poem_image_paths = {}  # Store paths to rendered images: {mode: {'poem': path, 'prompt': path, 'footnote': path}}
        self.poem_images_loaded = {}  # Cache loaded pygame surfaces
        
        # STATS screen auto-scroll back to latest after 5 mins inactivity
        self.last_interaction_time = time.time()  # Track last user interaction
        
        # Exhibition mode settings
        self.manual_generation_count = 0  # Track manual generations for visual poem frequency
        self.led_quit_tap_count = 0  # Track rapid taps on LED button for hidden quit
        self.led_quit_tap_start_time = 0  # Reset tap count after timeout
        self.quit_confirm_active = False  # Show quit confirmation
        self.quit_confirm_time = 0  # When confirmation was shown
        self.led_quit_flash_time = 0  # Show visual feedback on LED taps
        self.generation_in_progress = False  # Prevent multiple simultaneous generations
        self.generation_progress_message = ""  # Show progress during generation
        self.generation_log = []  # Terminal-style log of generation steps
        
        # Email report prompt for manual generation
        self.prompt_email_report = False
        self.pending_email_data = None
        
        # Auto-generation scheduling (8pm daily)
        self.auto_gen_hour = 20  # 8 PM
        # Initialize to yesterday so 8pm trigger works on first day
        self.last_auto_gen_date = (datetime.now() - timedelta(days=1)).date()
        self.checking_auto_gen = False
        
        # Initialize Notion client
        self.notion_client = None
        self.notion_db_id = None
        if NOTION_AVAILABLE:
            notion_key = os.getenv('NOTION_API_KEY')
            self.notion_db_id = os.getenv('NOTION_DATABASE_ID')
            if notion_key and self.notion_db_id:
                try:
                    self.notion_client = NotionClient(auth=notion_key)
                    print(f"[DEBUG] Notion client initialized (DB: {self.notion_db_id[:8]}...)")
                except Exception as e:
                    print(f"[DEBUG] Notion init failed: {e}")
            else:
                print("[DEBUG] Notion credentials missing in .env")
        
        # Initialize email config
        self.email_enabled = False
        self.smtp_email = os.getenv('SMTP_EMAIL')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        if self.smtp_email and self.smtp_password:
            self.email_enabled = True
            print(f"[DEBUG] Email configured: {self.smtp_email}")
        else:
            print("[DEBUG] Email not configured (add SMTP_EMAIL and SMTP_PASSWORD to .env)")
        
        # Initialize poem generation logger
        # This logs ALL poem generations to poem_generations.csv with:
        # - timestamp, poem text, prompt data, sensor data, API metadata
        # - Check poem_generations.csv for complete generation history
        self.poem_logger = None
        if LOGGER_AVAILABLE:
            try:
                self.poem_logger = PoemGenerationLogger('poem_generations.csv')
                count = self.poem_logger.get_generation_count()
                print(f"[DEBUG] Poem logger initialized ({count} generations logged)")
            except Exception as e:
                print(f"[DEBUG] Poem logger init failed: {e}")

        self.clock=pygame.time.Clock()

        # Load latest poem if exists
        self._load_latest_poem()
        
        # Auto-start logging (after a short delay to let display init)
        # Don't do initial burst - wait for first interval
        self.logging=True
        self.log_t0=time.time()
        self.next_burst=time.time() + 5.0  # First burst after 5 seconds
        self.stop_evt.clear()
        self.thread=threading.Thread(target=self._loop,daemon=True)
        self.thread.start()
        self.status="Logging started"


    # ---------- poem persistence ----------
    def _save_latest_poem(self):
        """Save the current poem to a file with proper linebreaks"""
        # Use poem_for_render (no prompt) for saving, fall back to poem_claude
        poem_to_save = self.poem_for_render or self.poem_claude
        if poem_to_save:
            try:
                # Save poem text (without prompt - just poem + footnote)
                with open('latest_poem.txt', 'w', encoding='utf-8') as f:
                    f.write(poem_to_save)
                print("[DEBUG] Saved poem to latest_poem.txt")
                
                # Save prompt_data for retroactive uploads
                if self.poem_prompt_data:
                    import json
                    import math
                    
                    # Convert any non-serializable objects (like DataFrames, Timestamps) to serializable format
                    def make_serializable(obj):
                        """Recursively convert objects to JSON-serializable format"""
                        import pandas as pd
                        import numpy as np
                        if obj is None:
                            return None
                        elif isinstance(obj, (float, np.floating)):
                            # Handle NaN and Inf - not JSON compliant
                            if math.isnan(obj) or math.isinf(obj):
                                return None
                            return float(obj)
                        elif isinstance(obj, (int, np.integer)):
                            return int(obj)
                        elif hasattr(obj, 'to_dict'):  # DataFrame, Series
                            return make_serializable(obj.to_dict())
                        elif isinstance(obj, (pd.Timestamp, datetime)):
                            return obj.isoformat()
                        elif isinstance(obj, np.ndarray):
                            return [make_serializable(x) for x in obj.tolist()]
                        elif isinstance(obj, dict):
                            return {str(k): make_serializable(v) for k, v in obj.items()}
                        elif isinstance(obj, (list, tuple)):
                            return [make_serializable(item) for item in obj]
                        elif isinstance(obj, str):
                            return obj
                        elif isinstance(obj, bool):
                            return obj
                        else:
                            # Try converting to string as last resort
                            try:
                                return str(obj)
                            except:
                                return None
                    
                    serializable_data = make_serializable(self.poem_prompt_data)
                    
                    with open('latest_poem_data.json', 'w', encoding='utf-8') as f:
                        json.dump(serializable_data, f, indent=2)
                    print("[DEBUG] Saved poem metadata to latest_poem_data.json")
            except Exception as e:
                print(f"[DEBUG] Failed to save poem: {e}")
                import traceback
                traceback.print_exc()
    
    def _update_gallery(self, latest_poem_folder=None):
        """Update the web gallery with the latest poem and auto-deploy to GitHub
        
        Args:
            latest_poem_folder: Optional name of the specific poem folder that was just created
        """
        try:
            import subprocess
            import shutil
            from datetime import datetime
            import time
            
            # Step 1: Copy images FIRST (before regenerating JSON)
            # This ensures the images are in place when gallery JSON references them
            now = datetime.now()
            year = now.strftime('%Y')
            month = now.strftime('%b').lower()
            day = now.strftime('%d')
            
            source_path = f"instagram_posts/{year}/{month}/{day}"
            dest_path = f"docs/images/{year}/{month}/{day}"
            
            if os.path.exists(source_path):
                print(f"[DEBUG] Copying images from {source_path} to {dest_path}...")
                try:
                    # Create destination directory
                    os.makedirs(dest_path, exist_ok=True)
                    
                    # If we know the specific folder, only copy that one
                    # Otherwise copy all folders (for retroactive updates)
                    folders_to_copy = []
                    if latest_poem_folder:
                        # Wait briefly to ensure Instagram render finished writing files
                        time.sleep(0.5)
                        src_folder = os.path.join(source_path, latest_poem_folder)
                        if os.path.exists(src_folder):
                            folders_to_copy = [latest_poem_folder]
                            print(f"[DEBUG] Copying specific folder: {latest_poem_folder}")
                        else:
                            print(f"[DEBUG] Warning: Latest folder not found: {src_folder}")
                            # Fall back to copying all
                            folders_to_copy = [f for f in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, f))]
                    else:
                        # Copy all folders in today's date
                        folders_to_copy = [f for f in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, f))]
                    
                    # Copy folders
                    for poem_folder in folders_to_copy:
                        src_folder = os.path.join(source_path, poem_folder)
                        dst_folder = os.path.join(dest_path, poem_folder)
                        if os.path.isdir(src_folder):
                            if os.path.exists(dst_folder):
                                shutil.rmtree(dst_folder)
                            shutil.copytree(src_folder, dst_folder)
                            print(f"[DEBUG]   ✓ Copied {poem_folder}")
                    
                    print("[DEBUG] ✅ Images copied to docs folder")
                except Exception as e:
                    print(f"[DEBUG] Image copy failed: {e}")
                    import traceback
                    traceback.print_exc()
                    return
            else:
                print(f"[DEBUG] No images found at {source_path} to copy")
            
            # Step 2: Regenerate full gallery JSON (after images are in place)
            script_path = os.path.join(os.path.dirname(__file__), 'regenerate_full_gallery.py')
            if os.path.exists(script_path):
                print("[DEBUG] Regenerating full gallery...")
                result = subprocess.run(
                    ['python3', script_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print("[DEBUG] ✅ Gallery JSON regenerated")
                else:
                    print(f"[DEBUG] Gallery regeneration failed: {result.stderr}")
                    return
            else:
                print(f"[DEBUG] Gallery script not found at {script_path}")
                return
            
            # Step 3: Auto-commit and push to GitHub (background process)
            print("[DEBUG] Auto-deploying to GitHub...")
            try:
                # Run git commands with timeout
                result = subprocess.run(
                    ['git', 'add', 'docs/poems.json', 'docs/images/'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=os.path.dirname(__file__)
                )
                
                # Check if there are changes to commit
                status_result = subprocess.run(
                    ['git', 'status', '--porcelain'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=os.path.dirname(__file__)
                )
                
                if status_result.stdout.strip():
                    # There are changes to commit
                    commit_result = subprocess.run(
                        ['git', 'commit', '-m', f'Auto-deploy: New poem on {year}-{month}-{day}'],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=os.path.dirname(__file__)
                    )
                    
                    # Push to GitHub with proper error handling
                    print("[DEBUG] Pushing to GitHub (this may take 10-30 seconds)...")
                    try:
                        push_result = subprocess.run(
                            ['git', 'push', 'origin', 'master'],
                            capture_output=True,
                            text=True,
                            timeout=60,  # Give it a full minute
                            cwd=os.path.dirname(__file__)
                        )
                        
                        if push_result.returncode == 0:
                            print("[DEBUG] ✅ Git push completed successfully!")
                            print("[DEBUG] Poem will appear on website in 1-2 minutes")
                        else:
                            print(f"[DEBUG] ⚠️ Git push failed:")
                            print(f"[DEBUG] {push_result.stderr}")
                            print("[DEBUG] Manual push needed: cd /home/biopoem && git push origin master")
                    except subprocess.TimeoutExpired:
                        print("[DEBUG] ⚠️ Git push timed out after 60 seconds")
                        print("[DEBUG] Push may still complete in background")
                        print("[DEBUG] Check website in 3-5 minutes")
                else:
                    print("[DEBUG] No changes to commit")
                    
            except Exception as e:
                print(f"[DEBUG] Auto-deployment failed: {e}")
                # Continue anyway - gallery still updated locally
                
        except Exception as e:
            print(f"[DEBUG] Gallery update error: {e}")
    
    def _load_latest_poem(self):
        """Load the latest poem from file with proper linebreaks"""
        import re
        try:
            if os.path.exists('latest_poem.txt'):
                with open('latest_poem.txt', 'r', encoding='utf-8') as f:
                    # Read poem preserving all linebreaks
                    self.poem_claude = f.read()
                print("[DEBUG] Loaded latest poem from file")
                # Debug: check if poem has linebreaks
                line_count = self.poem_claude.count('\n')
                print(f"[DEBUG] Poem has {line_count} linebreaks")
                
                # Try to load associated prompt_data if it exists
                if os.path.exists('latest_poem_data.json'):
                    import json
                    with open('latest_poem_data.json', 'r', encoding='utf-8') as f:
                        json_text = f.read()
                    
                    try:
                        data = json.loads(json_text)
                        self.poem_prompt_data = data
                        print("[DEBUG] Loaded poem metadata for retroactive uploads")
                    except json.JSONDecodeError:
                        # JSON truncated - try regex extraction for key fields
                        print("[DEBUG] JSON truncated, extracting with regex...")
                        self.poem_prompt_data = {'metadata': {}}
                        
                        # Extract visual_pattern
                        pattern_match = re.search(r'"visual_pattern":\s*"([^"]+)"', json_text)
                        if pattern_match:
                            self.poem_prompt_data['metadata']['visual_pattern'] = pattern_match.group(1)
                            print(f"[DEBUG] Extracted visual_pattern: {pattern_match.group(1)}")
                        
                        # Extract primary_theme
                        theme_match = re.search(r'"primary_theme":\s*"([^"]+)"', json_text)
                        if theme_match:
                            self.poem_prompt_data['metadata']['primary_theme'] = theme_match.group(1)
                        
                        # Extract influence
                        influence_match = re.search(r'"influence_name":\s*"([^"]+)"', json_text)
                        if influence_match:
                            self.poem_prompt_data['metadata']['influence_name'] = influence_match.group(1)
                
                # Try to find and load associated rendered images
                self._discover_poem_images()
            else:
                print("[DEBUG] No latest_poem.txt found")
        except Exception as e:
            print(f"[DEBUG] Failed to load poem: {e}")

    def _discover_poem_images(self):
        """Find rendered images for the currently loaded poem"""
        if not self.poem_claude:
            return
        
        try:
            # Extract title from first line
            first_line = self.poem_claude.split('\n')[0].strip()
            # Clean title for filename matching
            title = first_line.replace('**', '').replace('*', '').strip()
            safe_title = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in title.lower())
            safe_title = '_'.join(safe_title.split())
            
            # Search for images in instagram_posts folder (newest first)
            from pathlib import Path
            base_path = Path('/home/biopoem/instagram_posts')
            
            # Search in last 30 days of folders
            found_images = {'dark': {}, 'light': {}}
            
            for year_dir in sorted(base_path.glob('*'), reverse=True):
                if not year_dir.is_dir():
                    continue
                for month_dir in sorted(year_dir.glob('*'), reverse=True):
                    if not month_dir.is_dir():
                        continue
                    for day_dir in sorted(month_dir.glob('*'), reverse=True):
                        if not day_dir.is_dir():
                            continue
                        for poem_dir in day_dir.glob('*'):
                            if not poem_dir.is_dir():
                                continue
                            
                            # Check if this folder matches our poem title
                            if safe_title in poem_dir.name or poem_dir.name in safe_title:
                                print(f"[DEBUG] Found poem folder: {poem_dir}")
                                
                                # Look for 28pt images
                                for mode in ['dark', 'light']:
                                    poem_img = list(poem_dir.glob(f'*_28pt_poem_*_{mode}.jpg'))
                                    footnote_img = list(poem_dir.glob(f'*_28pt_footnote_*_{mode}.jpg'))
                                    prompt_img = list(poem_dir.glob(f'*prompt*_{mode}.jpg'))
                                    
                                    if poem_img:
                                        found_images[mode]['poem'] = str(poem_img[0])
                                        print(f"[DEBUG] Found {mode} poem: {poem_img[0].name}")
                                    if footnote_img:
                                        found_images[mode]['footnote'] = str(footnote_img[0])
                                        print(f"[DEBUG] Found {mode} footnote: {footnote_img[0].name}")
                                    if prompt_img:
                                        found_images[mode]['prompt'] = str(prompt_img[0])
                                        print(f"[DEBUG] Found {mode} prompt: {prompt_img[0].name}")
                                
                                # If we found images, store them and stop searching
                                if found_images['dark'] or found_images['light']:
                                    self.poem_image_paths = found_images
                                    print(f"[DEBUG] Loaded image paths for existing poem")
                                    return
            
            print("[DEBUG] No rendered images found for this poem")
        except Exception as e:
            print(f"[DEBUG] Error discovering poem images: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_logging_quit_tap(self):
        """Handle rapid taps on LOGGING text - hidden quit mechanism (5 taps in 2 seconds)"""
        current_time = time.time()
        
        # If quit confirmation is already active, execute quit on next tap
        if self.quit_confirm_active:
            print("[DEBUG] Quit confirmed - exiting application")
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            return
        
        # Reset count if more than 2 seconds since last tap
        if self.led_quit_tap_start_time > 0 and (current_time - self.led_quit_tap_start_time) > 2.0:
            self.led_quit_tap_count = 0
        
        # Start or continue tap sequence
        self.led_quit_tap_start_time = current_time
        self.led_quit_tap_count += 1
        self.led_quit_flash_time = current_time  # Flash text for visual feedback
        
        print(f"[DEBUG] Logging quit tap {self.led_quit_tap_count}/5")
        
        if self.led_quit_tap_count >= 5:
            # Show quit confirmation
            self.quit_confirm_active = True
            self.quit_confirm_time = current_time
            self.led_quit_tap_count = 0
            self.needs_redraw = True
            print("[DEBUG] Quit confirmation activated - tap LOGGING again to quit")
    
    def _handle_generate_button(self):
        """Handle Generate button click"""
        if self.generation_in_progress:
            self.status = "Generation already in progress..."
            return
        
        # Check cooldown (1 minute minimum between generations)
        if hasattr(self, 'last_manual_generation_time'):
            elapsed = time.time() - self.last_manual_generation_time
            if elapsed < 60:
                remaining = int(60 - elapsed)
                self.status = f"Please wait {remaining}s before generating again"
                return
        
        self.last_manual_generation_time = time.time()
        self.generation_in_progress = True
        self.manual_generation_count += 1
        
        # Reset typing effect
        self.log_char_index = []
        
        # Hide UI during generation
        self.poem_ui_visible = False
        
        # Every 4th generation is visual
        force_visual = (self.manual_generation_count % 4 == 0)
        
        if force_visual:
            self.generation_progress_message = "Generating..."
            self.generation_log = ["> Starting visual poem generation"]
            print("[DEBUG] Generating visual poem (every 4th)")
        else:
            self.generation_progress_message = "Generating..."
            self.generation_log = ["> Starting poem generation"]
        
        self.status = self.generation_progress_message
        self.needs_redraw = True
        
        # Trigger generation in background thread
        import threading
        thread = threading.Thread(target=self._generate_poem_thread, args=(force_visual,))
        thread.daemon = True
        thread.start()
    
    def _generate_poem_thread(self, force_visual):
        """Background thread for poem generation"""
        try:
            self.generation_log.append("> Poetry engine: initializing...")
            self.generation_log.append("> Reading sensor data from CSV...")
            self.needs_redraw = True
            pygame.time.wait(100)  # Small delay to show message
            
            # Use the existing generation logic
            if not self.generating_poems and POETRY_AVAILABLE:
                self.screen_id = self.POEM
                self._enter_screen()
                self.generating_poems = True
                self.poem_generation_mode = "daily"
                
                if force_visual:
                    # Force visual poem generation (auto-select pattern)
                    self.force_visual_generation = True
                    self.selected_visual_pattern = None  # Auto-select
                else:
                    # Force standard poem
                    self.force_standard_generation = True
                
                # Run generation in current thread (already in background)
                self._generate_poems_thread()
            
            # Keep the log visible for 3 seconds after completion
            pygame.time.wait(3000)
            self.generation_progress_message = ""
            # Clear the log so poem will be shown
            self.generation_log = []
            self.generating_poems = False  # Reset flag so poem will display
            
            # Keep UI hidden when showing poem after generation
            self.poem_ui_visible = False
            
            self.status = f"Poem generated! (#{self.manual_generation_count})"
        except Exception as e:
            print(f"[DEBUG] Generation error: {e}")
            import traceback
            traceback.print_exc()
            self.generation_log.append(f"> Error: {str(e)[:40]}")
            pygame.time.wait(1000)
            self.generation_progress_message = ""
            # Don't clear the log on error
            # self.generation_log = []
            self.status = f"Generation failed: {e}"
        finally:
            self.generation_in_progress = False
            self.needs_redraw = True
    
    # ---------- Email list sync ----------
    def _sync_email_lists(self):
        """Sync email lists from Google Forms spreadsheet"""
        import subprocess
        
        # Run the sync script
        result = subprocess.run(
            ['python3', 'sync_email_list_v1.4.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"Sync failed: {result.stderr}")
        
        print(f"[DEBUG] Sync output: {result.stdout}")
    
    # ---------- Notion integration ----------
    def _send_admin_report(self, poem_text, poem_folder, prompt_data=None, poem_type="daily", 
                          gdrive_status=None, notion_status=None, api_time=None, errors=None):
        """Send admin report email with poem confirmation and images
        
        Args:
            poem_text: The complete poem text
            poem_folder: Path to instagram_posts folder with images
            prompt_data: Metadata from poetry engine
            poem_type: "daily" or "weekly"
            gdrive_status: Google Drive sync result
            notion_status: Notion upload result
            api_time: API response time in seconds
            errors: List of any errors/warnings
        """
        if not self.email_enabled:
            print("[DEBUG] Email not configured for admin report")
            return False
        
        try:
            admin_email = 'biopoem.daily@gmail.com'
            print(f"[DEBUG] Sending admin report to {admin_email}...")
            
            # Parse poem for title and count lines
            lines = poem_text.strip().split('\n')
            title = lines[0].strip() if lines else f"{'Weekly' if poem_type == 'weekly' else 'Daily'} Biopoem"
            
            # Count actual poem lines (exclude title and footnote)
            poem_lines = []
            in_footnote = False
            for line in lines[1:]:
                if '---' in line or 'Generated:' in line:
                    in_footnote = True
                if not in_footnote and line.strip():
                    poem_lines.append(line)
            poem_line_count = len(poem_lines)
            
            # Get current mode preference (alternates light/dark each generation)
            # Use generation count to alternate
            if hasattr(self, 'poem_logger') and self.poem_logger:
                gen_count = self.poem_logger.get_generation_count()
                current_mode = "light" if gen_count % 2 == 0 else "dark"
                total_generations = gen_count
            else:
                current_mode = "dark"
                total_generations = 0
            
            # Get full prompt if available
            full_prompt = ""
            if prompt_data:
                # prompt_data can have prompt at top level or nested in metadata
                if 'prompt' in prompt_data:
                    full_prompt = prompt_data['prompt']
                elif 'metadata' in prompt_data and 'prompt' in prompt_data['metadata']:
                    full_prompt = prompt_data['metadata']['prompt']
            
            if not full_prompt:
                print("[DEBUG] ⚠️  No full prompt found in prompt_data")
            else:
                print(f"[DEBUG] ✓ Full prompt included in email ({len(full_prompt)} chars)")
            
            # Build status indicators HTML
            status_html = """
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #2e7d32;">
                <h3 style="margin-top: 0; color: #2e7d32;">✅ Status Checks</h3>
                <table style="width: 100%; font-size: 13px;">
            """
            
            # Generation count
            status_html += f"<tr><td><strong>Total Generations:</strong></td><td>{total_generations}</td></tr>"
            
            # Poem length check
            length_check = "✅" if 6 <= poem_line_count <= 10 else "⚠️"
            status_html += f"<tr><td><strong>Poem Length:</strong></td><td>{length_check} {poem_line_count} lines (target: 6-10)</td></tr>"
            
            # Google Drive sync
            if gdrive_status is not None:
                gdrive_icon = "✅" if gdrive_status else "❌"
                status_html += f"<tr><td><strong>Google Drive Sync:</strong></td><td>{gdrive_icon} {'Success' if gdrive_status else 'Failed'}</td></tr>"
            
            # Notion upload
            if notion_status is not None:
                notion_icon = "✅" if notion_status else "❌"
                status_html += f"<tr><td><strong>Notion Upload:</strong></td><td>{notion_icon} {'Success' if notion_status else 'Failed'}</td></tr>"
            
            # API time
            if api_time:
                status_html += f"<tr><td><strong>API Response Time:</strong></td><td>{api_time:.1f}s</td></tr>"
            
            # Check if visual pattern
            visual_pattern = None
            if prompt_data and 'metadata' in prompt_data:
                visual_pattern = prompt_data['metadata'].get('visual_pattern')
                if visual_pattern:
                    status_html += f"<tr><td><strong>Visual Pattern:</strong></td><td>{visual_pattern}</td></tr>"
            
            # Image files check
            image_count = 0
            if os.path.exists(poem_folder):
                image_count = len([f for f in os.listdir(poem_folder) if f.endswith('.jpg')])
            image_check = "✅" if image_count >= 16 else "⚠️"
            status_html += f"<tr><td><strong>Image Files:</strong></td><td>{image_check} {image_count} files (expected: 16+)</td></tr>"
            
            status_html += "</table></div>"
            
            # Errors/warnings section
            errors_html = ""
            if errors and len(errors) > 0:
                errors_html = """
                <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ff9800;">
                    <h3 style="margin-top: 0; color: #e65100;">⚠️ Warnings</h3>
                    <ul style="font-size: 13px; margin: 5px 0; padding-left: 20px;">
                """
                for error in errors:
                    errors_html += f"<li>{error}</li>"
                errors_html += "</ul></div>"
            
            # Create email
            from email.mime.image import MIMEImage
            msg = MIMEMultipart('related')
            msg['From'] = self.smtp_email
            msg['To'] = admin_email
            msg['Subject'] = f"✅ Biopoem Generated: {title}"
            
            # Build metadata summary
            metadata_html = ""
            if prompt_data:
                theme_name = prompt_data.get('theme_name', 'Unknown')
                theme_score = prompt_data.get('theme_score', 0)
                influence = prompt_data.get('influence_name', 'Unknown')
                sensor_data = prompt_data.get('sensor_summary', {})
                
                voltage_avg = sensor_data.get('voltage', {}).get('avg_24h', 0)
                moisture_current = sensor_data.get('moisture', {}).get('current', 0)
                temp_current = sensor_data.get('temperature', {}).get('current', 0)
                light_avg = sensor_data.get('light', {}).get('avg_24h', 0)
                
                # Get repetition warnings if available
                repetition_info = ""
                if 'repetition_warnings' in prompt_data:
                    warnings = prompt_data['repetition_warnings']
                    if warnings:
                        repetition_info = f"<tr><td colspan='2'><strong>Avoided phrases:</strong> {', '.join(warnings[:5])}</td></tr>"
                
                metadata_html = f"""
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #555;">Generation Metadata</h3>
                    <table style="width: 100%; font-size: 13px;">
                        <tr><td><strong>Theme:</strong></td><td>{theme_name} (score: {theme_score:.2f})</td></tr>
                        <tr><td><strong>Influence:</strong></td><td>{influence}</td></tr>
                        <tr><td><strong>Voltage (24h avg):</strong></td><td>{voltage_avg:.3f}V</td></tr>
                        <tr><td><strong>Moisture:</strong></td><td>{moisture_current:.1f}%</td></tr>
                        <tr><td><strong>Temperature:</strong></td><td>{temp_current:.1f}°C</td></tr>
                        <tr><td><strong>Light (24h avg):</strong></td><td>{light_avg:.1f} lux</td></tr>
                        {repetition_info}
                    </table>
                </div>
                """
            
            # Build Instagram caption preview
            caption_preview = ""
            caption_file = os.path.join(poem_folder, 'caption.txt')
            if os.path.exists(caption_file):
                try:
                    with open(caption_file, 'r', encoding='utf-8') as f:
                        caption_text = f.read()[:500]  # First 500 chars
                    caption_preview = f"""
                    <div style="background-color: #f3e5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #6a1b9a;">📱 Instagram Caption Preview</h3>
                        <pre style="white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.4; color: #333;">{caption_text}...</pre>
                    </div>
                    """
                except:
                    pass
            
            # Build full prompt section (collapsible details)
            prompt_html = ""
            if full_prompt:
                # Escape HTML in prompt
                prompt_escaped = full_prompt.replace('<', '&lt;').replace('>', '&gt;')
                prompt_html = f"""
                <details style="margin: 20px 0;">
                    <summary style="cursor: pointer; font-weight: bold; color: #1976d2; padding: 10px; background-color: #e3f2fd; border-radius: 5px;">
                        📝 View Full Prompt (Click to expand)
                    </summary>
                    <div style="background-color: #fafafa; padding: 15px; border-radius: 5px; margin-top: 10px; border: 1px solid #ddd;">
                        <pre style="white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 11px; line-height: 1.4; max-height: 600px; overflow-y: auto;">{prompt_escaped}</pre>
                    </div>
                </details>
                """
            
            # Build HTML body
            html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h2 style="color: #2e7d32; margin-top: 0;">✅ Poem Generated Successfully</h2>
        <p style="color: #666; font-size: 14px;">
            <strong>Type:</strong> {poem_type.capitalize()}<br>
            <strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>
            <strong>Folder:</strong> <code>{poem_folder}</code><br>
            <strong>Image Mode:</strong> {current_mode.capitalize()} (alternates each generation)
        </p>
        
        {status_html}
        {errors_html}
        {metadata_html}
        
        <div style="background-color: #f0f0f0; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Poem Text ({poem_line_count} lines):</h3>
            <pre style="white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.6;">{poem_text}</pre>
        </div>
        
        {caption_preview}
        
        <h3>Instagram Images (28pt, {current_mode} mode):</h3>
        <div style="margin: 20px 0;">
            <p style="font-size: 13px; color: #666;">Poem:</p>
            <img src="cid:poem_image" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;" />
        </div>
        <div style="margin: 20px 0;">
            <p style="font-size: 13px; color: #666;">Footnote:</p>
            <img src="cid:footnote_image" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;" />
        </div>
        
        {prompt_html}
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        <p style="color: #888; font-size: 12px; text-align: center;">
            Biopoem V2.0 Admin Report
        </p>
    </div>
</body>
</html>
"""
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach images - extract date from folder name for new naming convention
            # Folder format: YYYYMMDD_title or YYYYMMDD_title_visual
            folder_name = os.path.basename(poem_folder)
            date_str = folder_name[:8] if len(folder_name) >= 8 else datetime.now().strftime('%Y%m%d')
            
            # Get title from prompt_data or folder name
            title = "poem"
            if prompt_data and 'title' in prompt_data:
                title = prompt_data['title'].lower().replace(' ', '_')
            elif '_' in folder_name:
                # Extract from folder name (remove date and _visual suffix)
                title = folder_name[9:].replace('_visual', '')
            
            # New naming convention: YYYYMMDD_XXpt_poem_title_mode.jpg
            poem_image_path = os.path.join(poem_folder, f'{date_str}_28pt_poem_{title}_{current_mode}.jpg')
            footnote_image_path = os.path.join(poem_folder, f'{date_str}_28pt_footnote_{title}_{current_mode}.jpg')
            
            if os.path.exists(poem_image_path):
                with open(poem_image_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<poem_image>')
                    msg.attach(img)
            else:
                print(f"[DEBUG] ⚠️  Poem image not found: {poem_image_path}")
            
            if os.path.exists(footnote_image_path):
                with open(footnote_image_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<footnote_image>')
                    msg.attach(img)
            else:
                print(f"[DEBUG] ⚠️  Footnote image not found: {footnote_image_path}")
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(msg)
            
            print(f"[DEBUG] ✅ Admin report sent to {admin_email}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] ❌ Admin report failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    

    
    def _upload_to_notion(self, poem_text, prompt_data=None, poem_type="daily"):
        """Upload poem to Notion database with split blocks (poem + footnotes) and metadata
        
        Args:
            poem_text: The complete poem text with title and footnotes
            prompt_data: Metadata dict from poetry engine
            poem_type: "daily" or "weekly"
        """
        if not self.notion_client or not self.notion_db_id:
            print("[DEBUG] Notion not configured - check .env file")
            print(f"[DEBUG]   notion_client exists: {self.notion_client is not None}")
            print(f"[DEBUG]   notion_db_id exists: {self.notion_db_id is not None}")
            return False
        
        try:
            print(f"[DEBUG] Starting Notion upload... (poem length: {len(poem_text)})")
            
            # Parse poem into title, body, and footnotes
            lines = poem_text.strip().split('\n')
            if not lines:
                print("[DEBUG] Empty poem text")
                return False
            
            # First line is title
            title = lines[0].strip()
            print(f"[DEBUG] Title: {title}")
            
            # Find separator line (should be ~80% dashes or em-dashes)
            separator_idx = None
            for i, line in enumerate(lines[1:], start=1):
                stripped = line.strip()
                if len(stripped) > 20:  # Reasonable separator length
                    # Count dashes (both regular and em-dashes)
                    dash_count = stripped.count('-') + stripped.count('\u2014')
                    if dash_count / len(stripped) > 0.8:
                        separator_idx = i
                        print(f"[DEBUG] Separator found at line {i}")
                        break
            
            if separator_idx is None:
                print("[DEBUG] No separator found, treating entire poem as body")
                poem_body = '\n'.join(lines[1:])
                footnote_text = ""
            else:
                # Split at separator
                poem_body = '\n'.join(lines[1:separator_idx])
                footnote_text = '\n'.join(lines[separator_idx+1:])
            
            print(f"[DEBUG] Poem body: {len(poem_body)} chars")
            print(f"[DEBUG] Footnote: {len(footnote_text)} chars")
            
            # Build Notion page content blocks
            children = []
            
            # Add poem as code block with BOLD ITALIC title
            if poem_body.strip():
                # Clean em-dashes from poem body
                clean_poem = poem_body.replace('—', '-')
                
                # Create rich text array: [bold italic title, newline, poem text]
                poem_rich_text = [
                    {
                        "type": "text",
                        "text": {"content": title},
                        "annotations": {
                            "bold": True,
                            "italic": True,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        }
                    },
                    {
                        "type": "text",
                        "text": {"content": "\n" + clean_poem.strip()}
                    }
                ]
                
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": poem_rich_text,
                        "language": "plain text"
                    }
                })
            
            # Add 1 blank line between poem and footnotes
            if footnote_text.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": ""}}]
                    }
                })
                
                # Parse footnote and create rich text with bold labels
                clean_footnote = footnote_text.replace('—', '-')
                footnote_lines = clean_footnote.strip().split('\n')
                footnote_rich_text = []
                
                # Labels that should be bold (and bold italic for title)
                bold_labels = ['Generated:', 'Observation period:', 'Light exp:', 'Theme:', 'Title:', 
                              'Sensor readings:', 'V:', 'Moisture:', 'Temp:', 'Light:', 'Loc:', 
                              'Patterns:', 'Influence:', 'Human:']
                
                for i, line in enumerate(footnote_lines):
                    line = line.strip()
                    if not line:
                        footnote_rich_text.append({"type": "text", "text": {"content": "\n"}})
                        continue
                    
                    # Check if line starts with a bold label
                    matched_label = None
                    for label in bold_labels:
                        if line.startswith(label):
                            matched_label = label
                            break
                    
                    if matched_label:
                        # Split into label and content
                        remaining = line[len(matched_label):]
                        
                        # Add label in bold (and italic if it's Title:)
                        if matched_label == 'Title:':
                            footnote_rich_text.append({
                                "type": "text",
                                "text": {"content": matched_label},
                                "annotations": {"bold": True, "italic": False}
                            })
                            # Title content should be bold italic
                            if remaining:
                                footnote_rich_text.append({
                                    "type": "text",
                                    "text": {"content": remaining},
                                    "annotations": {"bold": True, "italic": True}
                                })
                        else:
                            footnote_rich_text.append({
                                "type": "text",
                                "text": {"content": matched_label},
                                "annotations": {"bold": True}
                            })
                            # Add remaining content normally
                            if remaining:
                                footnote_rich_text.append({
                                    "type": "text",
                                    "text": {"content": remaining}
                                })
                    else:
                        # Regular line (no bold label) - could be pattern items or continuation
                        footnote_rich_text.append({
                            "type": "text",
                            "text": {"content": line}
                        })
                    
                    # Add newline after each line except the last
                    if i < len(footnote_lines) - 1:
                        footnote_rich_text.append({"type": "text", "text": {"content": "\n"}})
                
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": footnote_rich_text,
                        "language": "plain text"
                    }
                })
            
            print(f"[DEBUG] Created {len(children)} blocks")
            
            # Extract metadata from prompt_data if available
            metadata = {}
            if prompt_data:
                meta = prompt_data.get('metadata', {})
                sensor_summary = prompt_data.get('sensor_summary', {})
                
                # Extract time_period and season from sensor readings text or calculate them
                time_period = ''
                season = ''
                sensor_readings = meta.get('sensor_readings', {})
                
                # Try to extract from voltage string (format: "1.489V (today avg: 1.486V)")
                voltage_str = sensor_readings.get('voltage', '')
                if isinstance(voltage_str, str) and 'today avg:' in voltage_str:
                    # Parse voltage from string
                    voltage = float(voltage_str.split('V')[0])
                else:
                    voltage = sensor_summary.get('voltage', {}).get('current', None)
                
                # Similar for other sensors
                moisture_str = sensor_readings.get('moisture', '')
                if isinstance(moisture_str, str) and 'today avg:' in moisture_str:
                    moisture = float(moisture_str.split('%')[0])
                else:
                    moisture = sensor_summary.get('moisture', {}).get('current', None)
                
                temp_str = sensor_readings.get('temperature', '')  
                if isinstance(temp_str, str) and 'today avg:' in temp_str:
                    temperature = float(temp_str.split('C')[0])
                else:
                    temperature = sensor_summary.get('temperature', {}).get('current', None)
                
                light_str = sensor_readings.get('light', '')
                if isinstance(light_str, str) and 'lux' in light_str:
                    light = float(light_str.split(' lux')[0])
                else:
                    light = sensor_summary.get('light', {}).get('current', None)
                
                # Get time and season from metadata or calculate from current time
                time_period = meta.get('time_period', '')
                season = meta.get('season', '')
                
                # If not in metadata, try to derive from current time
                if not time_period:
                    hour = datetime.now().hour
                    if 5 <= hour < 12:
                        time_period = "morning"
                    elif 12 <= hour < 17:
                        time_period = "afternoon"
                    elif 17 <= hour < 21:
                        time_period = "evening"
                    else:
                        time_period = "night"
                
                if not season:
                    month = datetime.now().month
                    if month in [12, 1, 2]:
                        season = "winter"
                    elif month in [3, 4, 5]:
                        season = "spring"
                    elif month in [6, 7, 8]:
                        season = "summer"
                    else:
                        season = "fall"
                
                metadata = {
                    'theme': meta.get('primary_theme', ''),
                    'influence': meta.get('influence_name', ''),
                    'moisture': moisture,
                    'voltage': voltage,
                    'temperature': temperature,
                    'light': light,
                    'location': meta.get('location', ''),
                    'time_period': time_period,
                    'season': season
                }
                print(f"[DEBUG] Metadata extracted: theme={metadata['theme']}, influence={metadata['influence']}, moisture={metadata['moisture']}, location={metadata['location']}, time={time_period}, season={season}")
            else:
                print("[DEBUG] ⚠️  No prompt_data available - this poem was generated before metadata persistence was added")
                print("[DEBUG]     Only Name, Date, and Version will be uploaded to Notion")
                print("[DEBUG]     Generate a new poem (G key) to get full metadata support!")
            
            # Build properties for Notion page
            properties = {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "Date": {
                    "date": {
                        "start": datetime.now().strftime("%Y-%m-%d")
                    }
                },
                "Version": {
                    "rich_text": [
                        {
                            "text": {
                                "content": APP_VERSION
                            }
                        }
                    ]
                }
            }
            
            # Add optional properties if data exists
            # Helper to check for valid float (not NaN, Inf, or None)
            import math
            def is_valid_number(val):
                if val is None:
                    return False
                try:
                    f = float(val)
                    return not (math.isnan(f) or math.isinf(f))
                except (ValueError, TypeError):
                    return False
            
            if metadata.get('theme'):
                properties["Theme"] = {
                    "rich_text": [{"text": {"content": metadata['theme']}}]
                }
            
            if metadata.get('influence'):
                properties["Influence"] = {
                    "rich_text": [{"text": {"content": metadata['influence']}}]
                }
            
            if is_valid_number(metadata.get('moisture')):
                properties["Moisture"] = {
                    "number": float(metadata['moisture'])
                }
            
            if is_valid_number(metadata.get('voltage')):
                properties["Voltage"] = {
                    "number": round(float(metadata['voltage']), 3)
                }
            
            if is_valid_number(metadata.get('temperature')):
                properties["Temperature"] = {
                    "number": round(float(metadata['temperature']), 1)
                }
            
            if is_valid_number(metadata.get('light')):
                properties["Light"] = {
                    "number": round(float(metadata['light']), 1)
                }
            
            if metadata.get('location'):
                properties["Location"] = {
                    "rich_text": [{"text": {"content": metadata['location']}}]
                }
            
            if metadata.get('time_period'):
                properties["Time"] = {
                    "rich_text": [{"text": {"content": metadata['time_period']}}]
                }
            
            if metadata.get('season'):
                properties["Season"] = {
                    "rich_text": [{"text": {"content": metadata['season']}}]
                }
            
            # Add poem type (daily or weekly)
            properties["Type"] = {
                "select": {"name": poem_type.capitalize()}
            }
            
            # Create page in Notion database
            print("[DEBUG] Calling Notion API...")
            response = self.notion_client.pages.create(
                parent={"database_id": self.notion_db_id},
                properties=properties,
                children=children
            )
            
            page_id = response.get('id', 'unknown')
            print(f"[DEBUG] ✅ Uploaded to Notion! Page ID: {page_id}")
            
            # Also update the latest poem display page
            self._update_latest_poem_display(poem_text, poem_type)
            
            return True
            
        except Exception as e:
            print(f"[DEBUG] ❌ Notion upload failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _update_latest_poem_display(self, poem_text, poem_type="daily"):
        """Update the specific synced code block in Notion
        
        Args:
            poem_text: The complete poem text
            poem_type: "daily" or "weekly"
        """
        if not self.notion_client:
            return
        
        # Specific code block ID (extracted from your URL)
        code_block_id = "2b511153c42c81eb8fa2e625a2c74510"
        
        try:
            print("[DEBUG] Updating synced code block...")
            
            # Parse poem to get title (first line) 
            lines = poem_text.strip().split('\n')
            title = lines[0].strip() if lines else ""
            poem_body = '\n'.join(lines[1:]) if len(lines) > 1 else ""
            
            # Update the specific code block directly
            self.notion_client.blocks.update(
                block_id=code_block_id,
                code={
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": title},
                            "annotations": {"bold": True}
                        },
                        {
                            "type": "text",
                            "text": {"content": "\n\n" + poem_body[:1950]}
                        }
                    ],
                    "language": "plain text"
                }
            )
            print("[DEBUG] Updated synced code block")
            
            print("[DEBUG] ✅ Latest poem display page updated!")
            
        except Exception as e:
            print(f"[DEBUG] Failed to update latest poem display: {e}")
    
    def _check_auto_generation(self):
        """Check if it's time for automatic poem generation (8pm daily, 8am Sunday weekly)"""
        if self.checking_auto_gen or self.generating_poems:
            return
        
        now = datetime.now()
        current_date = now.date()
        current_hour = now.hour
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        
        # Debug: Log once per hour to track generation checks
        if not hasattr(self, '_last_debug_hour') or self._last_debug_hour != current_hour:
            self._last_debug_hour = current_hour
            if current_hour == 20 or current_hour == 8:  # Only log at trigger hours
                print(f"[AUTO-GEN DEBUG] {now.strftime('%Y-%m-%d %H:%M')} | Hour: {current_hour} | Last gen date: {self.last_auto_gen_date} | Current date: {current_date}")
        
        # Check for Sunday 8am weekly generation
        if current_day == 6 and current_hour == 8:  # Sunday at 8am
            if not hasattr(self, 'last_weekly_gen_date') or self.last_weekly_gen_date != current_date:
                print(f"[DEBUG] 🌅 WEEKLY auto-generation triggered at {now.strftime('%H:%M:%S on %A')}")
                self.last_weekly_gen_date = current_date
                self.checking_auto_gen = True
                self.poem_generation_mode = "weekly"
                
                # Switch to poem screen and start generation
                self.screen_id = self.POEM
                self._enter_screen()
                self.generating_poems = True
                
                # Start generation thread
                self.generation_thread = threading.Thread(
                    target=self._auto_generate_and_upload,
                    daemon=True
                )
                self.generation_thread.start()
                return
        
        # Check for daily 8pm generation
        if current_hour == self.auto_gen_hour and self.last_auto_gen_date != current_date:
            # Only generate if app has been running for 5+ minutes (prevents startup generation)
            if hasattr(self, '_app_started_at'):
                import time
                uptime = time.time() - self._app_started_at
                if uptime < 300:  # Less than 5 minutes
                    print(f"[DEBUG] Skipping auto-gen (app just started {uptime:.0f}s ago)")
                    return
            
            print(f"[DEBUG] 🌙 DAILY auto-generation triggered at {now.strftime('%H:%M:%S')}")
            self.last_auto_gen_date = current_date
            self.checking_auto_gen = True
            self.poem_generation_mode = "daily"
            
            # Switch to poem screen and start generation
            self.screen_id = self.POEM
            self._enter_screen()
            self.generating_poems = True
            
            # Start generation thread
            self.generation_thread = threading.Thread(
                target=self._auto_generate_and_upload,
                daemon=True
            )
            self.generation_thread.start()
    
    def _auto_generate_and_upload(self):
        """Background thread for automatic poem generation (8pm daily OR 8am Sunday weekly)"""
        mode = getattr(self, 'poem_generation_mode', 'daily')
        print(f"[DEBUG] Auto-generation thread started! Mode: {mode}")
        
        # Update UI with terminal-style log
        self.generation_progress_message = "Generating..."
        if mode == 'weekly':
            self.generation_log = ["▸ Starting weekly poem (8am Sunday)"]
        else:
            self.generation_log = ["▸ Starting daily poem (8pm)"]
        self.needs_redraw = True
        
        # Start LED pulsation during generation
        try:
            self.sensors.start_poem_pulsation()
            self.generation_log.append("▸ LED indicator started")
            self.needs_redraw = True
            print("[DEBUG] LED pulsation started (auto-gen)")
        except Exception as e:
            print(f"[DEBUG] LED pulsation failed to start: {e}")
        
        try:
            # Generate poem
            self.generation_log.append("Reading sensor data from CSV...")
            self.needs_redraw = True
            pygame.time.wait(200)  # Allow UI to update
            
            gen = DailyPoetryGenerator(CSV_PATH)
            
            if mode == "weekly":
                self.generation_log.append("Analyzing 7-day data window...")
                self.needs_redraw = True
                pygame.time.wait(200)
                print("[DEBUG] Generating WEEKLY poem...")
                prompt_data = gen.generate_weekly_poem_prompt()
            else:
                self.generation_log.append("Analyzing 24-hour data window...")
                self.needs_redraw = True
                pygame.time.wait(200)
                print("[DEBUG] Generating DAILY poem...")
                prompt_data = gen.generate_daily_poem_prompt()
            
            # Extract and show sensor data
            metadata = prompt_data.get('metadata', {})
            sensor_summary = prompt_data.get('sensor_summary', {})
            
            self.generation_log.append("")
            self.generation_log.append("Sensor readings:")
            if 'moisture_pct' in sensor_summary:
                moisture = sensor_summary['moisture_pct']
                self.generation_log.append(f"  Moisture: {moisture:.1f}%")
            if 'temp_C' in sensor_summary:
                temp = sensor_summary['temp_C']
                self.generation_log.append(f"  Temperature: {temp:.1f}°C")
            if 'lux_lx' in sensor_summary:
                lux = sensor_summary['lux_lx']
                self.generation_log.append(f"  Light: {lux:.0f} lux")
            self.needs_redraw = True
            pygame.time.wait(300)  # Let user see sensor data
            
            # Show theme and poet selection
            self.generation_log.append("")
            theme = metadata.get('primary_theme', 'unknown')
            theme_score = metadata.get('theme_score', 0)
            poet = metadata.get('poet', 'unknown')
            influence = metadata.get('influence', 'unknown')
            
            self.generation_log.append(f"Theme: {theme} (score: {theme_score:.2f})")
            self.generation_log.append(f"Poet: {poet}")
            self.generation_log.append(f"Style: {influence}")
            self.needs_redraw = True
            pygame.time.wait(300)  # Let user see theme selection
            
            prompt = prompt_data['prompt'] if isinstance(prompt_data, dict) else prompt_data
            
            # Show prompt stats
            self.generation_log.append("")
            prompt_length = len(prompt)
            self.generation_log.append(f"Prompt: {prompt_length} characters")
            self.generation_log.append("")
            self.generation_log.append("Sending to Claude API...")
            self.generation_log.append("(this may take 5-15 seconds)")
            self.needs_redraw = True
            pygame.time.wait(300)  # Let user see we're about to call API
            
            import time
            start_time = time.time()
            client = PoemAPIClient("anthropic")
            claude_result = client.generate_poem(prompt)
            elapsed = time.time() - start_time
            
            if claude_result.get('success'):
                raw_poem = claude_result.get('poem')
                poem_lines = len(raw_poem.split('\n'))
                poem_chars = len(raw_poem)
                
                self.generation_log.append("")
                self.generation_log.append(f"✓ Response received in {elapsed:.1f}s")
                self.generation_log.append(f"  Poem: {poem_lines} lines, {poem_chars} chars")
                self.generation_log.append("")
                self.generation_log.append("Extracting poem from response...")
                self.needs_redraw = True
                pygame.time.wait(200)
                self.needs_redraw = True
                self.needs_redraw = True
                raw_poem = claude_result.get('poem')
                self.poem_prompt_data = prompt_data  # Store for retroactive uploads
                poem_type = prompt_data.get('poem_type', 'daily')
                print(f"[DEBUG] Auto-generation successful! Type: {poem_type}")
                
                # Build structured footnote and append prompt for screen display
                try:
                    metadata = prompt_data.get('metadata', {})
                    sensor_summary = prompt_data.get('sensor_summary', {})
                    
                    # Extract clean poem (without any AI-generated footnote)
                    poem_lines = raw_poem.split('\n')
                    clean_lines = []
                    for line in poem_lines:
                        stripped = line.strip()
                        if stripped.startswith('---') or stripped.startswith('*Biopoem') or 'Generated:' in stripped:
                            break
                        # Strip markdown formatting (asterisks for bold/italic)
                        cleaned_line = line.replace('**', '').replace('*', '')
                        clean_lines.append(cleaned_line)
                    clean_poem = '\n'.join(clean_lines).strip()
                    title = clean_lines[0].strip() if clean_lines else "untitled"
                    
                    gen_date = metadata.get('generation_date')
                    if isinstance(gen_date, str):
                        try:
                            gen_date = datetime.fromisoformat(gen_date)
                        except:
                            gen_date = datetime.now()
                    elif gen_date is None:
                        gen_date = datetime.now()
                    
                    footnote_args = {
                        'date': gen_date,
                        'theme_analysis': {
                            'primary_theme': metadata.get('primary_theme'),
                            'primary_score': metadata.get('theme_score', 0.0),
                            'title': title,
                            'visual_pattern': metadata.get('visual_pattern', 'standard')
                        },
                        'influence_key': metadata.get('influence'),
                        'sensor_summary': sensor_summary,
                        'human_context': None,
                        'location_context': {'current': metadata.get('location', 'office')},
                        'multi_day_patterns': metadata.get('multi_day_patterns', [])
                    }
                    
                    structured_footnote = gen._build_footnote(**footnote_args)
                    full_prompt = prompt_data.get('prompt', '')
                    
                    separator = '————————————————————————————————————————'
                    prompt_separator = '════════════════ FULL PROMPT ════════════════'
                    
                    # Add many blank lines so footnote is only visible after scrolling down
                    scroll_padding = '\n' * 30
                    
                    # Version for rendering/saving (NO prompt - just poem + footnote)
                    self.poem_for_render = clean_poem + '\n\n' + separator + '\n' + structured_footnote
                    
                    # Version for screen 3 display (includes prompt after scrolling)
                    self.poem_claude = clean_poem + scroll_padding + separator + '\n' + structured_footnote
                    if full_prompt:
                        self.poem_claude += '\n\n' + prompt_separator + '\n\n' + full_prompt
                    
                    self.generation_log.append("Building footnote...")
                    self.needs_redraw = True
                    pygame.time.wait(150)
                    print(f"[DEBUG] ✓ Auto-gen: Added structured footnote and prompt")
                except Exception as e:
                    print(f"[DEBUG] Auto-gen: Failed to build footnote: {e}")
                    self.poem_claude = raw_poem
                
                # Record poem for diversity tracking
                self.generation_log.append("Recording to diversity tracker...")
                self.needs_redraw = True
                pygame.time.wait(150)
                try:
                    metadata = prompt_data.get('metadata', {})
                    gen.record_generated_poem(
                        poem_text=self.poem_claude,
                        theme=metadata.get('primary_theme', 'unknown'),
                        influence=metadata.get('influence', 'unknown'),
                        generation_date=metadata.get('generation_date')
                    )
                except Exception as e:
                    print(f"[DEBUG] Diversity tracking failed: {e}")
                
                # Render Instagram images
                self.generation_log.append("")
                self.generation_log.append("> Rendering poem...")
                self.needs_redraw = True
                pygame.time.wait(200)
                print("[DEBUG] Auto-gen: Rendering Instagram images...")
                poem_folder_path = None
                try:
                    renderer = InstagramRenderer(output_dir="instagram_posts")
                    metadata = prompt_data.get('metadata', {})
                    
                    # Determine dark mode (alternating)
                    dark_mode = not self.last_generation_dark_mode
                    self.last_generation_dark_mode = dark_mode
                    
                    # Check if visual poem
                    is_visual = metadata.get('visual_pattern') and metadata.get('visual_pattern') != 'standard'
                    
                    # Use clean version without full prompt
                    text_to_render = self.poem_for_render if self.poem_for_render else self.poem_claude
                    has_prompt_separator = '════════════════ FULL PROMPT' in text_to_render
                    print(f"[DEBUG] Auto-gen: Rendering with poem_for_render={bool(self.poem_for_render)}, has_prompt_in_text={has_prompt_separator}")
                    
                    if is_visual:
                        visual_pattern = metadata.get('visual_pattern')
                        print(f"[DEBUG] Rendering VISUAL poem with pattern: {visual_pattern}")
                        images = renderer.render_visual_poem(
                            poem_text=text_to_render,
                            layout_type=visual_pattern,
                            dark_mode=dark_mode,
                            metadata=metadata
                        )
                    else:
                        print("[DEBUG] Rendering NORMAL poem (left-aligned)")
                        images = renderer.render_normal_poem(
                            poem_text=text_to_render,
                            metadata=metadata,
                            dark_mode=dark_mode
                        )
                    
                    # Get the actual folder path from renderer
                    poem_folder_path = renderer.output_dir
                    self.generation_log.append("  ✓ Images saved")
                    self.needs_redraw = True
                    print(f"[DEBUG] ✓ Rendered {len(images) if isinstance(images, list) else 'dict'} images to: {poem_folder_path}")
                    
                    # Store image paths for carousel display
                    # images can be dict with 'dark'/'light' keys, or list (legacy)
                    if isinstance(images, dict):
                        # New format: {'dark': [poem, footnote], 'light': [poem, footnote]}
                        for mode in ['dark', 'light']:
                            if mode in images and images[mode]:
                                self.poem_image_paths[mode] = {}
                                for img_path in images[mode]:
                                    if 'footnote' in os.path.basename(img_path):
                                        self.poem_image_paths[mode]['footnote'] = img_path
                                    elif 'poem' in os.path.basename(img_path):
                                        self.poem_image_paths[mode]['poem'] = img_path
                                print(f"[DEBUG] Stored {mode} image paths: {self.poem_image_paths[mode]}")
                    else:
                        # Legacy format: list of image paths
                        mode = 'dark' if dark_mode else 'light'
                        self.poem_image_paths[mode] = {}
                        for img_path in images:
                            if 'footnote' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['footnote'] = img_path
                            elif 'poem' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['poem'] = img_path
                        print(f"[DEBUG] Stored {mode} image paths: {self.poem_image_paths[mode]}")
                    
                    # Render the creative prompt to same poem folder
                    try:
                        full_prompt = prompt_data.get('prompt', '')
                        if full_prompt:
                            creative_brief = InstagramRenderer.extract_creative_brief(full_prompt)
                            if creative_brief:
                                # Clean prompt: remove CRITICAL section
                                clean_lines = []
                                for line in creative_brief.split('\n'):
                                    if line.strip().startswith('CRITICAL:'):
                                        break
                                    clean_lines.append(line)
                                clean_prompt = '\n'.join(clean_lines).strip()
                                
                                title = self.poem_claude.split('\n')[0].strip().replace('**', '').replace('*', '') if self.poem_claude else 'prompt'
                                prompt_paths = renderer.render_prompt_both_modes(clean_prompt, output_dir=poem_folder_path, title=title)
                                print(f"[DEBUG] ✓ Rendered prompt images: {prompt_paths}")
                                # Store prompt paths
                                if prompt_paths:
                                    for path in prompt_paths:
                                        if '_dark' in path:
                                            if 'dark' not in self.poem_image_paths:
                                                self.poem_image_paths['dark'] = {}
                                            self.poem_image_paths['dark']['prompt'] = path
                                        else:
                                            if 'light' not in self.poem_image_paths:
                                                self.poem_image_paths['light'] = {}
                                            self.poem_image_paths['light']['prompt'] = path
                    except Exception as e:
                        print(f"[DEBUG] Prompt rendering failed: {e}")
                        
                except Exception as e:
                    print(f"[DEBUG] Instagram rendering failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Clear image cache so new images will be loaded
                self.poem_images_loaded = {}
                print("[DEBUG] Cleared image cache for new poem")
                
                # Clear image cache so new images will be loaded
                self.poem_images_loaded = {}
                print("[DEBUG] Cleared image cache for new poem")
                
                # Save to file
                self._save_latest_poem()
                
                # Update web gallery with latest folder
                latest_folder = os.path.basename(poem_folder_path) if 'poem_folder_path' in locals() else None
                self._update_gallery(latest_poem_folder=latest_folder)
                
                # Log to CSV with all generation data
                if self.poem_logger:
                    try:
                        self.poem_logger.log_generation(
                            poem_text=self.poem_claude,
                            prompt_data=prompt_data,
                            api_result=claude_result
                        )
                        count = self.poem_logger.get_generation_count()
                        print(f"[DEBUG] Logged to CSV - Total generations: {count}")
                    except Exception as e:
                        print(f"[DEBUG] CSV logging failed: {e}")
                
                # Upload to Notion
                self.generation_log.append("")
                self.generation_log.append("Uploading to Notion database...")
                self.needs_redraw = True
                print(f"[DEBUG] Auto-gen: Starting Notion upload ({poem_type})...")
                api_time = claude_result.get('time_elapsed', 0)
                upload_success = self._upload_to_notion(self.poem_claude, prompt_data=prompt_data, poem_type=poem_type)
                if upload_success:
                    self.status = f"Auto-gen: {poem_type.capitalize()} poem uploaded ✅"
                    self.generation_log.append("Notion upload: success")
                    self.needs_redraw = True
                    print(f"[DEBUG] ✅ Auto-upload to Notion successful ({poem_type})")
                else:
                    self.status = f"Auto-gen: Upload failed ❌"
                    self.generation_log.append("Notion upload: failed")
                    self.needs_redraw = True
                    print("[DEBUG] ❌ Auto-upload to Notion failed")
                
                # Show completion briefly then clear
                pygame.time.wait(2000)
                self.generation_progress_message = ""
                # Don't clear log - keep it visible
                # self.generation_log = []
                
                # Google Drive sync
                self.generation_log.append("")
                self.generation_log.append("Syncing to Google Drive...")
                self.needs_redraw = True
                print(f"[DEBUG] Auto-gen: Syncing to Google Drive...")
                gdrive_success = False
                if poem_folder_path:
                    try:
                        # Get relative path from instagram_posts base
                        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instagram_posts')
                        if poem_folder_path.startswith(base_dir):
                            relative_path = poem_folder_path[len(base_dir):].lstrip(os.sep)
                        else:
                            relative_path = os.path.basename(poem_folder_path)
                        
                        # Run gdrive sync preserving month/day structure
                        result = subprocess.run(
                            ['rclone', 'sync', poem_folder_path, f'gdrive:biopoem_instagram/{relative_path}', '-v'],
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        gdrive_success = (result.returncode == 0)
                        if gdrive_success:
                            self.generation_log.append("  ✓ Drive sync complete")
                            self.needs_redraw = True
                            print(f"[DEBUG] ✅ Google Drive sync successful: {relative_path}")
                        else:
                            self.generation_log.append("  ✗ Drive sync failed")
                            self.needs_redraw = True
                            print(f"[DEBUG] ❌ Google Drive sync failed: {result.stderr}")
                    except Exception as e:
                        self.generation_log.append("  ✗ Drive sync error")
                        self.needs_redraw = True
                        print(f"[DEBUG] ❌ Google Drive sync error: {e}")
                        gdrive_success = False
                else:
                    print("[DEBUG] ❌ No poem folder to sync (rendering may have failed)")
                    gdrive_success = False
                
                # Collect errors/warnings
                errors = []
                if not upload_success:
                    errors.append("Notion upload failed")
                if not gdrive_success:
                    errors.append("Google Drive sync failed")
                
                # Send admin report email automatically for auto-generation
                if self.email_enabled and poem_folder_path:
                    self.generation_log.append("")
                    self.generation_log.append("Sending admin email...")
                    self.needs_redraw = True
                    print(f"[DEBUG] Auto-gen: Sending admin report email...")
                    
                    if self._send_admin_report(
                        self.poem_claude, 
                        poem_folder_path, 
                        prompt_data=prompt_data, 
                        poem_type=poem_type,
                        gdrive_status=gdrive_success,
                        notion_status=upload_success,
                        api_time=api_time,
                        errors=errors if errors else None
                    ):
                        self.generation_log.append("  ✓ Email sent")
                        self.needs_redraw = True
                        print(f"[DEBUG] ✅ Admin report sent successfully")
                    else:
                        self.generation_log.append("  ✗ Email failed")
                        self.needs_redraw = True
                        print("[DEBUG] ❌ Admin report send failed")
                else:
                    if not self.email_enabled:
                        print("[DEBUG] Auto-gen: Email not enabled (check .env file)")
                    if not poem_folder_path:
                        print("[DEBUG] Auto-gen: No poem folder (rendering may have failed)")
                
                # Final completion message
                self.generation_log.append("")
                self.generation_log.append("> Generation complete!")
                self.needs_redraw = True
                # Wait 3 seconds then clear terminal and show poem
                pygame.time.wait(3000)
                self.generation_log = []
                self.generating_poems = False
                self.needs_redraw = True
            else:
                self.generation_log.append(f"> API error: {str(claude_result.get('error', ''))[:30]}")
                self.needs_redraw = True
                pygame.time.wait(2000)
                self.generation_progress_message = ""
                # Don't clear log on error
                # self.generation_log = []
                self.status = "Auto-gen: API failed (will retry)"
                print(f"[DEBUG] Auto-generation failed: {claude_result.get('error')}")
        
        except Exception as e:
            self.generation_log.append(f"▸ Error: {str(e)[:30]}")
            self.needs_redraw = True
            pygame.time.wait(2000)
            self.generation_progress_message = ""
            self.generation_log = []
            self.status = "Auto-gen: Error"
            print(f"[DEBUG] Auto-generation error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop LED pulsation
            try:
                self.sensors.stop_poem_pulsation()
                print("[DEBUG] LED pulsation stopped (auto-gen)")
            except Exception as e:
                print(f"[DEBUG] LED pulsation failed to stop: {e}")
            
            self.generating_poems = False
            self.checking_auto_gen = False
            self.needs_redraw = True

    # ---------- logging ----------
    def start_logging(self):
        if self.logging: return
        self.logging=True
        self.log_t0=time.time(); self.next_burst=time.time()
        self.stop_evt.clear()
        self.thread=threading.Thread(target=self._loop,daemon=True); self.thread.start()
        self.status="Logging ON"
    def stop_logging(self):
        if not self.logging: return
        self.logging=False
        if self.log_t0: self.elapsed_pause += (time.time()-self.log_t0); self.log_t0=None
        self.stop_evt.set(); self.thread=None; self.status="Logging OFF"
    def _loop(self):
        while not self.stop_evt.is_set():
            if time.time()>=self.next_burst:
                self.overlay_until = time.time() + self.burst + 0.3
                self._burst_and_log()
                if self.store.t: self.view_right=self.store.t[-1]
                self.next_burst=time.time()+self.interval
            time.sleep(0.02)

    def _burst_and_log(self, mark=False, note=""):
        # Don't set overlay_until here - let caller control ECG display
        vavg,vmin,vmax,mraw,mp,tc,hu,pr,lx = self._do_burst(self.burst, allow_draw=mark)
        ts=time.time()
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        row = [
            dt_str,
            f"{ts:.3f}", self.location,
            "" if vavg is None else f"{vavg:.6f}",
            "" if vmin is None else f"{vmin:.6f}",
            "" if vmax is None else f"{vmax:.6f}",
            "" if mraw is None else str(int(round(mraw))),
            "" if mp   is None else f"{mp:.2f}",
            "" if tc   is None else f"{tc:.2f}",
            "" if hu   is None else f"{hu:.1f}",
            "" if pr   is None else f"{pr:.1f}",
            "" if lx   is None else f"{lx:.2f}",
            "1" if mark else "0",
            note or ""
        ]
        append_row(CSV_PATH,row)
        self.store.push(ts,vavg,vmin,vmax,mraw,mp,tc,hu,pr,lx,mark,note,self.location)
        self.status=f"Logged @ {time.strftime('%H:%M:%S')}"

    def _do_burst(self, seconds, allow_draw=False):
        n=max(1,int(seconds*BURST_HZ)); period=1.0/BURST_HZ
        warm=min(n-1, max(0, int(0.5*BURST_HZ)))   # discard first ~0.5s of LUX, but keep at least 1 sample
        vs=[]; mrs=[]; tcs=[]; hus=[]; prs=[]; lxs=[]
        self.live_trace["ts"].clear(); self.live_trace["v"].clear()
        
        # Track burst timing for countdown
        self.burst_start_time = time.time()
        self.burst_duration = seconds
        
        # Force ECG overlay and redraw for the duration of burst
        self.overlay_until = time.time() + seconds + 0.5
        
        for i in range(n):
            v = self.sensors.read_v()
            m = self.sensors.read_mraw()
            # Read all BME280 values at once for efficiency
            tc_val, hu_val, pr_val = self.sensors.read_bme_all()
            lx = self.sensors.read_lx()
            
            if v is not None: vs.append(v)
            if m is not None: mrs.append(m)
            if tc_val is not None: tcs.append(tc_val)
            if hu_val is not None: hus.append(hu_val)
            if pr_val is not None: prs.append(pr_val)
            if lx is not None and i>=warm: lxs.append(lx)
            if v is not None:
                now=time.time()
                self.live_trace["ts"].append(now)
                self.live_trace["v"].append(v)
                
            # Force screen update during manual bursts (Mark events) if on Screen 2
            # For auto-bursts from background thread, main loop will handle drawing
            if allow_draw and self.screen_id == self.LOG and i % 2 == 0:
                self.needs_redraw = True
                self._draw(overlay_ecg=True)  # Explicitly request ECG overlay
                pygame.display.flip()  # Update the display
                
            # Process events to keep UI responsive
            pygame.event.pump()
            time.sleep(period)
        vavg=mean(vs) if vs else None; vmin=min(vs) if vs else None; vmax=max(vs) if vs else None
        mraw=mean(mrs) if mrs else None
        mp  = moisture_pct_from_raw(int(round(mraw))) if (mraw is not None) else None
        tc  = mean(tcs) if tcs else None
        hu  = mean(hus) if hus else None
        pr  = mean(prs) if prs else None
        lx  = mean(lxs) if lxs else None
        return vavg,vmin,vmax,mraw,mp,tc,hu,pr,lx

    # ---------- UI plumbing ----------
    def _update_scr(self):
        # No longer needed - screen navigation is handled by dedicated buttons
        pass

    def run(self):
        running=True
        last_heartbeat = time.time()
        heartbeat_file = "/tmp/biopoem_heartbeat.txt"
        
        # Write initial heartbeat
        with open(heartbeat_file, 'w') as f:
            f.write(f"{time.time()}\n")
        
        while running:
            # Update heartbeat every 30 seconds
            if time.time() - last_heartbeat > 30:
                try:
                    with open(heartbeat_file, 'w') as f:
                        f.write(f"{time.time()}\nScreen: {self.screen_id}\nLogging: {self.logging}\n")
                    last_heartbeat = time.time()
                except Exception as e:
                    print(f"[DEBUG] Heartbeat write failed: {e}")
            
            # Check for inactivity timeout (3 minutes) - auto-return to POEM view
            if self.screen_id in (self.DASH, self.LOG):
                inactivity_time = time.time() - self.last_interaction_time
                if inactivity_time > 180:  # 3 minutes
                    print(f"[DEBUG] Inactivity timeout after {inactivity_time:.0f}s - returning to POEM view")
                    self.screen_id = self.POEM
                    self._enter_screen()
                    self.last_interaction_time = time.time()
            
            events_happened = False
            for ev in pygame.event.get():
                events_happened = True
                # Update interaction time on any event
                self.last_interaction_time = time.time()
                
                if ev.type==pygame.QUIT:
                    print(f"[EXIT] pygame.QUIT event received at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    import traceback
                    print(f"[EXIT] Call stack:")
                    traceback.print_stack()
                    running=False
                elif ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_ESCAPE:
                        print(f"[EXIT] ESCAPE key pressed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                        running=False
                    elif ev.key==pygame.K_LEFT:  self.screen_id=max(self.DASH,self.screen_id-1); self._enter_screen()
                    elif ev.key==pygame.K_RIGHT: self.screen_id=min(self.POEM,self.screen_id+1); self._enter_screen()
                    elif ev.key==pygame.K_1: self.screen_id=self.DASH; self._enter_screen()
                    elif ev.key==pygame.K_2: self.screen_id=self.LOG;  self._enter_screen()
                    elif ev.key==pygame.K_3: self.screen_id=self.POEM; self._enter_screen()
                    elif ev.key==pygame.K_g:  # G key to generate STANDARD (non-visual) poem
                        print(f"[DEBUG] G key detected! generating_poems={self.generating_poems}, POETRY_AVAILABLE={POETRY_AVAILABLE}")
                        if not self.generating_poems and POETRY_AVAILABLE:
                            print("[DEBUG] G key pressed - starting STANDARD (non-visual) poem generation...")
                            self.screen_id = self.POEM
                            self._enter_screen()
                            self.generating_poems = True
                            self.poem_generation_mode = "daily"
                            self.force_standard_generation = True  # Flag to force standard poem
                            self.generation_thread = threading.Thread(target=self._generate_poems_thread, daemon=True)
                            self.generation_thread.start()
                        elif self.generating_poems:
                            print("[DEBUG] Already generating - ignoring G key")
                        elif not POETRY_AVAILABLE:
                            print("[DEBUG] Poetry engine not available - cannot generate")
                    elif ev.key==pygame.K_w:  # W key to generate weekly poem
                        print(f"[DEBUG] W key detected! generating_poems={self.generating_poems}, POETRY_AVAILABLE={POETRY_AVAILABLE}")
                        if not self.generating_poems and POETRY_AVAILABLE:
                            print("[DEBUG] W key pressed - starting WEEKLY poem generation...")
                            self.screen_id = self.POEM
                            self._enter_screen()
                            self.generating_poems = True
                            self.poem_generation_mode = "weekly"
                            self.generation_thread = threading.Thread(target=self._generate_poems_thread, daemon=True)
                            self.generation_thread.start()
                        elif self.generating_poems:
                            print("[DEBUG] Already generating - ignoring W key")
                        elif not POETRY_AVAILABLE:
                            print("[DEBUG] Poetry engine not available - cannot generate")
                    elif ev.key==pygame.K_v:  # V key to generate visual poem (manual force)
                        print(f"[DEBUG] V key detected! generating_poems={self.generating_poems}, POETRY_AVAILABLE={POETRY_AVAILABLE}")
                        if not self.generating_poems and POETRY_AVAILABLE:
                            # Show pattern selection modal
                            selected_pattern = self._modal_visual_pattern_select()
                            if selected_pattern:
                                print(f"[DEBUG] V key pressed - starting VISUAL poem with pattern: {selected_pattern}")
                                self.screen_id = self.POEM
                                self._enter_screen()
                                self.generating_poems = True
                                self.poem_generation_mode = "daily"  # Visual poems are daily type
                                self.force_visual_generation = True  # Flag for manual visual forcing
                                self.selected_visual_pattern = selected_pattern  # Store selected pattern
                                self.generation_thread = threading.Thread(target=self._generate_poems_thread, daemon=True)
                                self.generation_thread.start()
                            else:
                                print("[DEBUG] Visual pattern selection cancelled")
                        elif self.generating_poems:
                            print("[DEBUG] Already generating - ignoring V key")
                        elif not POETRY_AVAILABLE:
                            print("[DEBUG] Poetry engine not available - cannot generate")
                    elif ev.key==pygame.K_UP and self.screen_id == self.POEM:
                        # Scroll up on poem screen
                        self.poem_scroll_offset = max(0, self.poem_scroll_offset - 30)
                        self.needs_redraw = True
                        print(f"[DEBUG] Scroll up: offset={self.poem_scroll_offset}")
                    elif ev.key==pygame.K_DOWN and self.screen_id == self.POEM:
                        # Scroll down on poem screen  
                        self.poem_scroll_offset += 30
                        self.needs_redraw = True
                        print(f"[DEBUG] Scroll down: offset={self.poem_scroll_offset}")
                    elif ev.key==pygame.K_LEFT and self.screen_id == self.POEM:
                        # Navigate carousel left (previous)
                        self.poem_carousel_index = max(0, self.poem_carousel_index - 1)
                        self.poem_scroll_offset = 0  # Reset scroll for new image
                        self.needs_redraw = True
                        print(f"[DEBUG] Carousel left: index={self.poem_carousel_index}")
                    elif ev.key==pygame.K_RIGHT and self.screen_id == self.POEM:
                        # Navigate carousel right (next)
                        self.poem_carousel_index = min(2, self.poem_carousel_index + 1)
                        self.poem_scroll_offset = 0  # Reset scroll for new image
                        self.needs_redraw = True
                        print(f"[DEBUG] Carousel right: index={self.poem_carousel_index}")
                    elif ev.key==pygame.K_u:  # Upload to Notion (retroactive)
                        if self.poem_claude:
                            print("[DEBUG] U key pressed - uploading to Notion...")
                            # Use stored prompt_data if available (from last generation or loaded from file)
                            poem_type = self.poem_prompt_data.get('poem_type', 'daily') if self.poem_prompt_data else 'daily'
                            if self._upload_to_notion(self.poem_claude, prompt_data=self.poem_prompt_data, poem_type=poem_type):
                                count = self.poem_logger.get_generation_count() if self.poem_logger else '?'
                                self.status = f"Uploaded to Notion! (Total: {count})"
                                print("[DEBUG] ✅ Upload successful!")
                    elif ev.key==pygame.K_y:  # Y key to send email report
                        if hasattr(self, 'prompt_email_report') and self.prompt_email_report:
                            print("[DEBUG] Y key pressed - sending email report...")
                            self.prompt_email_report = False
                            if hasattr(self, 'pending_email_data'):
                                data = self.pending_email_data
                                if self._send_admin_report(
                                    data['poem_text'],
                                    data['poem_folder'],
                                    prompt_data=data['prompt_data'],
                                    poem_type=data['poem_type'],
                                    gdrive_status=data['gdrive_status'],
                                    notion_status=data['notion_status'],
                                    api_time=data['api_time'],
                                    errors=data['errors']
                                ):
                                    self.status = "Email report sent! ✅"
                                    print("[DEBUG] ✅ Email report sent successfully")
                                else:
                                    self.status = "Email report failed ❌"
                                    print("[DEBUG] ❌ Email report send failed")
                                delattr(self, 'pending_email_data')
                    elif ev.key==pygame.K_n:  # N key to skip email report
                        if hasattr(self, 'prompt_email_report') and self.prompt_email_report:
                            print("[DEBUG] N key pressed - skipping email report")
                            self.prompt_email_report = False
                            if hasattr(self, 'pending_email_data'):
                                delattr(self, 'pending_email_data')
                            count = self.poem_logger.get_generation_count() if self.poem_logger else '?'
                            self.status = f"Poem generated (Total: {count})"
                    elif ev.key==pygame.K_d and self.screen_id == self.POEM:  # Toggle dark mode manually
                        self.poem_dark_mode = not self.poem_dark_mode
                        self.poem_auto_dark_mode = False  # Disable auto when manually toggled
                        self.needs_redraw = True
                        mode_str = "dark" if self.poem_dark_mode else "light"
                    elif ev.key==pygame.K_r and self.screen_id == self.POEM:  # R key to render images for current poem
                        if self.poem_claude and not self.generating_poems:
                            print("[DEBUG] R key pressed - rendering images for current poem...")
                            self.status = "Rendering images..."
                            threading.Thread(target=self._render_current_poem_images, daemon=True).start()
                        else:
                            self.status = "No poem to render" if not self.poem_claude else "Already generating"
                        print(f"[DEBUG] D key pressed - toggled to {mode_str} mode (auto disabled)")
                        self.status = f"Poem display: {mode_str} mode"
                    elif ev.key==pygame.K_s:  # S key to show sensor status
                        print("[DEBUG] S key pressed - showing sensor status")
                        self._modal_sensors()
                    elif ev.key==pygame.K_e and self.screen_id == self.POEM:  # E key to open visual editor
                        print("[DEBUG] E key pressed - opening visual poem editor...")
                        import webbrowser
                        webbrowser.open('http://192.168.0.242:5000')
                        self.status = "Opening editor in browser..."
                    elif ev.key==pygame.K_l:  # L key to test LED palette
                        if self.sensors.ok_led:
                            if self.sensors._led_pulsing:
                                # Stop if already running
                                print("[DEBUG] L key pressed - stopping LED test")
                                self.sensors.stop_poem_pulsation()
                                self.status = ""  # Clear status when stopped
                            else:
                                # Start LED test
                                print("[DEBUG] L key pressed - starting LED palette test")
                                self.sensors.start_poem_pulsation()
                                self.status = "LED"  # Show only "LED" while testing
                        else:
                            self.status = "No LED"
                            print("[DEBUG] L key pressed but LED not available")
                        self.needs_redraw = True

                elif ev.type==pygame.MOUSEBUTTONDOWN:
                    if getattr(ev,"button",None) in (4,5):  # wheel (legacy)
                        class _WheelEvent: pass
                        e=_WheelEvent(); e.y= 1 if ev.button==4 else -1; self._wheel(e)
                    else:
                        self._mouse_down(ev.pos)
                elif ev.type==pygame.MOUSEBUTTONUP:
                    # Handle swipe gestures on poem screen
                    if self.screen_id == self.POEM and self.poem_swipe_start_x is not None:
                        mx = ev.pos[0]
                        dx = self.poem_swipe_start_x - mx
                        swipe_time = time.time() - self.poem_swipe_start_time
                        
                        # Detect horizontal swipe (dx > 100px and time < 0.5s)
                        if abs(dx) > 100 and swipe_time < 0.5:
                            if dx > 0:  # Swipe left = next image
                                self.poem_carousel_index = min(2, self.poem_carousel_index + 1)
                                self.poem_scroll_offset = 0  # Reset scroll for new image
                                self.needs_redraw = True
                                print(f"[DEBUG] Swiped to carousel index {self.poem_carousel_index}")
                            elif dx < 0:  # Swipe right = previous image
                                self.poem_carousel_index = max(0, self.poem_carousel_index - 1)
                                self.poem_scroll_offset = 0  # Reset scroll for new image
                                self.needs_redraw = True
                                print(f"[DEBUG] Swiped to carousel index {self.poem_carousel_index}")
                        
                        self.poem_swipe_start_x = None
                    
                    self.drag=False; self.last_x=None
                    self.poem_scroll_start_y = None  # End touch scroll
                elif ev.type==pygame.MOUSEMOTION:
                    if self.screen_id == self.POEM and self.poem_scroll_start_y is not None:
                        # Check if motion is primarily vertical (scroll) or horizontal (swipe)
                        mx, my = ev.pos[0], ev.pos[1]
                        dx = abs(mx - self.poem_swipe_start_x) if self.poem_swipe_start_x else 0
                        dy = abs(my - self.poem_scroll_start_y) if self.poem_scroll_start_y else 0
                        
                        # If primarily vertical motion, scroll
                        if dy > dx and dy > 5:
                            delta = self.poem_scroll_start_y - my
                            self.poem_scroll_offset += delta
                            self.poem_scroll_offset = max(0, self.poem_scroll_offset)
                            self.poem_scroll_start_y = my
                            self.poem_last_scroll_time = time.time()
                            self.needs_redraw = True
                        # If horizontal, wait for mouseup to detect swipe
                        # (no immediate action, just track for swipe detection)
                    elif self.drag:
                        # Chart panning
                        dx=ev.pos[0] - (self.last_x if self.last_x is not None else ev.pos[0])
                        self.last_x=ev.pos[0]
                        sec_per_px=self.view_span/max(1,self.p1.width)
                        self.view_right -= dx*sec_per_px
                        self.last_interaction_time = time.time()  # Track interaction
                        self.needs_redraw = True
                elif ev.type==pygame.MOUSEWHEEL:
                    # If showing ECG, allow zooming
                    if time.time()<self.overlay_until:
                        if ev.y>0: self.ecg_zoom=max(0.5, self.ecg_zoom*0.9)
                        elif ev.y<0: self.ecg_zoom=min(5.0, self.ecg_zoom/0.9)
                        self.needs_redraw = True
                    else:
                        self._wheel(ev)

            # Check for automatic 8pm poem generation
            self._check_auto_generation()
            
            # Auto-reset poem scroll after 10s of inactivity
            if self.poem_scroll_offset > 0 and time.time() - self.poem_last_scroll_time > 10:
                self.poem_scroll_offset = 0
                self.needs_redraw = True
            
            # Auto-scroll STATS screen back to latest after 5 mins of inactivity
            if self.screen_id == self.LOG:
                if time.time() - self.last_interaction_time > 300:  # 5 minutes
                    if self.store.t:
                        latest = self.store.t[-1]
                        if abs(self.view_right - latest) > 1.0:  # Only update if not already at latest
                            self.view_right = latest
                            self.needs_redraw = True
                            self.last_interaction_time = time.time()  # Reset timer after auto-scroll
            
            # dashboard live sampler - ONLY when on dashboard screen
            if self.screen_id==self.DASH:
                # dash_on is set immediately now (no countdown)
                if self.dash_on and time.time()>=self.dash_next:
                    self._dash_sample()
                    self.dash_next += self.dash_dt
                    self.needs_redraw = True
            else:
                # Not on dashboard - turn off sampling to save resources
                if self.dash_on:
                    self.dash_on=False
                    self.needs_redraw = True

            # ECG overlay forces redraws
            if time.time() < self.overlay_until:
                self.needs_redraw = True

            # Only draw if needed - wrap in try/except to catch crashes
            if events_happened or self.needs_redraw or self.logging:
                try:
                    self._draw()
                    self.needs_redraw = False
                except Exception as e:
                    print(f"[CRASH] Draw error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Try to continue running after draw error
                    self.needs_redraw = True
            
            self.clock.tick(FPS_UI)

        print(f"[EXIT] Main loop ended at {time.strftime('%Y-%m-%d %H:%M:%S')}, running={running}")
        self.stop_logging()
        print(f"[EXIT] Calling pygame.quit()")
        pygame.quit()
        print(f"[EXIT] pygame.quit() complete, exiting program")

    def _enter_screen(self):
        self._update_scr()
        # When leaving dashboard, stop live sampling
        if self.screen_id != self.DASH:
            self.dash_on = False
        else:
            self.dash_on = True  # Start live immediately on dashboard
        
        # Hide UI when entering poem screen
        if self.screen_id == self.POEM:
            self.poem_ui_visible = False
        
        self.dash_enter=time.time()
        # Clear ECG trace when switching screens to prevent long line
        # But keep ECG display for Screen 2 (Logger) during bursts
        if self.screen_id != self.DASH and self.screen_id != self.LOG:
            self.live_trace["ts"].clear()
            self.live_trace["v"].clear()
            self.overlay_until = 0  # Cancel any pending ECG display
        self.needs_redraw = True

    def _mouse_down(self,pos):
        print(f"[DEBUG] Mouse click at {pos}, screen={self.screen_id}")
        
        # Start touch interaction on poem screen (track both x and y for swipe detection)
        if self.screen_id == self.POEM and self.poem_claude and not self.generating_poems:
            self.poem_swipe_start_x = pos[0]
            self.poem_scroll_start_y = pos[1]
            self.poem_swipe_start_time = time.time()
            self.poem_last_scroll_time = time.time()
        

        # On poem screen, handle touch scrolling and UI toggle
        if self.screen_id == self.POEM:
            # Start touch scroll if there's a poem
            if self.poem_claude and not self.generating_poems:
                self.poem_scroll_start_y = pos[1]
                self.poem_last_scroll_time = time.time()
                # Don't return yet, check for buttons first
            
            # Check quit confirmation timeout (auto-cancel after 5 seconds)
            if self.quit_confirm_active and (time.time() - self.quit_confirm_time) > 5.0:
                self.quit_confirm_active = False
                self.needs_redraw = True
                print("[DEBUG] Quit confirmation timed out")
            
            # Always check top buttons first (if UI is visible)
            if self.poem_ui_visible and pos[1] < TOPBAR_H:
                # Check which button was clicked
                for btn in [self.b_live, self.b_stats, self.b_poem, self.b_generate]:
                    if btn.contains(pos):
                        # Handle button click below (don't return here)
                        break
                else:
                    # Clicked in top bar but not on a button - toggle UI
                    self.poem_ui_visible = not self.poem_ui_visible
                    self.needs_redraw = True
                    print(f"[DEBUG] Poem UI toggled (topbar): {self.poem_ui_visible}")
                    return
            elif self.poem_ui_visible:
                # Clicked outside top bar with UI visible - toggle off
                self.poem_ui_visible = False
                pygame.mouse.set_visible(False)
                self.needs_redraw = True
                print(f"[DEBUG] Poem UI hidden")
                return
            elif not self.poem_ui_visible:
                # UI hidden - any tap shows it
                self.poem_ui_visible = True
                pygame.mouse.set_visible(True)
                self.needs_redraw = True
                print(f"[DEBUG] Poem UI shown")
                return
        
        # Check bottom status bar clickable regions first
        status_y = self.sh - 40  # Approximate status bar Y position
        if pos[1] >= status_y:
            # Check LOGGING text (left side) - hidden quit mechanism
            if hasattr(self, 'logging_text_rect') and self.logging_text_rect.collidepoint(pos):
                self._handle_logging_quit_tap()
                self.needs_redraw = True
                return
            
            # Check LED button (right side)
            if hasattr(self, 'led_btn_rect') and self.led_btn_rect.collidepoint(pos):
                print(f"[DEBUG] LED button clicked. quit_confirm_active={self.quit_confirm_active}, ok_led={self.sensors.ok_led}, _led_pulsing={self.sensors._led_pulsing}", flush=True)
                # Toggle LED only if not in quit confirmation mode
                if not self.quit_confirm_active and self.sensors.ok_led:
                    if self.sensors._led_pulsing:
                        self.sensors.stop_poem_pulsation()
                        print("[DEBUG] LED button - stopped", flush=True)
                    else:
                        self.sensors.start_poem_pulsation()
                        print("[DEBUG] LED button - started", flush=True)
                self.needs_redraw = True
                return
        
        # Screen navigation buttons
        if self.b_live.contains(pos):
            self.screen_id = self.DASH
            self._enter_screen()
        elif self.b_stats.contains(pos):
            self.screen_id = self.LOG
            self._enter_screen()
        elif self.b_poem.contains(pos):
            self.screen_id = self.POEM
            self._enter_screen()
        elif self.b_generate.contains(pos):
            self._handle_generate_button()
        elif self.screen_id == self.DASH and self.b_zoom_in.contains(pos):
            # Zoom in (increase zoom factor)
            self.dash_y_zoom = min(10.0, self.dash_y_zoom * 1.5)
            self.needs_redraw = True
        elif self.screen_id == self.DASH and self.b_zoom_out.contains(pos):
            # Zoom out (decrease zoom factor)
            self.dash_y_zoom = max(0.5, self.dash_y_zoom / 1.5)
            self.needs_redraw = True
        else:
            if self.screen_id == self.POEM:
                # Touch scroll on poem screen
                if self.poem_scroll_start_y is not None:
                    my = pygame.mouse.get_pos()[1]
                    delta = self.poem_scroll_start_y - my
                    self.poem_scroll_offset += delta
                    self.poem_scroll_offset = max(0, self.poem_scroll_offset)  # Will be clamped in render
                    self.poem_scroll_start_y = my
                    self.poem_last_scroll_time = time.time()
                    self.needs_redraw = True
            elif self.screen_id in (self.DASH,self.LOG):
                if self.p1.collidepoint(pos) or self.p2.collidepoint(pos) or self.pLux.collidepoint(pos) or self.pTemp.collidepoint(pos):
                    self.drag=True; self.last_x=pos[0]

    def _wheel(self,ev):
        mods=pygame.key.get_mods(); ctrl=(mods & pygame.KMOD_CTRL)!=0
        mx,my=pygame.mouse.get_pos()
        panel = "v" if self.p1.collidepoint((mx,my)) else ("mp" if self.p2.collidepoint((mx,my)) else ("lx" if self.pLux.collidepoint((mx,my)) else ("tc" if self.pTemp.collidepoint((mx,my)) else None)))
        if ctrl:  # X-zoom
            if ev.y>0: self.view_span=max(X_SPAN_MIN, self.view_span*WHEEL_ZOOM_FACTOR)
            elif ev.y<0: self.view_span=min(X_SPAN_MAX, self.view_span/WHEEL_ZOOM_FACTOR)
        else:      # Y-zoom for panel
            if not panel: return
            f=WHEEL_ZOOM_FACTOR if ev.y>0 else (1.0/WHEEL_ZOOM_FACTOR)
            self.y_zoom[panel]=clampf(self.y_zoom[panel]*f, 0.05, 20.0)
        self.needs_redraw = True

    # ---------- Modals ----------
    def _modal_mark_note(self):
        """Ask for event note, then will do burst. Returns note text or None if cancelled."""
        W,H=320,340; m=pygame.Rect(self.sw//2-W//2,self.sh//2-H//2,W,H)
        text=""; typing=True; clock=pygame.time.Clock()
        bg_surface = self.screen.copy()
        
        # Button rectangles
        btn_w = 120
        btn_h = 45
        btn_spacing = 10
        
        # Keyboard button (top)
        kbd_btn = pygame.Rect(m.centerx - 100, m.top + 170, 200, 40)
        
        # OK and Cancel buttons (bottom)
        btn_y = m.bottom - btn_h - 15
        ok_btn = pygame.Rect(m.left + 20, btn_y, btn_w, btn_h)
        cancel_btn = pygame.Rect(m.right - btn_w - 20, btn_y, btn_w, btn_h)
        
        while typing:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: 
                    self.keyboard.hide()
                    return None
                if ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_RETURN: 
                        self.keyboard.hide()
                        return text  # OK - will do burst
                    elif ev.key==pygame.K_ESCAPE:
                        self.keyboard.hide()
                        return None  # Cancel
                    elif ev.key==pygame.K_BACKSPACE: 
                        text=text[:-1]
                    else:
                        if ev.unicode and ev.unicode.isprintable() and len(text)<120: 
                            text+=ev.unicode
                elif ev.type==pygame.MOUSEBUTTONDOWN:
                    # Check keyboard first
                    key_pressed = self.keyboard.handle_click(ev.pos)
                    if key_pressed:
                        if key_pressed == '\b':  # Backspace
                            text = text[:-1]
                        elif len(text) < 120:
                            text += key_pressed
                    elif ok_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        return text  # OK clicked
                    elif cancel_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        return None  # Cancel clicked
                    elif kbd_btn.collidepoint(ev.pos):
                        self.keyboard.toggle()
            
            self.screen.blit(bg_surface, (0,0))
            pygame.draw.rect(self.screen,(30,30,40),m,border_radius=10)
            pygame.draw.rect(self.screen,(140,140,160),m,2,border_radius=10)
            
            title=self.big.render("Mark Event",True,TEXT_COLOR)
            self.screen.blit(title,(m.centerx-title.get_width()//2, m.top+18))
            
            hint=self.font.render("Enter note (optional)",True,(200,200,220))
            self.screen.blit(hint,(m.centerx-hint.get_width()//2, m.top+58))
            
            # Text input box
            box=pygame.Rect(m.left+20,m.top+95,m.width-40,60)
            pygame.draw.rect(self.screen,(10,10,12),box,border_radius=8)
            pygame.draw.rect(self.screen,(120,140,200),box,2,border_radius=8)
            
            # Show text with cursor
            display_text = text + "|"
            ttxt=self.font.render(display_text,True,(240,240,240))
            self.screen.blit(ttxt,(box.left+10, box.top+16))
            
            # Keyboard button
            kbd_color = (70,70,120) if not self.keyboard.visible else (100,140,100)
            pygame.draw.rect(self.screen,kbd_color,kbd_btn,border_radius=8)
            pygame.draw.rect(self.screen,(140,140,180),kbd_btn,2,border_radius=8)
            kbd_txt=self.font.render("Show Keyboard" if not self.keyboard.visible else "Hide Keyboard",True,(240,240,240))
            self.screen.blit(kbd_txt,(kbd_btn.centerx-kbd_txt.get_width()//2, kbd_btn.centery-kbd_txt.get_height()//2))
            
            # OK button
            pygame.draw.rect(self.screen,(60,100,60),ok_btn,border_radius=8)
            pygame.draw.rect(self.screen,(120,160,120),ok_btn,2,border_radius=8)
            ok_txt=self.big.render("OK",True,(240,240,240))
            self.screen.blit(ok_txt,(ok_btn.centerx-ok_txt.get_width()//2, ok_btn.centery-ok_txt.get_height()//2))
            
            # Cancel button
            pygame.draw.rect(self.screen,(100,60,60),cancel_btn,border_radius=8)
            pygame.draw.rect(self.screen,(160,120,120),cancel_btn,2,border_radius=8)
            cancel_txt=self.big.render("Cancel",True,(240,240,240))
            self.screen.blit(cancel_txt,(cancel_btn.centerx-cancel_txt.get_width()//2, cancel_btn.centery-cancel_txt.get_height()//2))
            
            # Draw keyboard last (on top)
            self.keyboard.draw()
            
            pygame.display.flip()
            clock.tick(30)
        
        self.keyboard.hide()
        return None

    def _modal_numeric(self, title, current_val, min_val=1, max_val=9999):
        """Generic numeric input modal - supports integers and floats"""
        W,H=420,340; box=pygame.Rect(self.sw//2-W//2,self.sh//2-H//2,W,H)
        # Allow decimal point for float values
        txt=str(current_val) if isinstance(current_val, float) else str(int(current_val))
        typing=True; clock=pygame.time.Clock()
        bg_surface = self.screen.copy()
        
        # Set keyboard to numeric mode
        self.keyboard.set_mode(numeric=True)
        
        # Button rectangles
        btn_w = 140
        btn_h = 45
        
        # Keyboard button (middle)
        kbd_btn = pygame.Rect(box.centerx - 100, box.centery + 40, 200, 40)
        
        # OK and Cancel buttons (bottom)
        btn_y = box.bottom - btn_h - 15
        ok_btn = pygame.Rect(box.left + 30, btn_y, btn_w, btn_h)
        cancel_btn = pygame.Rect(box.right - btn_w - 30, btn_y, btn_w, btn_h)
        
        while typing:
            for ev in pygame.event.get():
                if ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_RETURN:
                        self.keyboard.hide()
                        self.keyboard.set_mode(numeric=False)
                        typing=False
                        try:
                            # Try float first, then int
                            val = float(txt) if '.' in txt else int(txt)
                            return max(min_val, min(max_val, val))
                        except:
                            return current_val
                    elif ev.key==pygame.K_ESCAPE:
                        self.keyboard.hide()
                        self.keyboard.set_mode(numeric=False)
                        return current_val
                    elif ev.key==pygame.K_BACKSPACE: txt=txt[:-1]
                    elif ev.key==pygame.K_DELETE: txt=""  # Clear all
                    else:
                        # Allow digits and decimal point
                        if (ev.unicode.isdigit() or (ev.unicode=='.' and '.' not in txt)) and len(txt)<5: 
                            txt+=ev.unicode
                elif ev.type==pygame.QUIT:
                    self.keyboard.hide()
                    self.keyboard.set_mode(numeric=False)
                    return current_val
                elif ev.type==pygame.MOUSEBUTTONDOWN:
                    # Check keyboard first
                    key_pressed = self.keyboard.handle_click(ev.pos)
                    if key_pressed:
                        if key_pressed == '\b':  # Backspace
                            txt = txt[:-1]
                        elif key_pressed == '\x7f':  # CLEAR (DEL character)
                            txt = ""
                        elif (key_pressed.isdigit() or (key_pressed=='.' and '.' not in txt)) and len(txt)<5:
                            txt += key_pressed
                    elif ok_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        self.keyboard.set_mode(numeric=False)
                        try:
                            val = float(txt) if '.' in txt else int(txt)
                            return max(min_val, min(max_val, val))
                        except:
                            return current_val
                    elif cancel_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        self.keyboard.set_mode(numeric=False)
                        return current_val
                    elif kbd_btn.collidepoint(ev.pos):
                        self.keyboard.toggle()
            
            self.screen.blit(bg_surface, (0,0))
            pygame.draw.rect(self.screen,(25,25,28),box,border_radius=8)
            pygame.draw.rect(self.screen,(120,120,150),box,2,border_radius=8)
            
            t1=self.big.render(title,True,TEXT_COLOR)
            self.screen.blit(t1,(box.centerx-t1.get_width()//2, box.top+18))
            
            # Value display
            display_val = txt if txt else "0"
            t2=self.huge.render(display_val,True,(240,240,240))
            self.screen.blit(t2,(box.centerx-t2.get_width()//2, box.centery-50))
            
            hint=self.fontS.render(f"Range: {min_val}-{max_val}",True,(180,180,200))
            self.screen.blit(hint,(box.centerx-hint.get_width()//2, box.centery+5))
            
            # Keyboard button
            kbd_color = (70,70,120) if not self.keyboard.visible else (100,140,100)
            pygame.draw.rect(self.screen,kbd_color,kbd_btn,border_radius=8)
            pygame.draw.rect(self.screen,(140,140,180),kbd_btn,2,border_radius=8)
            kbd_txt=self.font.render("Keypad" if not self.keyboard.visible else "Hide Keypad",True,(240,240,240))
            self.screen.blit(kbd_txt,(kbd_btn.centerx-kbd_txt.get_width()//2, kbd_btn.centery-kbd_txt.get_height()//2))
            
            # OK button
            pygame.draw.rect(self.screen,(60,100,60),ok_btn,border_radius=8)
            pygame.draw.rect(self.screen,(120,160,120),ok_btn,2,border_radius=8)
            ok_txt=self.big.render("OK",True,(240,240,240))
            self.screen.blit(ok_txt,(ok_btn.centerx-ok_txt.get_width()//2, ok_btn.centery-ok_txt.get_height()//2))
            
            # Cancel button
            pygame.draw.rect(self.screen,(100,60,60),cancel_btn,border_radius=8)
            pygame.draw.rect(self.screen,(160,120,120),cancel_btn,2,border_radius=8)
            cancel_txt=self.big.render("Cancel",True,(240,240,240))
            self.screen.blit(cancel_txt,(cancel_btn.centerx-cancel_txt.get_width()//2, cancel_btn.centery-cancel_txt.get_height()//2))
            
            # Draw keyboard last (on top)
            self.keyboard.draw()
            
            pygame.display.flip()
            clock.tick(30)
        
        self.keyboard.hide()
        self.keyboard.set_mode(numeric=False)
        return current_val
    
    def _modal_sensors(self):
        """Show sensor status modal - compact bottom popup"""
        W,H=400,220; 
        box=pygame.Rect(self.sw//2-W//2, self.sh-H-60, W, H)  # Bottom of screen
        viewing=True; clock=pygame.time.Clock()
        bg_surface = self.screen.copy()
        
        while viewing:
            for ev in pygame.event.get():
                if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN): 
                    viewing=False
                elif ev.type==pygame.QUIT: 
                    return
            
            self.screen.blit(bg_surface, (0,0))
            pygame.draw.rect(self.screen,(25,25,28),box,border_radius=10)
            pygame.draw.rect(self.screen,(120,120,150),box,3,border_radius=10)
            
            title=self.big.render("Sensor Status",True,TEXT_COLOR)
            self.screen.blit(title,(box.centerx-title.get_width()//2, box.top+15))
            
            y = box.top + 60
            sensors = [
                ("Soil Moisture (Grove A0)", self.sensors.ok_soil),
                ("Light (VEML6030)", self.sensors.ok_lux),
                ("Temp/Humid/Pres (BME280)", self.sensors.ok_bme),
                ("Voltage (ADS1115)", False, "DISABLED"),  # Disabled
            ]
            
            for item in sensors:
                if len(item) == 3:  # Disabled sensor
                    name, status, note = item
                    txt = self.font.render(f"—  {name} [{note}]", True, (150, 150, 150))
                else:
                    name, status = item
                    color = (80,255,120) if status else (255,80,80)
                    icon = "OK" if status else "X"
                    txt = self.font.render(f"{icon}  {name}", True, color)
                self.screen.blit(txt, (box.left+25, y))
                y += 42
            
            hint=self.fontS.render("Tap to close",True,(180,180,200))
            self.screen.blit(hint,(box.centerx-hint.get_width()//2, box.bottom-25))
            pygame.display.flip(); clock.tick(30)
        self.needs_redraw = True

    def _modal_visual_pattern_select(self):
        """Show visual pattern selection modal - returns selected pattern or None for cancel"""
        # All 15 visual patterns organized by tier
        patterns = [
            # Tier 1 - Basic
            ("centered_spine", "Centered Spine", "Lines stacked in center"),
            ("center_stem", "Center Stem", "Alternating around center"),
            ("refrain_stack", "Refrain Stack", "Alternating left/right"),
            ("right_droop", "Right Droop", "Progressive right indent"),
            ("left_climb", "Left Climb", "Decreasing indent from right"),
            # Tier 2 - Advanced
            ("field_constellation", "Field Constellation", "Scattered placement"),
            ("diagonal_pairing", "Diagonal Pairing", "Two diagonal paths"),
            ("distant_islands", "Distant Islands", "Isolated word groups"),
            ("minimal_drift", "Minimal Drift", "Sparse, minimal"),
            # Tier 3 - Complex
            ("swarming_refrain", "Swarming Refrain", "Chaotic scatter"),
            ("echo_cascade", "Echo Cascade", "Progressive indent"),
            ("forked_path", "Forked Path", "Split paths"),
            ("dense_field", "Dense Field", "Tightly packed"),
            ("central_thread", "Central Thread", "Narrow center column"),
            ("morph_ladder", "Morph Ladder", "Stair-step pattern"),
        ]
        
        W, H = 500, 520
        box = pygame.Rect(self.sw//2 - W//2, self.sh//2 - H//2, W, H)
        bg_surface = self.screen.copy()
        clock = pygame.time.Clock()
        
        # Scrollable list state
        scroll_offset = 0
        item_height = 50
        visible_items = 8
        max_scroll = max(0, len(patterns) * item_height - visible_items * item_height)
        hover_index = -1  # Track which item mouse is hovering over
        
        # Cancel button
        cancel_btn = pygame.Rect(box.centerx - 60, box.bottom - 50, 120, 40)
        
        selecting = True
        while selecting:
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.needs_redraw = True
                        return None
                    elif ev.key == pygame.K_UP:
                        scroll_offset = max(0, scroll_offset - item_height)
                    elif ev.key == pygame.K_DOWN:
                        scroll_offset = min(max_scroll, scroll_offset + item_height)
                elif ev.type == pygame.QUIT:
                    self.needs_redraw = True
                    return None
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if cancel_btn.collidepoint(ev.pos):
                        self.needs_redraw = True
                        return None
                    # Check if clicked on a pattern
                    list_area = pygame.Rect(box.left + 20, box.top + 60, box.width - 40, visible_items * item_height)
                    if list_area.collidepoint(ev.pos):
                        click_y = ev.pos[1] - list_area.top + scroll_offset
                        idx = int(click_y // item_height)
                        if 0 <= idx < len(patterns):
                            self.needs_redraw = True
                            return patterns[idx][0]  # Return pattern key
                elif ev.type == pygame.MOUSEWHEEL:
                    scroll_offset = max(0, min(max_scroll, scroll_offset - ev.y * item_height))
            
            # Track mouse hover position
            mouse_pos = pygame.mouse.get_pos()
            list_area = pygame.Rect(box.left + 20, box.top + 60, box.width - 40, visible_items * item_height)
            if list_area.collidepoint(mouse_pos):
                hover_y = mouse_pos[1] - list_area.top + scroll_offset
                hover_index = int(hover_y // item_height)
                if hover_index < 0 or hover_index >= len(patterns):
                    hover_index = -1
            else:
                hover_index = -1
            
            # Draw
            self.screen.blit(bg_surface, (0, 0))
            pygame.draw.rect(self.screen, (25, 25, 28), box, border_radius=10)
            pygame.draw.rect(self.screen, (120, 120, 150), box, 2, border_radius=10)
            
            # Title
            title = self.big.render("Select Visual Pattern", True, TEXT_COLOR)
            self.screen.blit(title, (box.centerx - title.get_width()//2, box.top + 18))
            
            # Pattern list area
            list_area = pygame.Rect(box.left + 20, box.top + 60, box.width - 40, visible_items * item_height)
            pygame.draw.rect(self.screen, (15, 15, 18), list_area, border_radius=8)
            
            # Clip to list area
            clip_rect = self.screen.get_clip()
            self.screen.set_clip(list_area)
            
            # Draw patterns
            for i, (key, name, desc) in enumerate(patterns):
                y = list_area.top + i * item_height - scroll_offset
                if list_area.top - item_height < y < list_area.bottom:
                    row_rect = pygame.Rect(list_area.left, y, list_area.width, item_height)
                    
                    # Highlight if hovering
                    if i == hover_index:
                        # Bright highlight for hovered item
                        pygame.draw.rect(self.screen, (70, 100, 140), row_rect)
                        pygame.draw.rect(self.screen, (100, 150, 200), row_rect, 2)
                        text_color = (255, 255, 255)
                        desc_color = (200, 200, 220)
                    elif i % 2 == 0:
                        # Alternating background
                        pygame.draw.rect(self.screen, (35, 35, 40), row_rect)
                        text_color = (230, 230, 230)
                        desc_color = (150, 150, 150)
                    else:
                        text_color = (230, 230, 230)
                        desc_color = (150, 150, 150)
                    
                    # Tier indicator
                    if i < 5:
                        tier_color = (100, 180, 100)  # Green - Tier 1
                    elif i < 9:
                        tier_color = (180, 180, 100)  # Yellow - Tier 2
                    else:
                        tier_color = (180, 100, 100)  # Red - Tier 3
                    
                    pygame.draw.circle(self.screen, tier_color, (list_area.left + 15, y + item_height//2), 6)
                    
                    # Pattern name
                    name_txt = self.font.render(name, True, text_color)
                    self.screen.blit(name_txt, (list_area.left + 30, y + 8))
                    
                    # Description
                    desc_txt = self.fontS.render(desc, True, desc_color)
                    self.screen.blit(desc_txt, (list_area.left + 30, y + 28))
            
            # Restore clip
            self.screen.set_clip(clip_rect)
            
            # Scroll indicator
            if max_scroll > 0:
                scroll_pct = scroll_offset / max_scroll
                indicator_h = 30
                indicator_y = list_area.top + int((list_area.height - indicator_h) * scroll_pct)
                pygame.draw.rect(self.screen, (80, 80, 100), 
                               (list_area.right - 8, indicator_y, 6, indicator_h), border_radius=3)
            
            # Tier legend
            legend_y = box.bottom - 90
            legend_items = [("●", (100, 180, 100), "Tier 1"), 
                          ("●", (180, 180, 100), "Tier 2"), 
                          ("●", (180, 100, 100), "Tier 3")]
            x = box.left + 40
            for dot, color, label in legend_items:
                pygame.draw.circle(self.screen, color, (x, legend_y + 8), 6)
                lbl = self.fontS.render(label, True, (180, 180, 180))
                self.screen.blit(lbl, (x + 12, legend_y))
                x += 100
            
            # Cancel button
            pygame.draw.rect(self.screen, (100, 60, 60), cancel_btn, border_radius=8)
            pygame.draw.rect(self.screen, (160, 120, 120), cancel_btn, 2, border_radius=8)
            cancel_txt = self.font.render("Cancel", True, (240, 240, 240))
            self.screen.blit(cancel_txt, (cancel_btn.centerx - cancel_txt.get_width()//2, 
                                         cancel_btn.centery - cancel_txt.get_height()//2))
            
            pygame.display.flip()
            clock.tick(30)
        
        self.needs_redraw = True
        return None

    def _modal_location(self, existing):
        """Update location with OK/Cancel buttons and built-in keyboard"""
        W,H=460,340; box=pygame.Rect(self.sw//2-W//2,self.sh//2-H//2,W,H)
        txt=existing; typing=True; clock=pygame.time.Clock()
        bg_surface = self.screen.copy()
        
        # Button rectangles
        btn_w = 140
        btn_h = 45
        
        # Keyboard button (middle)
        kbd_btn = pygame.Rect(box.centerx - 100, box.top + 160, 200, 40)
        
        # OK and Cancel buttons (bottom)
        btn_y = box.bottom - btn_h - 15
        ok_btn = pygame.Rect(box.left + 40, btn_y, btn_w, btn_h)
        cancel_btn = pygame.Rect(box.right - btn_w - 40, btn_y, btn_w, btn_h)
        
        while typing:
            for ev in pygame.event.get():
                if ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_RETURN:
                        self.keyboard.hide()
                        return txt
                    elif ev.key==pygame.K_ESCAPE:
                        self.keyboard.hide()
                        return existing
                    elif ev.key==pygame.K_BACKSPACE: 
                        txt=txt[:-1]
                    else:
                        if ev.unicode and ev.unicode.isprintable() and len(txt)<24: 
                            txt+=ev.unicode
                elif ev.type==pygame.QUIT:
                    self.keyboard.hide()
                    return existing
                elif ev.type==pygame.MOUSEBUTTONDOWN:
                    # Check keyboard first
                    key_pressed = self.keyboard.handle_click(ev.pos)
                    if key_pressed:
                        if key_pressed == '\b':  # Backspace
                            txt = txt[:-1]
                        elif len(txt) < 24:
                            txt += key_pressed
                    elif ok_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        return txt
                    elif cancel_btn.collidepoint(ev.pos):
                        self.keyboard.hide()
                        return existing
                    elif kbd_btn.collidepoint(ev.pos):
                        self.keyboard.toggle()
            
            self.screen.blit(bg_surface, (0,0))
            pygame.draw.rect(self.screen,(25,25,28),box,border_radius=10)
            pygame.draw.rect(self.screen,(120,120,150),box,2,border_radius=10)
            
            title=self.big.render("Update Location",True,TEXT_COLOR)
            self.screen.blit(title,(box.centerx-title.get_width()//2, box.top+18))
            
            # Text box
            input_box=pygame.Rect(box.left+20,box.top+70,box.width-40,60)
            pygame.draw.rect(self.screen,(10,10,12),input_box,border_radius=8)
            pygame.draw.rect(self.screen,(120,140,200),input_box,2,border_radius=8)
            
            t2=self.big.render(txt + "|",True,(240,240,240))
            self.screen.blit(t2,(input_box.left+12, input_box.top+16))
            
            # Keyboard button
            kbd_color = (70,70,120) if not self.keyboard.visible else (100,140,100)
            pygame.draw.rect(self.screen,kbd_color,kbd_btn,border_radius=8)
            pygame.draw.rect(self.screen,(140,140,180),kbd_btn,2,border_radius=8)
            kbd_txt=self.font.render("Show Keyboard" if not self.keyboard.visible else "Hide Keyboard",True,(240,240,240))
            self.screen.blit(kbd_txt,(kbd_btn.centerx-kbd_txt.get_width()//2, kbd_btn.centery-kbd_txt.get_height()//2))
            
            # OK button
            pygame.draw.rect(self.screen,(60,100,60),ok_btn,border_radius=8)
            pygame.draw.rect(self.screen,(120,160,120),ok_btn,2,border_radius=8)
            ok_txt=self.big.render("OK",True,(240,240,240))
            self.screen.blit(ok_txt,(ok_btn.centerx-ok_txt.get_width()//2, ok_btn.centery-ok_txt.get_height()//2))
            
            # Cancel button
            pygame.draw.rect(self.screen,(100,60,60),cancel_btn,border_radius=8)
            pygame.draw.rect(self.screen,(160,120,120),cancel_btn,2,border_radius=8)
            cancel_txt=self.big.render("Cancel",True,(240,240,240))
            self.screen.blit(cancel_txt,(cancel_btn.centerx-cancel_txt.get_width()//2, cancel_btn.centery-cancel_txt.get_height()//2))
            
            # Draw keyboard last (on top)
            self.keyboard.draw()
            
            pygame.display.flip()
            clock.tick(30)
        
        self.keyboard.hide()
        self.needs_redraw = True
        return txt

    # ---------- Draw ----------
    def _draw_topbar(self):
        # Clear topbar area first to prevent ghosting
        topbar_rect = pygame.Rect(0, 0, self.sw, TOPBAR_H)
        self.screen.fill(BG_COLOR, topbar_rect)
        
        # Highlight current screen button
        self.b_live.active = (self.screen_id == self.DASH)
        self.b_stats.active = (self.screen_id == self.LOG)
        self.b_poem.active = (self.screen_id == self.POEM)
        
        for b,warn in [(self.b_live,False),(self.b_stats,False),(self.b_poem,False),(self.b_generate,False)]:
            b.draw(self.screen, self.big, warn=warn)
        
        # Don't show generation progress in topbar - it's shown in main screen
        
        if self.quit_confirm_active:
            confirm_text = "Tap center again to quit"
            msg = self.big.render(confirm_text, True, (255, 100, 100))
            msg_x = (self.sw - msg.get_width()) // 2
            msg_y = TOPBAR_H // 2 - msg.get_height() // 2
            self.screen.blit(msg, (msg_x, msg_y))
        
        # Draw zoom buttons only on dashboard
        if self.screen_id == self.DASH:
            self.b_zoom_out.draw(self.screen, self.big, warn=False)
            self.b_zoom_in.draw(self.screen, self.big, warn=False)
            
            # Show zoom level
            zoom_level_text = self.fontS.render(f"{self.dash_y_zoom:.1f}x", True, (180, 200, 220))
            self.screen.blit(zoom_level_text, (self.b_zoom_out.rect.left - zoom_level_text.get_width() - 8, self.b_zoom_out.rect.centery - zoom_level_text.get_height()//2))
        
        now=time.time()
        elapsed = self.elapsed_pause + ((now-self.log_t0) if self.log_t0 else 0)
        el=self.big.render(f"{fmt_hms(elapsed)}",True,(200,220,255))
        # Position timer below button bar on the right
        timer_x = self.sw - el.get_width() - 10
        timer_y = TOPBAR_H + 5
        self.screen.blit(el,(timer_x, timer_y))

    def _smooth_range(self,key,lo,hi,min_span,clamp):
        prev=self.y_dyn[key]
        if prev[0] is None:
            self.y_dyn[key]=[lo,hi]; return lo,hi
        # If new range is completely outside previous, jump immediately
        if hi < prev[0] or lo > prev[1]:
            self.y_dyn[key]=[lo,hi]; return lo,hi
        new_lo=(1-Y_SMOOTH_ALPHA)*prev[0]+Y_SMOOTH_ALPHA*lo
        new_hi=(1-Y_SMOOTH_ALPHA)*prev[1]+Y_SMOOTH_ALPHA*hi
        span=max(1e-9,prev[1]-prev[0]); max_step=span*Y_MAX_STEP_FRAC
        new_lo = prev[0] + clampf(new_lo-prev[0], -max_step, max_step)
        new_hi = prev[1] + clampf(new_hi-prev[1], -max_step, max_step)
        new_lo=max(clamp[0],new_lo); new_hi=min(clamp[1],new_hi)
        if new_hi-new_lo<min_span:
            mid=0.5*(new_hi+new_lo); new_lo=max(clamp[0],mid-0.5*min_span); new_hi=min(clamp[1],mid+0.5*min_span)
        self.y_dyn[key]=[new_lo,new_hi]; return new_lo,new_hi

    def _apply_yzoom(self,key,lo,hi,min_span,clamp):
        mid=0.5*(lo+hi); span=max(min_span,(hi-lo)*self.y_zoom[key])
        lo=max(clamp[0],mid-0.5*span); hi=min(clamp[1],mid+0.5*span)
        if hi-lo<min_span:
            mid=0.5*(hi+lo); lo=max(clamp[0],mid-0.5*min_span); hi=min(clamp[1],mid+0.5*min_span)
        return lo,hi

    def _draw(self, overlay_ecg=False, base_only=False):
        self.screen.fill(BG_COLOR)
        
        # On poem screen with UI hidden, skip topbar and status
        if self.screen_id == self.POEM and not self.poem_ui_visible:
            self._draw_poem()
            pygame.display.flip()
            return
        
        self._draw_topbar()

        # Normal display based on screen (ECG overlay removed - no voltage sensor)
        if self.screen_id==self.LOG:
            self._draw_logger()
        elif self.screen_id==self.DASH:
            self._draw_dashboard()
        else:
            self._draw_poem()

        # Add sensor status to status bar (simplified)
        stxt=f"{'LOGGING' if self.logging else 'PAUSED'}"
        
        # Reset flash after 150ms
        if self.led_quit_flash_time > 0 and (time.time() - self.led_quit_flash_time) > 0.15:
            self.led_quit_flash_time = 0
        
        # Choose color based on quit state
        if self.led_quit_flash_time > 0:
            # Flash white on rapid taps
            text_color = (255, 255, 255)
        elif self.quit_confirm_active:
            # Red during quit confirmation
            text_color = (255, 100, 100)
        else:
            text_color = TEXT_COLOR
        
        s = self.font.render(stxt, True, text_color)
        
        # Draw status text and store rect for click detection
        status_y = self.sh - s.get_height() - 6
        self.logging_text_rect = pygame.Rect(PANEL_MARGIN, status_y, s.get_width(), s.get_height())
        self.screen.blit(s, (PANEL_MARGIN, status_y))
        
        # Show quit confirmation message above LOGGING text
        if self.quit_confirm_active:
            quit_msg = "TAP AGAIN TO QUIT"
            quit_surf = self.fontS.render(quit_msg, True, (255, 100, 100))
            self.screen.blit(quit_surf, (PANEL_MARGIN, status_y - 25))
        
        # LED button at right side of status bar
        led_text = "LED"
        led_width = self.font.size(led_text)[0]
        led_x = self.sw - PANEL_MARGIN - led_width - 16
        
        # Store LED button rect for click detection
        self.led_btn_rect = pygame.Rect(led_x - 8, status_y - 4, led_width + 16, s.get_height() + 8)
        
        # Choose background color: green for active, or dark default
        if self.sensors._led_pulsing:
            # Green if LED is active
            pygame.draw.rect(self.screen, (40, 140, 40), self.led_btn_rect, border_radius=4)
            pygame.draw.rect(self.screen, (80, 200, 80), self.led_btn_rect, 2, border_radius=4)
            led_color = (255, 255, 255)
        else:
            # Dark default
            pygame.draw.rect(self.screen, (40, 50, 60), self.led_btn_rect, border_radius=4)
            pygame.draw.rect(self.screen, (80, 100, 120), self.led_btn_rect, 1, border_radius=4)
            led_color = TEXT_COLOR
        
        led_surf = self.font.render(led_text, True, led_color)
        self.screen.blit(led_surf, (led_x, status_y))
        
        # Draw email confirmation dialog if shown

        
        pygame.display.flip()



    def _draw_logger(self):
        tmax=self.view_right; tmin=tmax-self.view_span
        li,ri=self.store.window_indices(tmax,self.view_span)
        ts=list(self.store.t)[li:ri+1]
        vs=list(self.store.v)[li:ri+1]
        mps=list(self.store.mp)[li:ri+1]
        tcs=list(self.store.tc)[li:ri+1]
        hus=list(self.store.hu)[li:ri+1]
        prs=list(self.store.pr)[li:ri+1]
        lxs=list(self.store.lx)[li:ri+1]
        marks=list(self.store.mark)[li:ri+1] if self.store.mark else None

        v_bad=[is_outlier(x,V_ABS_RANGE) if x is not None else False for x in vs]
        mp_bad=[is_outlier(x,MP_ABS_RANGE) if x is not None else False for x in mps]
        tc_bad=[is_outlier(x,TC_ABS_RANGE) if x is not None else False for x in tcs]
        hu_bad=[is_outlier(x,HU_ABS_RANGE) if x is not None else False for x in hus]
        pr_bad=[is_outlier(x,PR_ABS_RANGE) if x is not None else False for x in prs]
        lx_bad=[is_outlier(x,LX_ABS_RANGE) if x is not None else False for x in lxs]

        # moisture centre panel is percentage with large overlay text
        mp_mid=50.0; mp_span=100.0*self.y_zoom["mp"]
        y2lo,y2hi=max(MP_CLAMP[0],mp_mid-0.5*mp_span), min(MP_CLAMP[1],mp_mid+0.5*mp_span)
        y2lo,y2hi=self._smooth_range("mp",y2lo,y2hi,MP_MIN_SPAN,MP_CLAMP)

        lx_for=[x if not lx_bad[i] else None for i,x in enumerate(lxs)]
        # Better default range for lux - if all values are low, use appropriate scale
        lx_valid = [x for x in lx_for if x is not None]
        if lx_valid:
            lx_max = max(lx_valid)
            if lx_max < 50:  # Very low light
                lx_default = (0.0, 50.0)
            elif lx_max < 200:  # Indoor lighting
                lx_default = (0.0, 200.0)
            else:  # Bright light
                lx_default = (0.0, max(500.0, lx_max * 1.2))
        else:
            lx_default = (0.0, 100.0)
        
        llo,lhi,_=adaptive_range(lx_for, default=lx_default, min_span=LX_MIN_SPAN, pad_frac=0.10, clamp=LX_CLAMP)
        llo,lhi=self._smooth_range("lx",llo,lhi,LX_MIN_SPAN,LX_CLAMP)
        llo,lhi=self._apply_yzoom("lx",llo,lhi,LX_MIN_SPAN,LX_CLAMP)

        tc_for=[x if not tc_bad[i] else None for i,x in enumerate(tcs)]
        tlo,thi,_=adaptive_range(tc_for, default=(15.0,30.0), min_span=TC_MIN_SPAN, pad_frac=0.10, clamp=TC_CLAMP)
        tlo,thi=self._smooth_range("tc",tlo,thi,TC_MIN_SPAN,TC_CLAMP)
        tlo,thi=self._apply_yzoom("tc",tlo,thi,TC_MIN_SPAN,TC_CLAMP)
        
        # Humidity range
        hu_for=[x if not hu_bad[i] else None for i,x in enumerate(hus)]
        hlo,hhi,_=adaptive_range(hu_for, default=(20.0,60.0), min_span=HU_MIN_SPAN, pad_frac=0.10, clamp=HU_CLAMP)
        hlo,hhi=self._smooth_range("hu",hlo,hhi,HU_MIN_SPAN,HU_CLAMP)
        hlo,hhi=self._apply_yzoom("hu",hlo,hhi,HU_MIN_SPAN,HU_CLAMP)
        
        # Pressure range
        pr_for=[x if not pr_bad[i] else None for i,x in enumerate(prs)]
        plo,phi,_=adaptive_range(pr_for, default=(990.0,1020.0), min_span=PR_MIN_SPAN, pad_frac=0.10, clamp=PR_CLAMP)
        plo,phi=self._smooth_range("pr",plo,phi,PR_MIN_SPAN,PR_CLAMP)
        plo,phi=self._apply_yzoom("pr",plo,phi,PR_MIN_SPAN,PR_CLAMP)

        # session markers
        sess=set()
        for s,e in self.store.sessions:
            if tmin<=s<=tmax: sess.add(s)
            if tmin<=e<=tmax: sess.add(e)
        sess=sorted(sess)

        # ===== TOP PANEL: Temperature =====
        self.screen.set_clip(self.p1)
        span=f"span {fmt_hms(self.view_span)}"
        draw_grid(self.screen, self.p1, tlo, thi, "Air Temp (°C)", span, self.font, self.fontS)
        draw_session_marks(self.screen, self.p1, sess, tmin, tmax, SESSION_COLOR)
        plot_series(self.screen, self.p1, ts, tcs, tmin, tmax, tlo, thi, 
                   (255, 180, 150), dot_color=(255, 200, 180), marks=marks, out_mask=tc_bad)
        
        # Show current temp + humidity values
        if self.store.tc and self.store.tc[-1] is not None:
            tval = self.huge.render(f"{self.store.tc[-1]:.1f}°", True, (255, 200, 180))
            self.screen.blit(tval, (self.p1.centerx - tval.get_width()//2 - 60, self.p1.centery - tval.get_height()//2))
        if self.store.hu and self.store.hu[-1] is not None:
            hval = self.big.render(f"{self.store.hu[-1]:.0f}% RH", True, (150, 200, 255))
            self.screen.blit(hval, (self.p1.centerx + 50, self.p1.centery - hval.get_height()//2))
        self.screen.set_clip(None)

        # left middle: moisture
        self.screen.set_clip(self.p2)
        draw_grid(self.screen,self.p2,y2lo,y2hi,"Soil Moist (%)",None,self.font,self.fontS)
        draw_session_marks(self.screen,self.p2,sess,tmin,tmax,SESSION_COLOR)
        plot_series(self.screen,self.p2,ts,mps,tmin,tmax,y2lo,y2hi,(200,230,160),dot_color=(210,255,180),marks=marks,out_mask=mp_bad)
        if self.store.mp and len(self.store.mp) > 0:
            lpct=self.store.mp[-1]
            lraw=self.store.mr[-1] if self.store.mr else None
            if lpct is not None:
                t=self.huge.render(f"{lpct:.0f}%",True,(220,255,210))
                self.screen.blit(t,(self.p2.centerx-t.get_width()//2, self.p2.centery-t.get_height()//2-18))
            sub=self.font.render(f"raw {int(lraw) if lraw is not None else '---'}",True,(200,220,200))
            self.screen.blit(sub,(self.p2.centerx-sub.get_width()//2, self.p2.centery+12))
        self.screen.set_clip(None)

        # right middle: lux
        self.screen.set_clip(self.pLux)
        draw_grid(self.screen,self.pLux,llo,lhi,"Ambient Lux (lx)",None,self.font,self.fontS)
        draw_session_marks(self.screen,self.pLux,sess,tmin,tmax,SESSION_COLOR)
        plot_series(self.screen,self.pLux,ts,lxs,tmin,tmax,llo,lhi,(200,220,255),marks=marks,out_mask=lx_bad)
        
        # Show current lux value - use most recent valid from lxs
        lx_valid = [x for x in lxs if x is not None]
        if lx_valid:
            lval=self.huge.render(f"{lx_valid[-1]:.0f}",True,(220,235,255))
            self.screen.blit(lval,(self.pLux.centerx-lval.get_width()//2, self.pLux.centery-lval.get_height()//2-18))
            sub=self.font.render("lux",True,(200,220,240))
            self.screen.blit(sub,(self.pLux.centerx-sub.get_width()//2, self.pLux.centery+12))
        
        self.screen.set_clip(None)

        # bottom: Pressure (hPa)
        self.screen.set_clip(self.pTemp)
        draw_grid(self.screen,self.pTemp,plo,phi,"Pressure (hPa)",None,self.font,self.fontS)
        draw_session_marks(self.screen,self.pTemp,sess,tmin,tmax,SESSION_COLOR)
        plot_series(self.screen,self.pTemp,ts,prs,tmin,tmax,plo,phi,(200,220,255),dot_color=(220,230,255),marks=marks,out_mask=pr_bad)
        if self.store.pr and self.store.pr[-1] is not None:
            pval=self.huge.render(f"{self.store.pr[-1]:.0f}",True,(200,220,255))
            self.screen.blit(pval,(self.pTemp.centerx-pval.get_width()//2, self.pTemp.centery-pval.get_height()//2))
            sub=self.font.render("hPa",True,(180,200,240))
            self.screen.blit(sub,(self.pTemp.centerx+pval.get_width()//2+10, self.pTemp.centery))
        self.screen.set_clip(None)

    def _pct_out(self, vals, clamp):
        vv=[x for x in vals if x is not None]
        if not vv: return 0.0
        n=sum(1 for x in vv if (x<clamp[0] or x>clamp[1])); return n/len(vv)

    def _draw_dashboard(self):
        # Fill entire panel areas with solid opaque black first (no border_radius)
        self.screen.fill((0,0,0), self.p1)
        self.screen.fill((0,0,0), self.p2)
        self.screen.fill((0,0,0), self.pLux)
        self.screen.fill((0,0,0), self.pTemp)
        
        # Draw LIVE badge
        live=self.big.render("LIVE",True,LIVE_HILITE)
        
        self.screen.blit(live,(self.p1.left+8, self.p1.top+8))

        # ===== TOP PANEL: Temperature + Humidity (BME280) =====
        self.screen.set_clip(self.p1)
        badge=self.font.render("ENVIRONMENT",True,LIVE_HILITE)
        self.screen.blit(badge,(self.p1.centerx-badge.get_width()//2, self.p1.top+10))
        
        # Get averaged samples for stability
        tc_samples = [x for x in list(self.dash["tc"])[-5:] if x is not None]
        hu_samples = [x for x in list(self.dash["hu"])[-5:] if x is not None]
        tc = mean(tc_samples) if tc_samples else None
        hu = mean(hu_samples) if hu_samples else None
        
        if tc is not None and hu is not None:
            # Display temperature and humidity side by side
            # Left side: Temperature
            temp_x = self.p1.centerx - 120
            tval = self.huge.render(f"{tc:.1f}°", True, (255, 180, 150))
            self.screen.blit(tval, (temp_x - tval.get_width()//2, self.p1.centery - tval.get_height()//2 - 10))
            tsub = self.font.render("temp °C", True, (200, 160, 140))
            self.screen.blit(tsub, (temp_x - tsub.get_width()//2, self.p1.centery + 30))
            
            # Right side: Humidity
            hu_x = self.p1.centerx + 120
            hval = self.huge.render(f"{hu:.0f}%", True, (150, 200, 255))
            self.screen.blit(hval, (hu_x - hval.get_width()//2, self.p1.centery - hval.get_height()//2 - 10))
            hsub = self.font.render("humidity", True, (130, 180, 220))
            self.screen.blit(hsub, (hu_x - hsub.get_width()//2, self.p1.centery + 30))
        elif tc is not None:
            tval = self.huge.render(f"{tc:.1f}°C", True, (255, 180, 150))
            self.screen.blit(tval, (self.p1.centerx - tval.get_width()//2, self.p1.centery - tval.get_height()//2))
        else:
            wait_text = self.big.render("Reading BME280...", True, (150, 150, 150))
            self.screen.blit(wait_text, (self.p1.centerx - wait_text.get_width()//2, self.p1.centery - wait_text.get_height()//2))
        
        self.screen.set_clip(None)

        # ===== LEFT MIDDLE: Soil Moisture =====
        # Fill panel background before drawing
        self.screen.fill((0,0,0), self.p2)
        
        mp_samples = [x for x in list(self.dash["mp"])[-5:] if x is not None]
        mp = mean(mp_samples) if mp_samples else None
        
        badge=self.font.render("SOIL MOISTURE",True,LIVE_HILITE)
        self.screen.blit(badge,(self.p2.centerx-badge.get_width()//2, self.p2.top+10))
        
        if mp is not None:
            # Color based on moisture level
            if mp < 30:
                mp_color = (255, 150, 100)  # Orange/dry
            elif mp > 80:
                mp_color = (100, 200, 255)  # Blue/wet
            else:
                mp_color = (150, 255, 150)  # Green/good
            
            mpct=self.huge.render(f"{mp:.0f}%",True, mp_color)
            self.screen.blit(mpct,(self.p2.centerx-mpct.get_width()//2, self.p2.centery-mpct.get_height()//2-10))
            
            # Show status text
            if mp < 30:
                status = "Needs water!"
            elif mp > 80:
                status = "Well watered"
            else:
                status = "Good"
            sub=self.font.render(status,True,(200,220,200))
            self.screen.blit(sub,(self.p2.centerx-sub.get_width()//2, self.p2.centery+40))
        else:
            wait_text = self.big.render("Reading...", True, (150, 150, 150))
            self.screen.blit(wait_text, (self.p2.centerx - wait_text.get_width()//2, self.p2.centery - wait_text.get_height()//2))

        # ===== RIGHT MIDDLE: Light (lux) =====
        lx_samples = [x for x in list(self.dash["lx"])[-5:] if x is not None]
        lx = mean(lx_samples) if lx_samples else None
        
        # Fill panel background before drawing
        self.screen.fill((0,0,0), self.pLux)
        
        badge=self.font.render("LIGHT",True,LIVE_HILITE)
        self.screen.blit(badge,(self.pLux.centerx-badge.get_width()//2, self.pLux.top+10))
        
        if lx is not None:
            lval=self.huge.render(f"{lx:.0f}",True,(255,255,180))
            self.screen.blit(lval,(self.pLux.centerx-lval.get_width()//2, self.pLux.centery-lval.get_height()//2-10))
            sub=self.big.render("lux",True,(230,230,150))
            self.screen.blit(sub,(self.pLux.centerx-sub.get_width()//2, self.pLux.centery+30))
        else:
            wait_text = self.big.render("Reading...", True, (150, 150, 150))
            self.screen.blit(wait_text, (self.pLux.centerx - wait_text.get_width()//2, self.pLux.centery - wait_text.get_height()//2))

        # ===== BOTTOM: Pressure (hPa) =====
        # Fill panel background before drawing
        self.screen.fill((0,0,0), self.pTemp)
        
        pr_samples = [x for x in list(self.dash["pr"])[-5:] if x is not None]
        pr = mean(pr_samples) if pr_samples else None
        
        badge=self.font.render("PRESSURE",True,LIVE_HILITE)
        self.screen.blit(badge,(self.pTemp.centerx-badge.get_width()//2, self.pTemp.top+10))
        
        if pr is not None:
            pval=self.huge.render(f"{pr:.0f}",True,(200,220,255))
            self.screen.blit(pval,(self.pTemp.centerx-pval.get_width()//2, self.pTemp.centery-pval.get_height()//2))
            sub=self.font.render("hPa",True,(180,200,240))
            self.screen.blit(sub,(self.pTemp.centerx+pval.get_width()//2+10, self.pTemp.centery))
        else:
            wait_text = self.big.render("Reading...", True, (150, 150, 150))
            self.screen.blit(wait_text, (self.pTemp.centerx - wait_text.get_width()//2, self.pTemp.centery - wait_text.get_height()//2))

    def _dash_sample(self):
        try:
            v=self.sensors.read_v()
            m=self.sensors.read_mraw()
            # Read all BME280 values at once
            tc, hu, pr = self.sensors.read_bme_all()
            l=self.sensors.read_lx()
            ts=time.time()
            self.dash["t"].append(ts)
            self.dash["v"].append(v if v is not None else None)
            self.dash["mp"].append(moisture_pct_from_raw(m) if m is not None else None)
            self.dash["tc"].append(tc if tc is not None else None)
            self.dash["hu"].append(hu if hu is not None else None)
            self.dash["pr"].append(pr if pr is not None else None)
            self.dash["lx"].append(l if l is not None else None)
        except Exception as e:
            # If sampling fails, just skip this sample
            pass

    def _generate_poems_thread(self):
        """Background thread to generate poems (manual Gen button, G key for daily, or W key for weekly)"""
        print("[DEBUG] Manual poem generation thread started!")
        
        # Start LED pulsation during generation
        try:
            self.sensors.start_poem_pulsation()
            print("[DEBUG] LED pulsation started")
        except Exception as e:
            print(f"[DEBUG] LED pulsation failed to start: {e}")
        
        try:
            # Check generation mode (daily or weekly)
            mode = getattr(self, 'poem_generation_mode', 'daily')
            force_visual = getattr(self, 'force_visual_generation', False)
            force_standard = getattr(self, 'force_standard_generation', False)
            selected_pattern = getattr(self, 'selected_visual_pattern', None)
            print(f"[DEBUG] Generation mode: {mode}, force_visual: {force_visual}, force_standard: {force_standard}, selected_pattern: {selected_pattern}")
            
            self.generation_log.append("> Analyzing sensor data...")
            self.needs_redraw = True
            pygame.time.wait(500)
            
            print("[DEBUG] Creating DailyPoetryGenerator...")
            gen = DailyPoetryGenerator(CSV_PATH)
            
            if mode == "weekly":
                self.generation_log.append("> Processing 7-day data window...")
                self.needs_redraw = True
                pygame.time.wait(500)
                print("[DEBUG] Generating WEEKLY poem prompt...")
                prompt_data = gen.generate_weekly_poem_prompt()
            else:
                self.generation_log.append("> Processing 24-hour data window...")
                self.needs_redraw = True
                pygame.time.wait(500)
                print("[DEBUG] Generating DAILY poem prompt...")
                prompt_data = gen.generate_daily_poem_prompt(force_visual=force_visual, selected_pattern=selected_pattern, force_standard=force_standard)
            
            # Clear the force_visual flag after use
            if hasattr(self, 'force_visual_generation'):
                self.force_visual_generation = False
            
            # Clear the force_standard flag after use
            if hasattr(self, 'force_standard_generation'):
                self.force_standard_generation = False
            
            # Clear the selected_visual_pattern after use
            if hasattr(self, 'selected_visual_pattern'):
                self.selected_visual_pattern = None
            
            # Show sensor readings
            metadata = prompt_data.get('metadata', {})
            sensor_summary = prompt_data.get('sensor_summary', {})
            
            self.generation_log.append("")
            self.generation_log.append("> Sensor readings:")
            
            # Get sensor data directly from CSV
            try:
                import pandas as pd
                print(f"[DEBUG] Reading CSV from: {CSV_PATH}")
                df = pd.read_csv(CSV_PATH)
                print(f"[DEBUG] CSV has {len(df)} rows")
                if len(df) > 0:
                    latest = df.iloc[-1]
                    print(f"[DEBUG] Latest row columns: {list(latest.index)}")
                    if 'soil_pct_avg' in latest:
                        moisture = latest['soil_pct_avg']
                        self.generation_log.append(f">   Moisture: {moisture:.1f}%")
                        print(f"[DEBUG] Moisture: {moisture}%")
                    else:
                        print("[DEBUG] No soil_pct_avg column")
                        self.generation_log.append(">   Moisture: (not found)")
                    if 'lux_lx_avg' in latest:
                        lux = latest['lux_lx_avg']
                        self.generation_log.append(f">   Light: {lux:.0f} lux")
                        print(f"[DEBUG] Light: {lux} lux")
                    else:
                        print("[DEBUG] No lux_lx_avg column")
                        self.generation_log.append(">   Light: (not found)")
                    if 'temp_C_avg' in latest:
                        temp = latest['temp_C_avg']
                        self.generation_log.append(f">   Temperature: {temp:.1f}C")
                        print(f"[DEBUG] Temperature: {temp}C")
                    if 'humidity_pct_avg' in latest:
                        humidity = latest['humidity_pct_avg']
                        self.generation_log.append(f">   Humidity: {humidity:.1f}%")
                        print(f"[DEBUG] Humidity: {humidity}%")
                    if 'pressure_hPa_avg' in latest:
                        pressure = latest['pressure_hPa_avg']
                        self.generation_log.append(f">   Pressure: {pressure:.1f} hPa")
                        print(f"[DEBUG] Pressure: {pressure} hPa")
                else:
                    self.generation_log.append(">   (no data in CSV)")
            except Exception as e:
                print(f"[DEBUG] Failed to read sensor data from CSV: {e}")
                import traceback
                traceback.print_exc()
                self.generation_log.append(">   (sensor data error)")
                
            self.needs_redraw = True
            pygame.time.wait(600)
            
            # Show theme and poet
            self.generation_log.append("")
            theme = metadata.get('primary_theme', 'unknown')
            theme_score = metadata.get('theme_score', 0)
            poet = metadata.get('poet', 'unknown')
            
            self.generation_log.append(f"> Theme: {theme} (score: {theme_score:.2f})")
            self.generation_log.append(f"> Poet: {poet}")
            self.needs_redraw = True
            pygame.time.wait(600)
            
            # Extract the actual prompt string from the dict
            prompt = prompt_data['prompt'] if isinstance(prompt_data, dict) else prompt_data
            print(f"[DEBUG] Prompt: {prompt[:100]}...")
            
            self.generation_log.append("")
            prompt_length = len(prompt)
            self.generation_log.append(f"> Prompt: {prompt_length} characters")
            self.needs_redraw = True
            pygame.time.wait(300)
            # Wrap entire prompt to multiple lines - calculate based on screen width
            prompt_text = prompt.replace('\n', ' ')
            # Calculate max characters per line based on screen width and font metrics
            # Available width = screen_width - margins (60px left + 60px right)
            available_width = self.sw - 120
            # Get average character width for monospace font
            sample_text = "M" * 10  # Monospace, so any char works
            sample_surf = self.fontS.render(sample_text, True, (255, 255, 255))
            char_width = sample_surf.get_width() / 10
            line_length = int(available_width / char_width) - 4  # -4 for ">   " prefix
            for i in range(0, len(prompt_text), line_length):
                chunk = prompt_text[i:i+line_length]
                self.generation_log.append(f">   {chunk}")
                self.needs_redraw = True
                pygame.time.wait(200)
            self.generation_log.append("")
            self.generation_log.append("> Sending to Claude API...")
            self.generation_log.append("> (this may take 5-15 seconds)")
            self.needs_redraw = True
            pygame.time.wait(500)
            
            print("[DEBUG] Creating Claude API client...")
            from api_client import PoemAPIClient
            import time
            start_time = time.time()
            client = PoemAPIClient("anthropic")
            print("[DEBUG] Calling generate_poem()...")
            claude_result = client.generate_poem(prompt)
            elapsed = time.time() - start_time
            print(f"[DEBUG] Claude result: {claude_result.get('success', False)}")
            
            self.generation_log.append("")
            self.generation_log.append(f"> Response received in {elapsed:.1f}s")
            self.needs_redraw = True
            pygame.time.wait(400)
            
            if claude_result.get('success'):
                raw_poem = claude_result.get('poem')
                self.poem_prompt_data = prompt_data  # Store for retroactive uploads
                poem_type = prompt_data.get('poem_type', 'daily')
                
                self.generation_log.append("> Extracting poem from response...")
                self.needs_redraw = True
                pygame.time.wait(400)
                
                print(f"[DEBUG] {poem_type.upper()} poem generated successfully!")
                
                # Build structured footnote (replace Claude's simple footnote)
                self.generation_log.append("> Building footnote...")
                self.needs_redraw = True
                pygame.time.wait(400)
                
                print("[DEBUG] Building structured footnote...")
                try:
                    # Extract title from poem
                    poem_lines = raw_poem.split('\n')
                    title = poem_lines[0].strip() if poem_lines else "untitled"
                    # Strip markdown formatting from title
                    title = title.replace('**', '').replace('*', '')
                    
                    # Remove Claude's footnote (various formats)
                    clean_lines = []
                    for line in poem_lines:
                        stripped = line.strip()
                        # Stop at separator or any footnote format
                        if stripped.startswith('---') or stripped.startswith('*Biopoem') or 'Living plant sensor data' in stripped or stripped.startswith('['):
                            break
                        # Strip markdown formatting (asterisks for bold/italic)
                        cleaned_line = line.replace('**', '').replace('*', '')
                        clean_lines.append(cleaned_line)
                    
                    clean_poem = '\n'.join(clean_lines).strip()
                    
                    # Build structured footnote using poetry_engine method
                    metadata = prompt_data.get('metadata', {})
                    sensor_summary = prompt_data.get('sensor_summary', {})
                    
                    # Get proper datetime object for date
                    gen_date = metadata.get('generation_date')
                    if isinstance(gen_date, str):
                        # Parse if it's a string
                        try:
                            gen_date = datetime.fromisoformat(gen_date)
                        except:
                            gen_date = datetime.now()
                    elif gen_date is None:
                        gen_date = datetime.now()
                    
                    footnote_args = {
                        'date': gen_date,
                        'theme_analysis': {
                            'primary_theme': metadata.get('primary_theme'),
                            'primary_score': metadata.get('theme_score', 0.0),
                            'title': title,
                            'visual_pattern': metadata.get('visual_pattern', 'standard')
                        },
                        'influence_key': metadata.get('influence'),
                        'sensor_summary': sensor_summary,
                        'human_context': None,
                        'location_context': {'current': metadata.get('location', 'office')},
                        'multi_day_patterns': metadata.get('multi_day_patterns', [])
                    }
                    
                    structured_footnote = gen._build_footnote(**footnote_args)
                    
                    # Get the full prompt for display
                    full_prompt = prompt_data.get('prompt', '')
                    
                    # Combine clean poem with structured footnote and full prompt
                    # User can scroll down to see footnote and prompt
                    separator = '————————————————————————————————————————'
                    prompt_separator = '════════════════ FULL PROMPT ════════════════'
                    
                    # Add many blank lines so footnote is only visible after scrolling down
                    scroll_padding = '\n' * 30
                    
                    # Version for rendering/saving (NO prompt - just poem + footnote)
                    self.poem_for_render = clean_poem + '\n\n' + separator + '\n' + structured_footnote
                    
                    # Version for screen 3 display (includes prompt after scrolling)
                    self.poem_claude = clean_poem + scroll_padding + separator + '\n' + structured_footnote
                    if full_prompt:
                        self.poem_claude += '\n\n' + prompt_separator + '\n\n' + full_prompt
                    
                    print(f"[DEBUG] ✓ Added structured footnote and prompt")
                    
                except Exception as e:
                    print(f"[DEBUG] Failed to build structured footnote: {e}")
                    # Fall back to original poem
                    self.poem_claude = raw_poem
                
                # Alternate dark/light mode
                dark_mode = not self.last_generation_dark_mode
                self.last_generation_dark_mode = dark_mode
                mode_str = "DARK" if dark_mode else "LIGHT"
                print(f"[DEBUG] Using {mode_str} mode (alternating)")
                
                # Render Instagram images
                self.generation_log.append("")
                self.generation_log.append("> Rendering poem...")
                self.needs_redraw = True
                pygame.time.wait(400)
                
                print("[DEBUG] Rendering Instagram images...")
                try:
                    renderer = InstagramRenderer(output_dir="instagram_posts")
                    metadata = prompt_data.get('metadata', {})
                    
                    # Check if visual poem
                    is_visual = metadata.get('visual_pattern') and metadata.get('visual_pattern') != 'standard'
                    
                    # Use clean version without full prompt
                    text_to_render = self.poem_for_render if self.poem_for_render else self.poem_claude
                    has_prompt_separator = '════════════════ FULL PROMPT' in text_to_render
                    print(f"[DEBUG] Rendering with poem_for_render={bool(self.poem_for_render)}, has_prompt_in_text={has_prompt_separator}")
                    
                    if is_visual:
                        visual_pattern = metadata.get('visual_pattern')
                        print(f"[DEBUG] Rendering VISUAL poem with pattern: {visual_pattern}")
                        images = renderer.render_visual_poem(
                            poem_text=text_to_render,
                            layout_type=visual_pattern,
                            dark_mode=dark_mode
                        )
                    else:
                        print("[DEBUG] Rendering NORMAL poem (left-aligned)")
                        images = renderer.render_normal_poem(
                            poem_text=text_to_render,
                            metadata=metadata,
                            dark_mode=dark_mode
                        )
                    
                    print(f"[DEBUG] ✓ Rendered {len(images) if isinstance(images, list) else 'dict'} images:")
                    if isinstance(images, list):
                        for img in images:
                            print(f"[DEBUG]   {img}")
                    
                    self.generation_log.append("> Poem rendered")
                    self.needs_redraw = True
                    pygame.time.wait(400)
                    
                    # Store image paths for carousel display
                    poem_folder_path = renderer.output_dir
                    # images can be dict with 'dark'/'light' keys, or list (legacy)
                    if isinstance(images, dict):
                        # New format: {'dark': [poem, footnote], 'light': [poem, footnote]}
                        for mode in ['dark', 'light']:
                            if mode in images and images[mode]:
                                self.poem_image_paths[mode] = {}
                                for img_path in images[mode]:
                                    if 'footnote' in os.path.basename(img_path):
                                        self.poem_image_paths[mode]['footnote'] = img_path
                                    elif 'poem' in os.path.basename(img_path):
                                        self.poem_image_paths[mode]['poem'] = img_path
                                print(f"[DEBUG] Stored {mode} image paths: {self.poem_image_paths[mode]}")
                    else:
                        # Legacy format: list of image paths
                        mode = 'dark' if dark_mode else 'light'
                        self.poem_image_paths[mode] = {}
                        for img_path in images:
                            if 'footnote' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['footnote'] = img_path
                            elif 'poem' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['poem'] = img_path
                        print(f"[DEBUG] Stored {mode} image paths: {self.poem_image_paths[mode]}")
                    
                    # Render the creative prompt to same poem folder
                    try:
                        full_prompt = prompt_data.get('prompt', '')
                        if full_prompt:
                            creative_brief = InstagramRenderer.extract_creative_brief(full_prompt)
                            if creative_brief:
                                # Clean prompt: remove CRITICAL section
                                clean_lines = []
                                for line in creative_brief.split('\n'):
                                    if line.strip().startswith('CRITICAL:'):
                                        break
                                    clean_lines.append(line)
                                clean_prompt = '\n'.join(clean_lines).strip()
                                
                                # Get title from poem for filename
                                title = self.poem_claude.split('\n')[0].strip().replace('**', '').replace('*', '') if self.poem_claude else 'prompt'
                                # Render directly to the poem folder
                                prompt_paths = renderer.render_prompt_both_modes(clean_prompt, output_dir=poem_folder_path, title=title)
                                print(f"[DEBUG] ✓ Rendered prompt images: {prompt_paths}")
                                # Store prompt paths
                                if prompt_paths:
                                    for path in prompt_paths:
                                        if '_dark' in path:
                                            if 'dark' not in self.poem_image_paths:
                                                self.poem_image_paths['dark'] = {}
                                            self.poem_image_paths['dark']['prompt'] = path
                                        else:
                                            if 'light' not in self.poem_image_paths:
                                                self.poem_image_paths['light'] = {}
                                            self.poem_image_paths['light']['prompt'] = path
                    except Exception as e:
                        print(f"[DEBUG] Prompt rendering failed: {e}")
                        
                except Exception as e:
                    print(f"[DEBUG] Instagram rendering failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Record poem for diversity tracking
                try:
                    metadata = prompt_data.get('metadata', {})
                    gen.record_generated_poem(
                        poem_text=self.poem_claude,
                        theme=metadata.get('primary_theme', 'unknown'),
                        influence=metadata.get('influence', 'unknown'),
                        generation_date=metadata.get('generation_date')
                    )
                except Exception as e:
                    print(f"[DEBUG] Diversity tracking failed: {e}")
                
                # Clear image cache so new images will be loaded
                self.poem_images_loaded = {}
                print("[DEBUG] Cleared image cache for new poem")
                
                # Save to file
                self._save_latest_poem()
                
                # Update web gallery with latest folder
                latest_folder = os.path.basename(poem_folder_path) if poem_folder_path else None
                self._update_gallery(latest_poem_folder=latest_folder)
                
                # Log to CSV
                if self.poem_logger:
                    try:
                        self.poem_logger.log_generation(
                            poem_text=self.poem_claude,
                            prompt_data=prompt_data,
                            api_result=claude_result
                        )
                        count = self.poem_logger.get_generation_count()
                        print(f"[DEBUG] Logged to CSV - Total generations: {count}")
                    except Exception as e:
                        print(f"[DEBUG] CSV logging failed: {e}")
                
                # Upload to Notion
                print("[DEBUG] Starting Notion upload after generation...")
                poem_type = prompt_data.get('poem_type', 'daily')
                api_time = claude_result.get('time_elapsed', 0)
                upload_success = self._upload_to_notion(self.poem_claude, prompt_data=prompt_data, poem_type=poem_type)
                if upload_success:
                    count = self.poem_logger.get_generation_count() if self.poem_logger else '?'
                    self.status = f"{poem_type.capitalize()} poem generated & uploaded! (Total: {count})"
                    print("[DEBUG] ✅ Upload to Notion successful!")
                else:
                    count = self.poem_logger.get_generation_count() if self.poem_logger else '?'
                    self.status = f"Poem generated (Notion upload failed) - Total: {count}"
                    print("[DEBUG] ❌ Upload to Notion failed")
                
                # Google Drive sync
                self.generation_log.append("")
                self.generation_log.append("> Syncing to Google Drive...")
                self.needs_redraw = True
                pygame.time.wait(400)
                
                print(f"[DEBUG] Manual-gen: Syncing to Google Drive...")
                gdrive_success = False
                try:
                    # Get the actual folder path from renderer (stored in output_dir)
                    if hasattr(renderer, 'output_dir') and renderer.output_dir:
                        poem_folder_path = renderer.output_dir
                        
                        # Get relative path from instagram_posts base
                        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instagram_posts')
                        if poem_folder_path.startswith(base_dir):
                            relative_path = poem_folder_path[len(base_dir):].lstrip(os.sep)
                        else:
                            relative_path = os.path.basename(poem_folder_path)
                        
                        # Run gdrive sync preserving month/day structure
                        result = subprocess.run(
                            ['rclone', 'sync', poem_folder_path, f'gdrive:biopoem_instagram/{relative_path}', '-v'],
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        gdrive_success = (result.returncode == 0)
                        if gdrive_success:
                            self.generation_log.append("> Drive sync complete")
                            print(f"[DEBUG] ✅ Google Drive sync successful: {relative_path}")
                        else:
                            self.generation_log.append("> Drive sync failed")
                            print(f"[DEBUG] ❌ Google Drive sync failed: {result.stderr}")
                        self.needs_redraw = True
                        pygame.time.wait(400)
                    else:
                        print("[DEBUG] ❌ No poem folder to sync (rendering may have failed)")
                except Exception as e:
                    print(f"[DEBUG] ❌ Google Drive sync error: {e}")
                    gdrive_success = False
                except Exception as e:
                    print(f"[DEBUG] ❌ Google Drive sync error: {e}")
                    gdrive_success = False
                
                # Final completion
                self.generation_log.append("")
                self.generation_log.append("> COMPLETE")
                self.needs_redraw = True
                pygame.time.wait(800)  # Show completion longer
                
                # Collect errors/warnings
                errors = []
                if not upload_success:
                    errors.append("Notion upload failed")
                if not gdrive_success:
                    errors.append("Google Drive sync failed")
                
                # Send email report automatically for manual generation (same as auto-gen)
                if self.email_enabled and hasattr(renderer, 'output_dir') and renderer.output_dir:
                    print("[DEBUG] Manual-gen: Sending admin report email automatically...")
                    if self._send_admin_report(
                        self.poem_claude,
                        renderer.output_dir,
                        prompt_data=prompt_data,
                        poem_type=poem_type,
                        gdrive_status=gdrive_success,
                        notion_status=upload_success,
                        api_time=api_time,
                        errors=errors if errors else None
                    ):
                        self.status = f"Poem generated! Email sent ✅"
                        print("[DEBUG] ✅ Manual-gen: Admin report sent successfully")
                    else:
                        self.status = f"Poem generated! Email failed ❌"
                        print("[DEBUG] ❌ Manual-gen: Admin report send failed")
                else:
                    self.status = f"Poem generated! ✅"
                    if not self.email_enabled:
                        print("[DEBUG] Manual-gen: Email not enabled (check .env file)")
            else:
                # Don't overwrite existing poem - just show error in status
                error_msg = claude_result.get('error', 'Unknown error')
                self.status = f"Generation failed: {error_msg[:50]}"
                print(f"[DEBUG] Generation failed: {error_msg}")
        except Exception as e:
            print(f"[DEBUG] ERROR in thread: {e}")
            import traceback
            traceback.print_exc()
            # Don't overwrite existing poem - just show error in status
            self.status = f"Error: {str(e)[:50]}"
        finally:
            # Stop LED pulsation
            try:
                self.sensors.stop_poem_pulsation()
                print("[DEBUG] LED pulsation stopped")
            except Exception as e:
                print(f"[DEBUG] LED pulsation failed to stop: {e}")
            
            self.generating_poems = False
            self.needs_redraw = True
            print("[DEBUG] Manual poem generation thread finished")
    
    
    def _render_current_poem_images(self):
        """Render images for the currently loaded poem"""
        try:
            if not self.poem_claude:
                return
            
            print("[DEBUG] Starting image rendering for current poem...")
            
            # Use InstagramRenderer to create images
            from instagram_renderer import InstagramRenderer
            renderer = InstagramRenderer(output_dir="instagram_posts")
            
            # Get metadata if available
            metadata = self.poem_prompt_data.get('metadata', {}) if self.poem_prompt_data else {}
            
            # Extract clean poem text (without FULL PROMPT section)
            # Split at the prompt separator to get only poem + sensor footnote
            prompt_separator = '════════════════ FULL PROMPT ════════════════'
            if prompt_separator in self.poem_claude:
                poem_for_render = self.poem_claude.split(prompt_separator)[0].strip()
                print("[DEBUG] Extracted clean poem (removed FULL PROMPT section)")
            else:
                poem_for_render = self.poem_claude
            
            # Determine dark mode (use current setting)
            dark_mode = self._is_dark_mode_active()
            
            # Check if visual poem
            is_visual = metadata.get('visual_pattern') and metadata.get('visual_pattern') != 'standard'
            
            if is_visual:
                visual_pattern = metadata.get('visual_pattern')
                print(f"[DEBUG] Rendering VISUAL poem with pattern: {visual_pattern}")
                images = renderer.render_visual_poem(
                    poem_text=poem_for_render,
                    layout_type=visual_pattern,
                    dark_mode=dark_mode,
                    metadata=metadata
                )
            else:
                print("[DEBUG] Rendering NORMAL poem")
                images = renderer.render_normal_poem(
                    poem_text=poem_for_render,
                    metadata=metadata,
                    dark_mode=dark_mode
                )
            
            # Store image paths
            poem_folder_path = renderer.output_dir
            if isinstance(images, dict):
                # New format: {'dark': [poem, footnote], 'light': [poem, footnote]}
                for mode in ['dark', 'light']:
                    if mode in images and images[mode]:
                        self.poem_image_paths[mode] = {}
                        for img_path in images[mode]:
                            if 'footnote' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['footnote'] = img_path
                            elif 'poem' in os.path.basename(img_path):
                                self.poem_image_paths[mode]['poem'] = img_path
                        print(f"[DEBUG] Stored {mode} image paths: {self.poem_image_paths[mode]}")
            
            # Render prompt images
            if self.poem_prompt_data:
                full_prompt = self.poem_prompt_data.get('prompt', '')
                if full_prompt:
                    creative_brief = InstagramRenderer.extract_creative_brief(full_prompt)
                    if creative_brief:
                        # Clean prompt: remove CRITICAL section and everything after
                        prompt_lines = creative_brief.split('\n')
                        clean_lines = []
                        for line in prompt_lines:
                            if line.strip().startswith('CRITICAL:'):
                                break
                            clean_lines.append(line)
                        clean_prompt = '\n'.join(clean_lines).strip()
                        
                        title = self.poem_claude.split('\n')[0].strip().replace('**', '').replace('*', '')
                        prompt_paths = renderer.render_prompt_both_modes(clean_prompt, output_dir=poem_folder_path, title=title)
                        print(f"[DEBUG] Rendered prompt images: {prompt_paths}")
                        if prompt_paths:
                            for path in prompt_paths:
                                if '_dark' in path:
                                    if 'dark' not in self.poem_image_paths:
                                        self.poem_image_paths['dark'] = {}
                                    self.poem_image_paths['dark']['prompt'] = path
                                else:
                                    if 'light' not in self.poem_image_paths:
                                        self.poem_image_paths['light'] = {}
                                    self.poem_image_paths['light']['prompt'] = path
            
            self.status = "✅ Images rendered!"
            self.needs_redraw = True
            print(f"[DEBUG] ✅ Image rendering complete: {poem_folder_path}")
            
        except Exception as e:
            print(f"[DEBUG] Image rendering failed: {e}")
            import traceback
            traceback.print_exc()
            self.status = f"Render failed: {str(e)[:30]}"
            self.needs_redraw = True
    
    def _is_dark_mode_active(self):
        """Determine if dark mode should be active based on auto/manual settings"""
        if self.poem_auto_dark_mode:
            # Auto mode: check time of day (7am-7pm = light, else dark)
            current_hour = datetime.now().hour
            return current_hour < 7 or current_hour >= 19
        else:
            # Manual mode: use toggle state
            return self.poem_dark_mode
    
    def _draw_poem(self):
        # Full screen poem - no Gen button, tap to toggle UI
        if self.poem_ui_visible:
            r=pygame.Rect(PANEL_MARGIN, TOPBAR_H+12, self.sw-2*PANEL_MARGIN, self.sh-(TOPBAR_H+12)-PANEL_MARGIN-60)
        else:
            # Fullscreen - no margins for UI
            r=pygame.Rect(PANEL_MARGIN, PANEL_MARGIN, self.sw-2*PANEL_MARGIN, self.sh-2*PANEL_MARGIN)
        
        # Always use pure black background for consistency
        bg_color = (0, 0, 0)
        text_color = (255, 255, 255)
        
        pygame.draw.rect(self.screen, bg_color, r, border_radius=12)
        
        if self.generating_poems or (self.generation_log and len(self.generation_log) > 0):
            # Terminal output - left-aligned, monospace, showing all log lines
            x_margin = 60
            y_start = 80
            line_height = 22
            # Calculate max visible lines based on actual screen height
            available_height = self.sh - y_start - 70  # 70px for bottom margin
            max_visible_lines = int(available_height / line_height)
            
            # Ensure char_index list matches generation_log length
            while len(self.log_char_index) < len(self.generation_log):
                self.log_char_index.append(0)
            
            # Only scroll if we have more lines than fit on screen
            if len(self.generation_log) > max_visible_lines:
                start_line = len(self.generation_log) - max_visible_lines
            else:
                start_line = 0
            
            for i in range(start_line, len(self.generation_log)):
                log_line = self.generation_log[i]
                display_index = i - start_line
                
                # Gradually reveal characters (typing effect)
                visible_chars = self.log_char_index[i]
                if visible_chars < len(log_line):
                    # Still typing this line
                    self.log_char_index[i] = min(visible_chars + self.log_typing_speed, len(log_line))
                    self.needs_redraw = True
                
                # Display only revealed characters
                visible_text = log_line[:self.log_char_index[i]]
                log_surf = self.fontS.render(visible_text, True, (180, 180, 180))
                self.screen.blit(log_surf, (x_margin, y_start + display_index * line_height))
        elif self.poem_claude:
            # Try to display rendered images, fall back to text
            mode = 'dark'  # Always use dark mode for images
            image_types = ['poem', 'prompt', 'footnote']
            current_type = image_types[self.poem_carousel_index]
            
            # Try to load and display image
            image_displayed = False
            image_path = None
            if mode in self.poem_image_paths and current_type in self.poem_image_paths[mode]:
                image_path = self.poem_image_paths[mode][current_type]
            
            if image_path and os.path.exists(image_path):
                # Load image (cache it)
                cache_key = f"{mode}_{current_type}"
                if cache_key not in self.poem_images_loaded:
                    try:
                        self.poem_images_loaded[cache_key] = pygame.image.load(image_path)
                        print(f"[DEBUG] Loaded image: {image_path}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to load image {image_path}: {e}")
                        self.poem_images_loaded[cache_key] = None
                
                img_surface = self.poem_images_loaded.get(cache_key)
                if img_surface:
                    # Scale image to fit screen while maintaining aspect ratio
                    img_w, img_h = img_surface.get_size()
                    scale = min(r.width / img_w, r.height / img_h)
                    new_w = int(img_w * scale)
                    new_h = int(img_h * scale)
                    scaled_img = pygame.transform.smoothscale(img_surface, (new_w, new_h))
                    
                    # Center image
                    img_x = r.centerx - new_w // 2
                    img_y = r.centery - new_h // 2
                    self.screen.blit(scaled_img, (img_x, img_y))
                    image_displayed = True
            
            # Fallback to text if no image available
            if not image_displayed:
                poem_rect = pygame.Rect(r.left+40, r.top+10, r.width-80, r.height-30)
                
                if self.poem_carousel_index == 0:
                    # Display poem only (extract from full poem text)
                    poem_only = self._extract_poem_only(self.poem_claude)
                    self._render_poem_text(poem_only, poem_rect, dark_mode=True, font_size=26)
                elif self.poem_carousel_index == 1:
                    # Display prompt
                    prompt_text = self._extract_prompt(self.poem_claude)
                    self._render_poem_text(prompt_text, poem_rect, dark_mode=True, font_size=20)
                elif self.poem_carousel_index == 2:
                    # Display footnote (sensor data)
                    footnote_text = self._extract_footnote(self.poem_claude)
                    self._render_poem_text(footnote_text, poem_rect, dark_mode=True, font_size=16)
            
            # Show carousel indicators at bottom
            if self.poem_ui_visible:
                self._draw_carousel_indicators(r, True)
        else:
            inst = self.big.render("Press G to generate poem", True, text_color)
            self.screen.blit(inst, (r.centerx-inst.get_width()//2, r.centery))
    
    def _extract_poem_only(self, full_text):
        """Extract just the poem from the full text (before separator)"""
        lines = full_text.strip().split('\n')
        poem_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Stop at separator
            if stripped.startswith("Generated:") or stripped == "---" or stripped == "—":
                break
            if stripped.startswith("*Biopoem"):
                break
            # Check for dash separator
            dash_count = stripped.count('—') + stripped.count('-')
            if dash_count > 10 and len(stripped) > 15:
                non_space = stripped.replace(' ', '')
                if non_space and (dash_count / len(non_space)) > 0.8:
                    break
            poem_lines.append(line)
        
        return '\n'.join(poem_lines).strip()
    
    def _extract_prompt(self, full_text):
        """Extract high-level prompt information for display (stops before CRITICAL)"""
        if self.poem_prompt_data:
            prompt = self.poem_prompt_data.get('prompt', '')
            
            # Extract only the content BEFORE "CRITICAL:" section
            lines = []
            
            for line in prompt.split('\n'):
                # Stop when we hit CRITICAL section
                if line.strip().startswith('CRITICAL:'):
                    break
                lines.append(line)
            
            # Return the clean prompt without instructions
            return '\n'.join(lines).strip() if lines else 'No prompt summary available'
        return "No prompt data available"
    
    def _extract_footnote(self, full_text):
        """Extract only sensor readings from footnote"""
        lines = full_text.strip().split('\n')
        sensor_lines = []
        in_footnote = False
        
        for line in lines:
            stripped = line.strip()
            # Detect separator
            if not in_footnote:
                if stripped.startswith("Generated:") or stripped == "---" or stripped == "—":
                    in_footnote = True
                    continue
                if stripped.startswith("*Biopoem"):
                    in_footnote = True
                # Check for dash separator
                dash_count = stripped.count('—') + stripped.count('-')
                if dash_count > 10 and len(stripped) > 15:
                    non_space = stripped.replace(' ', '')
                    if non_space and (dash_count / len(non_space)) > 0.8:
                        in_footnote = True
                        continue
            elif in_footnote:
                # Only include lines with sensor readings (contain numbers and units)
                if any(unit in stripped.lower() for unit in ['°c', '°f', '%', 'lux', 'kpa', 'hpa', 'ppm']):
                    sensor_lines.append(stripped)
                # Also include lines that look like "Moisture: 45%"
                elif ':' in stripped and any(c.isdigit() for c in stripped):
                    sensor_lines.append(stripped)
        
        return '\n'.join(sensor_lines).strip() if sensor_lines else "No sensor data available"
    
    def _draw_carousel_indicators(self, rect, dark_mode):
        """Draw dots to indicate carousel position"""
        dot_color = (150, 150, 150)
        active_color = (255, 255, 255) if dark_mode else (0, 0, 0)
        dot_size = 8
        dot_spacing = 20
        
        # Center 3 dots at bottom
        total_width = 3 * dot_size + 2 * dot_spacing
        start_x = rect.centerx - total_width // 2
        dot_y = rect.bottom - 15
        
        for i in range(3):
            x = start_x + i * (dot_size + dot_spacing)
            color = active_color if i == self.poem_carousel_index else dot_color
            pygame.draw.circle(self.screen, color, (x + dot_size//2, dot_y), dot_size//2)
    
    def _render_poem_text(self, text, rect, dark_mode=False, font_size=20):
        """Render text with word wrapping at specified font size"""
        text_color = (255, 255, 255)  # Always white text on black background
        
        # Create font at requested size
        if font_size == 26:
            font = pygame.font.SysFont('monospace', 26)
            line_height = 32
        elif font_size == 20:
            font = self.fontS
            line_height = 24
        elif font_size == 16:
            font = pygame.font.SysFont('monospace', 16)
            line_height = 20
        else:
            font = self.fontS
            line_height = 24
        
        lines = text.strip().split('\n')
        y = rect.top - self.poem_scroll_offset
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                y += line_height
                continue
            
            # Word wrap
            words = stripped.split(' ')
            current_line = ""
            
            for word in words:
                test_line = current_line + word + " "
                test_surf = font.render(test_line, True, text_color)
                
                if test_surf.get_width() > rect.width - 80:
                    if current_line:
                        line_surf = font.render(current_line.rstrip(), True, text_color)
                        if rect.top <= y < rect.bottom:
                            self.screen.blit(line_surf, (rect.left, y))
                        y += line_height
                        current_line = word + " "
                    else:
                        current_line = test_line
                else:
                    current_line = test_line
            
            # Render remaining text
            if current_line.strip():
                line_surf = font.render(current_line.rstrip(), True, text_color)
                if rect.top <= y < rect.bottom:
                    self.screen.blit(line_surf, (rect.left, y))
                y += line_height

    def _render_single_poem(self, poem_text, rect, model_name, dark_mode=False, visual_pattern=None):
        """Render a single poem in clean document style with word wrapping - like a Kindle
        
        Args:
            poem_text: The poem text to render
            rect: The pygame.Rect to render within
            model_name: The model name (unused but kept for compatibility)
            dark_mode: Whether to use dark mode colors
            visual_pattern: Visual pattern type (refrain_stack, centered_spine, etc.)
        """
        if not poem_text:
            return
        
        # Try to extract visual pattern from poem text if not provided
        if not visual_pattern:
            import re
            match = re.search(r'Visual style:\s*(\w+)', poem_text)
            if match:
                visual_pattern = match.group(1)
        
        # Set colors based on dark mode
        text_color = (255, 255, 255) if dark_mode else (0, 0, 0)  # Pure white in dark, pure black in light
        error_color = (255, 100, 100) if dark_mode else (180, 60, 60)
        
        if poem_text.startswith("Error"):
            error_msg = self.fontS.render(poem_text, True, error_color)
            self.screen.blit(error_msg, (rect.centerx-error_msg.get_width()//2, rect.centery))
            return
        
        # Use consistent font for all text (20pt monospace)
        poem_font = self.fontS
        poem_font_bold = pygame.font.SysFont('monospace', 20, bold=True)  # Bold version for title
        line_height = 24  # Consistent line height
        
        lines = poem_text.strip().split('\n')
        
        # First pass: calculate total content height
        total_height = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check for separator
            dash_count = stripped.count('—') + stripped.count('-')
            if dash_count > 10 and len(stripped) > 15:
                non_space = stripped.replace(' ', '')
                if non_space and (dash_count / len(non_space)) > 0.8:
                    total_height += line_height + 20  # Separator with padding
                    continue
            
            # Estimate wrapped lines for this line
            if stripped:
                # Simple word wrapping calculation
                words = stripped.split(' ')
                current_line_width = 0
                max_width = rect.width - 120
                
                for word in words:
                    word_width = poem_font.size(word + " ")[0]
                    if current_line_width + word_width > max_width and current_line_width > 0:
                        total_height += line_height  # New line needed
                        current_line_width = word_width
                    else:
                        current_line_width += word_width
                
                total_height += line_height  # Final line
            else:
                total_height += line_height  # Blank line
        
        # Calculate max scroll offset (content height - visible height + padding)
        # Add 4 line breaks (96px) of padding after content
        padding = line_height * 4
        max_scroll = max(0, total_height - rect.height + padding)
        
        # Clamp scroll offset to valid range
        self.poem_scroll_offset = max(0, min(self.poem_scroll_offset, max_scroll))
        
        y = rect.top - self.poem_scroll_offset  # Apply scroll offset
        in_footnote = False
        
        # Find separator - look for line starting with "Generated:" (footnote start)
        # OR a line that's mostly dashes/em-dashes (old format) or exactly "---"
        separator_idx = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Primary: Look for "Generated:" which marks start of footnote
            if stripped.startswith("Generated:"):
                separator_idx = i
                break
            
            # Also check for simple "---" separator (old format)
            if stripped == "---" or stripped == "—":
                separator_idx = i
                break
            
            # Also check for "*Biopoem" which is the start of footnote (old format)
            if stripped.startswith("*Biopoem"):
                separator_idx = i
                break
            
            # Fallback: Count em-dashes (—) and regular dashes (-)
            dash_count = stripped.count('—') + stripped.count('-')
            # If line has more than 10 dashes and is mostly dashes, it's the separator
            if dash_count > 10 and len(stripped) > 15:
                # Check if it's mostly dashes (over 80% dashes)
                non_space = stripped.replace(' ', '')
                if non_space and (dash_count / len(non_space)) > 0.8:
                    separator_idx = i
                    break
        
        # Define colors for different text elements
        # Poem text: black in light mode, white in dark mode
        # Footnote text: green in light mode, cyan in dark mode
        separator_color = (100, 100, 100) if dark_mode else (180, 180, 180)
        footnote_color = (0, 200, 255) if dark_mode else (0, 128, 0)  # Bright cyan in dark, green in light
        
        # Helper function to render text with word wrapping
        def render_wrapped_text(text, color, max_width):
            nonlocal y
            if not text.strip():
                y += line_height  # Blank line
                return
            
            words = text.split(' ')
            current_line = ""
            
            for word in words:
                test_line = current_line + word + " "
                test_surf = poem_font.render(test_line, True, color)
                
                # If line is too long, render current line and start new one
                if test_surf.get_width() > max_width and current_line:
                    line_surf = poem_font.render(current_line.rstrip(), True, color)
                    if y + line_height <= rect.bottom - 30:
                        self.screen.blit(line_surf, (rect.left, y))
                        y += line_height
                    current_line = word + " "
                else:
                    current_line = test_line
            
            # Render remaining text
            if current_line.strip():
                line_surf = poem_font.render(current_line.rstrip(), True, color)
                if y + line_height <= rect.bottom - 30:
                    self.screen.blit(line_surf, (rect.left, y))
                    y += line_height
        
        # Render lines
        for i, line in enumerate(lines):
            if y + line_height > rect.bottom - 30:
                break
            
            # Handle separator - add spacing and dash line before footnote
            if separator_idx is not None and i == separator_idx:
                y += line_height * 3  # 3 blank lines
                sep = poem_font.render('--------------------------------', True, separator_color)
                self.screen.blit(sep, (rect.left, y))
                y += line_height
                in_footnote = True
                # Don't continue - render this line as first footnote line
            
            # Strip markdown formatting (asterisks) from all lines
            line = line.replace('**', '').replace('*', '')
            
            # Title (first line) - bold, same size
            if i == 0:
                # Render title with bold font
                if not line.strip():
                    y += line_height
                    continue
                
                max_width = rect.width
                words = line.split(' ')
                current_line = ""
                
                for word in words:
                    test_line = current_line + word + " "
                    test_surf = poem_font_bold.render(test_line, True, text_color)
                    
                    if test_surf.get_width() > max_width and current_line:
                        line_surf = poem_font_bold.render(current_line.rstrip(), True, text_color)
                        if y + line_height <= rect.bottom - 30:
                            self.screen.blit(line_surf, (rect.left, y))
                            y += line_height
                        current_line = word + " "
                    else:
                        current_line = test_line
                
                if current_line.strip():
                    line_surf = poem_font_bold.render(current_line.rstrip(), True, text_color)
                    if y + line_height <= rect.bottom - 30:
                        self.screen.blit(line_surf, (rect.left, y))
                        y += line_height
                
                y += 5  # Extra space after title
            # Footnote text - green (light mode) or blue (dark mode)
            elif in_footnote:
                render_wrapped_text(line, footnote_color, rect.width)
            # Regular poem lines - apply visual pattern if specified
            else:
                if visual_pattern and line.strip():
                    # Count non-empty poem body lines for pattern calculation
                    poem_body_lines = [l for l in lines[1:separator_idx] if l.strip()] if separator_idx else [l for l in lines[1:] if l.strip()]
                    try:
                        body_line_idx = poem_body_lines.index(line)
                    except ValueError:
                        body_line_idx = 0
                    total_body_lines = max(len(poem_body_lines), 1)
                    progress = body_line_idx / max(total_body_lines - 1, 1)
                    
                    center_x = rect.left + rect.width // 2
                    max_line_width = rect.width - 40  # Leave some margin
                    
                    # Word wrap long lines first
                    words = line.strip().split(' ')
                    wrapped_lines = []
                    current_wrap = ""
                    for word in words:
                        test = current_wrap + word + " "
                        test_w = poem_font.size(test)[0]
                        if test_w > max_line_width and current_wrap:
                            wrapped_lines.append(current_wrap.rstrip())
                            current_wrap = word + " "
                        else:
                            current_wrap = test
                    if current_wrap.strip():
                        wrapped_lines.append(current_wrap.rstrip())
                    
                    # Render each wrapped segment with pattern positioning
                    for wrap_line in wrapped_lines:
                        line_surf = poem_font.render(wrap_line, True, text_color)
                        line_w = line_surf.get_width()
                        
                        if visual_pattern == "refrain_stack":
                            # Alternating left/right with decreasing indent
                            max_indent = min(100, rect.width // 4)
                            indent = int(max_indent * (1 - progress))
                            if body_line_idx % 2 == 0:
                                x = rect.left + indent
                            else:
                                x = max(rect.left, rect.left + rect.width - line_w - indent)
                        elif visual_pattern == "centered_spine":
                            # All lines centered
                            x = center_x - line_w // 2
                        elif visual_pattern == "center_stem":
                            # All lines centered (like centered_spine but shorter)
                            x = center_x - line_w // 2
                        elif visual_pattern == "right_droop":
                            # Progressive right indent
                            max_indent = min(150, rect.width // 3)
                            indent = int(max_indent * progress)
                            x = rect.left + indent
                        elif visual_pattern == "left_climb":
                            # Decreasing indent from right
                            max_indent = 150
                            indent = int(max_indent * (1 - progress))
                            x = rect.left + indent
                        elif visual_pattern == "field_constellation":
                            # Scattered words - pseudo-random based on line index
                            import hashlib
                            seed = int(hashlib.md5(wrap_line.encode()).hexdigest()[:8], 16)
                            x = rect.left + (seed % (rect.width - line_w - 40))
                        elif visual_pattern == "diagonal_pairing":
                            # Two diagonal paths - even lines descend L→R, odd ascend
                            if body_line_idx % 2 == 0:
                                x = rect.left + body_line_idx * 30
                            else:
                                x = rect.left + rect.width - line_w - body_line_idx * 30
                        elif visual_pattern == "distant_islands":
                            # Centered with extra spacing (handled elsewhere)
                            x = center_x - line_w // 2
                        elif visual_pattern == "minimal_drift":
                            # Sparse placement at different x positions
                            positions = [rect.width // 4, rect.width * 3 // 4, rect.width // 2]
                            x = rect.left + positions[body_line_idx % 3] - line_w // 2
                        # Tier 3 patterns
                        elif visual_pattern == "swarming_refrain":
                            # Chaotic scattered - pseudo-random offset based on line index
                            x = rect.left + ((body_line_idx * 67) % min(150, rect.width // 3))
                        elif visual_pattern == "echo_cascade":
                            # Progressive indentation - each line indents more
                            indent = body_line_idx * 25
                            x = rect.left + min(indent, rect.width // 2)
                        elif visual_pattern == "forked_path":
                            # First third centered, then split left/right
                            third = max(total_body_lines // 3, 1)
                            if body_line_idx < third:
                                x = center_x - line_w // 2
                            elif body_line_idx < third * 2:
                                x = rect.left + (body_line_idx - third) * 20
                            else:
                                x = max(rect.left, rect.left + rect.width - line_w - (body_line_idx - third * 2) * 20)
                        elif visual_pattern == "dense_field":
                            # Left-aligned, tight (handled by normal rendering, just left align)
                            x = rect.left
                        elif visual_pattern == "central_thread":
                            # Centered narrow column
                            x = center_x - line_w // 2
                        elif visual_pattern == "morph_ladder":
                            # Stair-step pattern
                            step = body_line_idx % 4
                            if step == 0:
                                x = rect.left
                            elif step == 1:
                                x = rect.left + 40
                            elif step == 2:
                                x = rect.left + 80
                            else:
                                x = rect.left + 40
                        else:
                            x = rect.left
                        
                        # Clamp x to prevent going off left edge
                        x = max(rect.left, x)
                        
                        if y + line_height <= rect.bottom - 30:
                            self.screen.blit(line_surf, (x, y))
                            y += line_height
                else:
                    render_wrapped_text(line, text_color, rect.width)

def main():
    print(f"[STARTUP] Biopoem starting at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    sys.stdout.flush()
    pygame.display.init()
    app=App()
    try:
        app.run()
    except KeyboardInterrupt:
        print(f"[EXIT] KeyboardInterrupt at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"[CRASH] Unhandled exception at {time.strftime('%Y-%m-%d %H:%M:%S')}: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise
    finally:
        print(f"[EXIT] main() function ending at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        sys.stdout.flush()

if __name__=="__main__":
    import math
    main()
