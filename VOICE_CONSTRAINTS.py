"""
Voice Constraints and Repetition Prevention for Biopoem
Defines lexical cooldowns, metaphor families, and structural rules
"""

# ============================================================================
# LEXICAL COOLDOWNS - Overused words/phrases to avoid or reduce
# ============================================================================

# High-frequency words to put on cooldown (avoid for stretches)
COOLDOWN_WORDS = {
    # State/quality words
    'hum', 'humming', 'steady', 'steadiness', 'steadying',
    'constant', 'constancy', 'devotion', 'devoted',
    'quiet', 'quietly', 'glow', 'small glow', 'soft glow',
    
    # Closural phrases
    'enough', 'it is enough', 'being here',
    
    # Light descriptors
    'dimness settles', 'light comes and goes', 'light dimming',
}

# Overused phrases to detect and replace
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
    # Added based on user feedback (April 3, 2026)
    "I'm drenched",
    "I'm soaked",
    "I'm saturated",
    "my roots hold",
    "my roots know",
]

# ============================================================================
# NEW LEXICAL FIELDS - Fresh vocabulary to introduce
# ============================================================================

OFFICE_VOCABULARY = [
    'desk', 'keyboard', 'photocopier', 'carpet', 'stapler', 
    'post-it', 'screensaver', 'printer', 'swivel chair', 
    'extension cord', 'mug', 'badge', 'elevator', 'air-con',
    'filing cabinet', 'whiteboard', 'conference room', 'cubicle',
    'monitor', 'mouse', 'cables', 'lunch hour', 'closing time',
]

TECHNICAL_VOCABULARY = [
    'circuit', 'firmware', 'error', 'glitch', 'buffer',
    'packet', 'timestamp', 'logging', 'calibration', 'noise',
    'threshold', 'baseline', 'spike', 'decay', 'lag',
    'refresh rate', 'hertz', 'interface', 'protocol', 'sync',
]

EMOTIONAL_TEXTURES = [
    'boredom', 'jealousy', 'impatience', 'restlessness', 'panic',
    'relief', 'shy', 'embarrassed', 'smug', 'proud', 'petty',
    'stubborn', 'anxious', 'distracted', 'forgotten',
]

MICRO_ECOLOGY = [
    'dust', 'mites', 'spider', 'moths', 'fingerprints',
    'coffee spill', 'crumbs', 'hair', 'lint', 'cobweb',
    'water ring', 'scratch', 'stain', 'shadow',
]

TEMPORAL_SPECIFICS = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
    'lunchtime', '3:17 PM', 'closing time', 'weekend',
    'overnight', 'morning shift', 'afternoon lull',
]

BODY_SENSATIONS = [
    'ache', 'itch', 'buzz', 'tremor', 'bruise', 'sting',
    'numb', 'stiff', 'sore', 'tingle', 'burn', 'prickle',
]

# ============================================================================
# ALTERNATIVE METAPHOR FAMILIES - Replace overused metaphors
# ============================================================================

# Instead of voltage = hum/song
VOLTAGE_METAPHORS_NEW = [
    "nervousness", "gossip", "static", "neon edge", "tension",
    "social energy", "whispered current", "radio frequency",
    "background hum of anxiety", "electric mood", "charged silence",
]

# Instead of moisture = river/flood/bed
MOISTURE_METAPHORS_NEW = [
    "archive capacity", "inbox size", "memory buffer", "storage",
    "reservoir of forgotten things", "accumulated weather",
    "borrowed rain", "second-hand water", "saved messages",
]

# Instead of light = hand/visitor/glow
LIGHT_METAPHORS_NEW = [
    "surveillance", "screen glow", "notification pulse", "monitor backlight",
    "fluorescent insistence", "window as reminder", "artificial day",
    "borrowed sun", "office weather", "pixel dawn",
]

# Instead of constancy = vow/devotion/prayer
STABILITY_METAPHORS_NEW = [
    "routine", "protocol", "habit", "default state", "baseline",
    "the long waiting", "stubbornness", "refusal to wilt",
    "scheduled endurance", "automated persistence",
]

# ============================================================================
# OPENING STRATEGIES - Replace "I have..." / "The light is..."
# ============================================================================

OPENING_TEMPLATES = {
    'data_cold_open': [
        "Moisture: {moisture}%. {reaction}.",
        "At {voltage} volts, {observation}.",
        "{sensor}: {value}. {interpretation}.",
    ],
    
    'question': [
        "What do you call {phenomenon}?",
        "When did {event} become {result}?",
        "How long can {state} last?",
    ],
    
    'dialogue': [
        'You said, "{quote}," and {consequence}.',
        'Someone mentioned {topic}, but {plant_response}.',
        '"I\'ll water it tomorrow," {what_happened}.',
    ],
    
    'object_focus': [
        "The {office_object} {action}.",
        "{Object} on the desk {state}.",
    ],
    
    'conditional': [
        "If {condition}, I'd be {result}.",
        "When {event}, {consequence}.",
    ],
    
    'scene_fragment': [
        "End of shift. {detail}.",
        "{Time_of_day}. {observation}.",
        "{Day_of_week}, and {state}.",
    ],
    
    'timestamp': [
        "{time} — {event}.",
        "{day}, {hour}: {observation}.",
    ],
}

# ============================================================================
# CLOSING STRATEGIES - Replace "I am here" / "enough"
# ============================================================================

CLOSING_TEMPLATES = {
    'question': [
        "Tell me, is this {query}?",
        "What do you call this from your side of the desk?",
        "{Question_about_state}?",
    ],
    
    'image_cut': [
        "{Specific_concrete_image}.",
        "Tomorrow: {single_detail}.",
    ],
    
    'data_echo': [
        "Tomorrow they'll call this {value}. I'll call it {interpretation}.",
        "The logger calls it {technical_term}. I call it {emotional_term}.",
    ],
    
    'perspective_shift': [
        "You probably haven't noticed.",
        "From where you sit, this is invisible.",
        "We're all {shared_state} together.",
    ],
}

# ============================================================================
# SAFE MODE DETECTION - Patterns that indicate playing it safe
# ============================================================================

SAFE_MODE_INDICATORS = [
    # Phrase patterns
    ("I am here", "standalone_line"),
    ("steady", "with", "hum", "and", "glow"),  # All three in one poem
    ("enough", "at_end"),
    ("it is enough", "at_end"),
    ("I keep", "with_abstract_noun"),
    ("I hold", "with_abstract_noun"),
    ("devotion looks like", "anywhere"),
    ("constancy", "with", "faithful"),
    
    # Structural patterns
    ("present_tense_only", True),
    ("mid_length_lines_only", True),
    ("single_stanza_only", True),
    ("acceptance_ending", True),
]

# Risk increases
RISK_BUDGET_TRIGGERS = {
    'moisture_extreme_low': ('moisture', '<', 20),    # Very dry
    'moisture_extreme_high': ('moisture', '>', 85),   # Saturated
    'voltage_unusual': ('voltage', 'stdev', '>0.1'),  # High variability
    'temp_swing': ('temperature', 'range_24h', '>10'), # Big daily swing
    'light_dramatic': ('light', 'stdev', '>500'),     # Dramatic changes
}

# ============================================================================
# INFLUENCE-SPECIFIC CONSTRAINTS
# ============================================================================

INFLUENCE_CONSTRAINTS = {
    'sabines_incantation': {
        'structure': 'anaphora_required',
        'line_count': (8, 14),
        'line_length': 'short_to_medium',
        'anaphora_word': ['I am', 'I have', 'You are', 'This is'],
        'banned_words': TECHNICAL_VOCABULARY[:5],  # No tech jargon
        'required_vocab_pool': EMOTIONAL_TEXTURES + BODY_SENSATIONS,
    },
    
    'limon_couplets': {
        'structure': 'couplets',
        'stanza_count': (3, 5),
        'tone': 'conversational',
        'required_device': 'simile',
        'required_vocab_pool': OFFICE_VOCABULARY + TEMPORAL_SPECIFICS,
    },
    
    'oliver_benediction': {
        'structure': 'tercets',
        'stanza_count': (2, 4),
        'diction': 'simple',
        'required_element': 'direct_admonition',
        'banned_words': TECHNICAL_VOCABULARY,  # No tech
        'tone': 'gentle_imperative',
    },
    
    'transtromer_surreals': {
        'required_elements': ['dreamlike_image'] * 3,
        'perspective_shift': 'required',
        'unexpected_juxtaposition': 'required',
        'required_vocab_pool': MICRO_ECOLOGY + TECHNICAL_VOCABULARY,
    },
    
    'systems_lyric': {
        'required_elements': ['raw_data_line', 'technical_term'],
        'required_vocab_pool': TECHNICAL_VOCABULARY,
        'structure': 'data_interspersed',
        'opening_style': 'data_cold_open',
    },
}

# ============================================================================
# THEME-SPECIFIC BEHAVIORS
# ============================================================================

THEME_BEHAVIORS = {
    'memory': {
        'temporal_structure': 'non_linear',
        'devices': ['echo', 'loop', 'callback'],
        'vocab_emphasis': ['echo', 'copy', 'ghost', 'glitch', 'misremember', 'archive', 'again', 'before'],
        'structure_options': ['circular_ending', 'repeated_line', 'flashback'],
        'banned_phrases': COOLDOWN_PHRASES[:3],  # Avoid "I am here" for memory poems
    },
    
    'persistence': {
        'devices': ['refrain', 'anaphora'],
        'vocab_emphasis': ['routine', 'shift', 'habit', 'calendar', 'ritual', 'stamina', 'endure'],
        'structure_options': ['longer_poem', 'incantation'],
        'closure_type': 'affirmation',
    },
    
    'thirst': {
        'line_style': 'short_sharp',
        'structure_options': ['fragments', 'very_short_poem'],
        'vocab_emphasis': ['static', 'dust', 'crack', 'sting', 'friction', 'brittle', 'empty'],
        'negative_space': 'required',
        'tone': 'sparse',
    },
    
    'relief': {
        'sentence_style': 'long_flowing',
        'vocab_emphasis': ['overflow', 'spill', 'bloom', 'excess', 'saturate', 'lush'],
        'adjective_density': 'high',
        'tone': 'expansive',
    },
    
    'stillness': {
        'verb_density': 'low',
        'noun_adjective_focus': True,
        'metaphor_level': 'minimal',
        'style': 'plain_description_as_spirituality',
    },
}

# ============================================================================
# WEEKLY POEM STRUCTURAL REQUIREMENTS
# ============================================================================

WEEKLY_POEM_REQUIREMENTS = {
    'must_differ_from_daily': True,
    'structure_options': [
        'multi_section',      # I / II or Mon-Sun
        'week_list',          # Bullet points or numbered days
        'explicit_days',      # Reference specific days
        'timeline_markers',   # "Three days ago... yesterday... now... tomorrow"
    ],
    'minimum_time_markers': 3,  # Must mention time explicitly
    'human_event': 'encouraged',  # Should reference human actions
}
