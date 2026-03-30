#!/usr/bin/env python3
"""
BIOPOEM Poetry Generation Engine - Complete Framework V2
Implements 7-theme scoring, 16-influence selection, and automated daily poem generation
Based on external GPT collaboration framework
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import random

# Import repetition prevention system
try:
    from repetition_prevention import RepetitionGovernor, SafeModeDetector
    REPETITION_PREVENTION_AVAILABLE = True
except ImportError:
    print("Warning: repetition_prevention.py not found. Running without diversity tracking.")
    REPETITION_PREVENTION_AVAILABLE = False

# Version
VERSION = "1.6"


# ============================================================================
# TIME & SEASONAL CONTEXT HELPERS
# ============================================================================

class TimeContext:
    """Provides time-of-day and seasonal awareness"""
    
    @staticmethod
    def get_time_of_day_from_experience(data_24h):
        """
        Analyze what the plant EXPERIENCED during the day based on sensor patterns.
        Always generates at 8pm, but describes the day's character.
        """
        if 'lux_lx_avg' not in data_24h.columns:
            # No light data - default to describing the full day cycle
            return "day cycle", "the full arc from darkness through light and back"
        
        lux_values = data_24h['lux_lx_avg'].dropna().values
        
        if len(lux_values) == 0:
            return "day cycle", "the full arc from darkness through light and back"
        
        # Analyze light patterns to understand what was significant
        avg_lux = np.mean(lux_values)
        max_lux = np.max(lux_values)
        min_lux = np.min(lux_values)
        std_lux = np.std(lux_values)
        
        # Detect the dominant experience
        # Thresholds tuned for indoor office/home environment
        
        # 1. Very dim (night, lights off, minimal light)
        if avg_lux < 5:
            return "near darkness", "deep night, minimal light, rest and stillness"
        
        # 2. Dim interior (night with some light, early morning)
        elif avg_lux < 15:
            return "dim interior", "low light, quiet hours, subdued presence"
        
        # 3. Experienced bright peak (window light, strong artificial)
        elif max_lux > 80:
            current_lux = lux_values[-1] if len(lux_values) > 0 else avg_lux
            
            # Very bright for indoor = direct window or outdoor
            if max_lux > 500:
                if current_lux > 200:
                    return "bright window light", "strong indirect sun, window glow, daylight flooding in"
                else:
                    return "after bright hours", "the strong light has passed, settling into dimness"
            # Moderate bright = good office lighting or diffuse window
            elif max_lux > 150:
                if current_lux > 80:
                    return "full indoor light", "well-lit hours, presence and activity, the workday brightness"
                else:
                    return "fading bright hours", "light softening, activity winding down"
            # Lower bright = typical indoor peak
            else:
                if current_lux > 50:
                    return "bright exposure", "heightened illumination, active hours, being seen"
                else:
                    return "after bright hours", "light has passed, returning to dimness, the bright memory fading"
        
        # 4. Experienced transition (dawn or dusk pattern)
        elif std_lux > 20:
            first_half_avg = np.mean(lux_values[:len(lux_values)//2])
            second_half_avg = np.mean(lux_values[len(lux_values)//2:])
            
            if second_half_avg > first_half_avg * 1.3:
                return "light increasing", "emerging from dimness, brightness building, awakening energy"
            elif first_half_avg > second_half_avg * 1.3:
                return "light fading", "dimming hours, the descent toward rest, settling"
            else:
                return "shifting light", "fluctuating brightness, variable illumination"
        
        # 5. Steady moderate light (typical indoor ambient)
        elif 15 <= avg_lux <= 50:
            return "ambient light", "soft indoor glow, steady presence, the ordinary hours"
        
        # 6. Steady brighter indoor light
        else:
            return "sustained brightness", "continuous light, all-day illumination, working hours"
    
    @staticmethod
    def get_time_of_day(dt):
        """Return time period and atmospheric descriptor (DEPRECATED - use get_time_of_day_from_experience)"""
        hour = dt.hour
        
        if 5 <= hour < 7:
            return "dawn", "first light, awakening, threshold between dark and day"
        elif 7 <= hour < 12:
            return "morning", "early light, fresh, beginning energy"
        elif 12 <= hour < 17:
            return "afternoon", "full light, sustained presence, the long middle"
        elif 17 <= hour < 19:
            return "dusk", "fading light, transition, the blue hour"
        elif 19 <= hour < 22:
            return "evening", "settled darkness, interior time, winding down"
        else:
            return "night", "deep darkness, quiet, rest and stillness"
    
    @staticmethod
    def get_season(dt):
        """Return detailed season with transitions (Southern Hemisphere - Australia)"""
        month = dt.month
        day = dt.day
        
        # SPRING (September 1 - November 30)
        if month in [9, 10, 11]:
            # Early spring
            if month == 9:
                return "early spring", "tentative emergence, warming days, brave shoots"
            # Mid spring
            elif month == 10:
                return "mid-spring", "full unfurling, greening, rapid growth, exuberance"
            # Late spring (approaching summer)
            else:
                return "late spring", "lengthening light, warmth building, anticipation of fullness"
        
        # SUMMER (December 1 - February 28/29)
        elif month in [12, 1, 2]:
            # Early summer (December solstice week)
            if month == 12 and 21 <= day <= 28:
                return "summer solstice", "longest day, peak light, turning point from expansion to ripening"
            # Early summer
            elif month == 12:
                return "early summer", "fullness arriving, heat establishing, abundance"
            # Mid summer (peak heat)
            elif month == 1:
                return "midsummer", "peak heat, deep stillness, slower rhythms, endurance"
            # Late summer
            else:
                return "late summer", "first hints of decline, light beginning to slant, harvest time"
        
        # AUTUMN (March 1 - May 31)
        elif month in [3, 4, 5]:
            # Early autumn
            if month == 3:
                return "early autumn", "first letting go, colors changing, temperatures dropping"
            # Mid autumn
            elif month == 4:
                return "mid-autumn", "deep release, leaves falling, preparation intensifies"
            # Late autumn (approaching winter)
            else:
                return "late autumn", "bare branches, cold settling in, waiting begins"
        
        # WINTER (June 1 - August 31)
        else:
            # Winter solstice week (June 21)
            if month == 6 and 21 <= day <= 28:
                return "winter solstice", "longest night, deepest darkness, light begins return"
            # Early winter
            elif month == 6:
                return "early winter", "new cold, deep rest, conserving energy"
            # Mid winter
            elif month == 7:
                return "midwinter", "deepest dormancy, waiting, interior time, patience"
            # Late winter (approaching spring)
            else:
                return "late winter", "stirring beneath surface, light returning, anticipation"


# ============================================================================
# EXPERIENTIAL METAPHOR PALETTES
# ============================================================================

class ExperientialMetaphors:
    """
    Translates sensor data into relatable human/experiential metaphors.
    Instead of passing raw numbers to the AI, we translate conditions into
    felt experiences that humans can empathize with.
    """
    
    # -------------------------------------------------------------------------
    # INNER VITALITY (replaces voltage)
    # -------------------------------------------------------------------------
    
    VITALITY_HIGH_STABLE = [
        "the quiet confidence of a well-rested body",
        "buoyancy, like floating without trying",
        "that ease when everything simply works",
        "the steadiness of a clear morning mind",
        "alive in that effortless way",
        "present the way a deep breath is present",
        "settled into yourself, nothing borrowed",
        "the lightness of having no immediate worries",
        "like warmth in your chest without reason",
        "full in a way that doesn't need filling",
        "the feeling after a good stretch",
        "like having slept exactly enough",
        "easy as an exhale",
        "that loose-shouldered feeling of a good day",
        "a body working well without asking",
    ]
    
    VITALITY_MODERATE = [
        "quiet, not tired, just listening",
        "the pace of an unhurried walk",
        "neither rising nor falling, just here",
        "contemplative, like a long afternoon",
        "holding steady without effort",
        "the simplicity of routine",
        "unremarkable and sufficient",
        "like resting between activities",
        "alert without urgency",
        "the middle of a held breath",
        "coasting, neither climbing nor descending",
        "that neutral gear of just being",
    ]
    
    VITALITY_LOW = [
        "the slow weight before sleep arrives",
        "thin, like reserves running quiet",
        "that tiredness behind the eyes",
        "the ebb of something once fuller",
        "like the last hour of a long day",
        "stretched, without quite knowing why",
        "the way effort becomes visible",
        "something asking to rest",
        "hollow but still standing",
        "patience wearing into weariness",
        "that heavy-limbed feeling",
        "like climbing stairs at the end of the day",
        "running on the last of something",
        "the body asking for a pause",
    ]
    
    VITALITY_VOLATILE = [
        "restless, like weather that can't decide",
        "the buzz of a body that won't settle",
        "shifting between states without warning",
        "unpredictable surges of wakefulness",
        "like being startled repeatedly",
        "fluttering between here and somewhere else",
        "that jittery feeling before something happens",
        "unable to find a resting position",
        "like a leg that won't stop bouncing",
        "the uneven rhythm of an unsettled day",
    ]
    
    # -------------------------------------------------------------------------
    # SATISFACTION (moisture-based) - REVISED Feb 2026
    # Natural language, accurate thresholds for Peperomia magnoliifolia
    # -------------------------------------------------------------------------
    
    SATISFACTION_FULL = [
        "that feeling after a long swim when everything feels right",
        "like the first hot shower after being cold for too long",
        "the specific happiness of being exactly where you need to be",
        "that good heavy feeling when you've had just the right amount",
        "like stretching out completely and having room to spare",
        "properly sorted, in the best possible way",
        "the kind of full that makes you want to stay still and enjoy it",
        "like the last day before a holiday—nothing outstanding, just good",
        "that uncomplicated feeling of having everything you need right now",
        "refreshed all the way through, not just on the surface",
        "the quiet version of delight",
        "like finishing a big drink of water and actually sighing",
        "abundance that feels personal, like it was meant for you",
        "the easy warmth of being genuinely taken care of",
    ]
    
    SATISFACTION_ADEQUATE = [
        "that warm, easy feeling of a good day with nothing wrong",
        "like the moment you sink into a couch after a long week",
        "the particular pleasure of just being comfortable",
        "like having the window open on a perfect day",
        "that small happiness of everything being in its place",
        "content in a way that actually feels good, not just neutral",
        "like a good cup of tea at exactly the right temperature",
        "the gentle version of thriving",
        "pleasantly, genuinely fine—not just tolerating it",
        "like humming to yourself without noticing",
        "that light feeling when nothing needs fixing",
        "quietly glad, in a way that doesn't need more than that",
        "the ease of a good, ordinary day going well",
        "like stretching and realizing nothing hurts",
    ]
    
    SATISFACTION_EASING = [
        "like realising halfway through a walk that you probably should have brought water",
        "that moment in a meeting when you notice you're a bit thirsty but it's not worth interrupting for",
        "like a garden in late summer—still green, but the edges are starting to crisp",
        "the way a sponge feels when it's been sitting out for a bit—still damp, not quite right",
        "like a park on a warm afternoon, waiting for the sprinklers to come on",
        "that point on a road trip when you've passed the last service station and the next one's a while away",
        "like soil at the edge of a garden bed that gets a bit less water than the middle",
        "the way a houseplant looks on a Friday when you watered it Monday",
        "like a river in late dry season—still flowing, but you can see the banks",
        "that feeling of a long afternoon with no drink in sight but you're not panicking yet",
        "like standing in a queue and noticing you're thirsty—nothing to do about it right now",
        "the way a cut flower still looks fine but has been out of water for a few hours",
        "like a field going golden at the end of summer—not dying, just drying",
        "that moment when you realise the water bottle you packed is emptier than you thought",
    ]
    
    SATISFACTION_LOW = [
        "like a garden bed that's been missed by the sprinklers for a few days running",
        "the way cracked mud looks at the edge of a dried-out pond",
        "like a long hike where the water ran out an hour ago and the trail isn't done",
        "that feeling in your mouth after a flight where you forgot to drink anything",
        "like a pot plant someone left on a balcony over a hot weekend",
        "the way your throat feels at the end of a long day of talking",
        "like a creek in the middle of a dry summer—still there, but barely",
        "that specific heaviness when you realise you've been dehydrated for hours",
        "like soil that pulls away from the sides of the pot when you press it",
        "the way a lawn looks after two weeks without rain—surviving, but only just",
        "like running on empty and knowing the next stop is still a while away",
        "the way your lips feel after a day at the beach with not enough water",
        "like a dam at low tide, showing the waterline from better days",
        "that feeling of needing something so consistently it stops feeling urgent and just becomes the background",
    ]
    
    SATISFACTION_DEPLETED = [
        "like a creek bed that's gone completely dry—just cracked earth where water used to be",
        "the way a plant looks when it's been left alone in a hot car for too long",
        "like a water tank that's down to the last few centimetres and making a different sound",
        "the way the ground looks in a drought photo—split open, reaching for nothing",
        "like a garden that's been abandoned over a long hot summer",
        "the way your body feels after a full day in the sun with almost nothing to drink",
        "like a dried-out sponge that's forgotten what wet feels like",
        "the way a river looks in satellite images of a bad drought year",
        "like the last day of a camping trip where you've been rationing water since yesterday",
        "like soil so dry it repels water when you finally pour some on",
    ]
    
    SATISFACTION_RENEWED = [
        "like finally getting a glass of water after being thirsty for hours and feeling it all the way down",
        "the specific joy of rain arriving after a long dry stretch",
        "like a plant visibly perking up within hours of being watered—that fast",
        "the relief of something you needed arriving exactly when you needed it",
        "like the feeling after a long shower when you were really cold—warmth moving through properly",
        "that particular happiness of being taken care of after going without",
        "like the moment a cool change arrives on a hot evening—instant and total",
        "the way your whole body responds when you finally drink enough water",
        "like watching a wilted plant straighten up again—almost too good to believe",
        "that rush of gratitude when something arrives that you'd started to doubt was coming",
    ]
    
    # -------------------------------------------------------------------------
    # COMFORT (temperature-based) - REVISED Feb 2026
    # Natural language, everyday temperature observations
    # -------------------------------------------------------------------------
    
    COMFORT_IDEAL = [
        "like a day where you're wearing exactly the right thing for the weather",
        "that specific pleasure of a room that's just the right temperature without any effort",
        "like the comfort of a familiar place that always feels good to come back to",
        "the way a perfect spring afternoon feels—mild, easy, nothing to adjust",
        "like finding a spot in the sun that's warm but not too warm and staying there",
        "that quiet happiness of conditions being exactly right",
        "like a morning where the temperature outside matches how you feel inside",
        "the feeling of a good day where your body just doesn't register the air at all",
        "like being in a garden on a mild afternoon with nowhere to be",
        "that particular contentment of nothing being too much or not enough",
    ]
    
    COMFORT_WARM = [
        "like a room that's been in the sun all afternoon with the windows closed",
        "the way a car feels after it's been parked in direct sun for an hour",
        "like being in a conservatory on a hot day—pleasantly warm for a while, then too much",
        "that heavy indoor warmth of a summer day when the cool change hasn't come yet",
        "like the air in a gym that hasn't quite cooled down after a busy class",
        "the way a north-facing room feels by 3pm in January",
        "like stepping off an air-conditioned train into a hot platform",
        "that thick, still warmth of a summer evening before the temperature drops",
        "the way the air feels in a kitchen when something's been in the oven for hours",
        "like a day where the fan is on but it's mostly just moving warm air around",
    ]
    
    COMFORT_COOL = [
        "like a room that hasn't warmed up yet on a winter morning",
        "the way an old house feels in June before the heating kicks in",
        "like stepping into a cool change after a warm day—air with an edge to it",
        "the feeling of a room where someone left a window open overnight",
        "like a morning that hasn't decided to warm up yet",
        "like being in a space that gets no direct sun in winter—persistently cool",
        "the way a concrete building feels in winter—slow to warm, quick to chill",
        "like a southerly change coming through—air that means business",
        "that particular coolness of early morning before the day heats up",
        "like a room near a door that keeps opening onto cold air",
    ]
    
    # -------------------------------------------------------------------------
    # THE DAY'S LIGHT - REVISED Feb 2026
    # Natural language, relatable everyday comparisons
    # -------------------------------------------------------------------------
    
    LIGHT_BRIGHT_DAY = [
        "like the feeling of walking out into a really good sunny day and immediately feeling better",
        "that particular aliveness of being in bright light on a clear morning",
        "like a day where the sun makes everything look like it's worth looking at",
        "the way a bright room lifts your mood before you've noticed it happening",
        "like sitting outside on a perfect day and feeling genuinely glad to be there",
        "the energy of a sunny morning that makes you want to actually do things",
        "like light that feels generous—warming everything it touches",
        "the way a bright day makes ordinary things look good",
        "like stepping into sunlight after being inside too long and feeling it land on your face",
        "that specific joy of a day with good light, the kind that makes photos look right without trying",
        "like a morning where the sun came out and everything got easier",
    ]
    
    LIGHT_DIM_DAY = [
        "like a room with the curtains mostly drawn on an overcast day",
        "the way a living room feels on a grey winter afternoon",
        "like being inside while it rains—soft light, no shadows",
        "the kind of day where you turn a lamp on even though it's not dark",
        "like a corner of a room that the sun never quite reaches",
        "the way light feels on a deeply overcast day—flat and even, no contrast",
        "like being in a cafe with small windows on a cloudy afternoon",
        "that particular indoor dimness of a day that never really got going",
        "like working in a room that faces the wrong direction",
        "the way a winter afternoon feels by 3pm—already fading",
        "like a day that stayed the colour of early morning all the way through",
    ]
    
    LIGHT_VARIABLE = [
        "like sitting by a window when clouds keep passing in front of the sun",
        "the way light changes in a room when someone walks past outside",
        "like a day that kept switching between bright and flat every half hour",
        "the way dappled light moves through leaves when there's a breeze",
        "like working near a window on a partly cloudy day—bright, then not, then bright again",
        "like the light on a day when the weather couldn't make up its mind",
        "the way a room flickers when headlights pass across the ceiling",
        "like an afternoon of shifting cloud cover, never settling into one thing",
        "the kind of day where you keep squinting and then not squinting",
        "like light through a venetian blind when someone opens a window nearby",
    ]
    
    LIGHT_AFTER_BRIGHT = [
        "like the way a room feels after the sun moves off it in the late afternoon",
        "the quality of light at 6pm after a long bright day",
        "like that shift when the direct sun finally drops below the window line",
        "the way your eyes feel after a full day of bright light—ready for less",
        "like coming inside after being in the sun all day and finding the indoor light gentle",
        "the way a bright room softens as evening comes on",
        "like the relief of shade after a long afternoon in full sun",
        "that particular dimming that happens fast once the sun gets low",
    ]
    
    LIGHT_AFTER_DIM = [
        "like the first properly bright morning after a run of grey days",
        "the way a room feels when the sun finally comes out after overcast days",
        "like opening the curtains after a dim stretch and getting more than you expected",
        "the way Melbourne winter light feels on the first clear day after a week of cloud",
        "like stepping outside after being in a dim room for hours—adjusting slowly",
        "the brightness of a sunny morning that follows days of flat light",
        "like a window that's been in shadow all week finally catching the sun",
        "that specific lift of a bright day after grey ones",
    ]
    
    # -------------------------------------------------------------------------
    # AIR HUMIDITY (new sensor - BME280) - REVISED Feb 2026
    # Natural language, everyday observations of air moisture
    # -------------------------------------------------------------------------
    
    HUMIDITY_DRY = [
        "like a heated room in the middle of winter when you've had the heating on all day",
        "that particular dryness that makes you want to drink water or open a window",
        "like air that's been stripped of moisture—static, crisp, brittle",
        "the way the air feels in an office building with the air con on too long",
        "like a room where someone's been running a heater for hours",
        "that dehydrated feeling of air that's lost its give",
        "like the air in a plane—recycled, dry, making your skin tight",
        "the way indoor air feels in the depths of winter when humidity drops",
        "like the dryness that makes your throat notice every breath",
        "that paper-dry quality of air that hasn't seen moisture in days",
    ]
    
    HUMIDITY_COMFORTABLE = [
        "like a mild spring day where the air just feels easy to breathe",
        "that particular comfort of humidity you don't notice—not dry, not damp, just right",
        "like the air in a well-ventilated room on a good day",
        "the way the air feels when conditions are balanced and your body doesn't have to think about it",
        "like a morning where the air is neither sticky nor crisp—just there",
        "that neutral humidity of a good autumn day—nothing to complain about",
        "like air that lets you forget about weather entirely",
        "the kind of day where you don't notice the air at all, which is perfect",
    ]
    
    HUMIDITY_HUMID = [
        "like stepping off a plane in a tropical city and feeling the air change immediately",
        "that thick, heavy feeling of humidity you can almost see",
        "like the air in a bathroom after a long hot shower—saturated, clinging",
        "the way a summer evening feels when the temperature drops but the moisture doesn't",
        "like air that's holding as much water as it can without actually raining",
        "that sticky, slow quality of a humid day where everything feels heavier",
        "like the atmosphere in a greenhouse—lush, close, breathing moisture",
        "the way coastal air feels on a muggy day—dense, damp, pressing in",
        "like walking into a wall of humidity after being in air conditioning",
        "that tropical heaviness where the air itself feels like a presence",
    ]
    
    # -------------------------------------------------------------------------
    # ATMOSPHERIC PRESSURE (new sensor - BME280) - REVISED Feb 2026
    # Natural language, everyday weather observations
    # -------------------------------------------------------------------------
    
    PRESSURE_LOW = [
        "like the feeling before a big storm rolls in—air heavy, light strange",
        "that oppressive weight of weather coming",
        "like the atmosphere pressing down, waiting",
        "the way the air feels thick and close before it breaks",
        "like a headache in the weather—everything too heavy",
        "that particular heaviness of a front moving through",
        "like the air is holding its breath",
        "the pressure of weather arriving whether you're ready or not",
        "like standing under a sky that's about to do something",
        "that dense, unsettled feeling of low-pressure weather sitting overhead",
    ]
    
    PRESSURE_STABLE = [
        "like a settled autumn week with the same mild weather day after day",
        "that unremarkable middle ground where the weather just... is",
        "like conditions that don't require checking the forecast",
        "the quiet predictability of nothing much happening",
        "like a run of days where you wear the same jacket and it's always fine",
        "that neutral pressure of ordinary weather doing ordinary things",
        "like the atmospheric equivalent of a Tuesday—nothing special, nothing wrong",
        "the kind of weather you stop noticing because it's just there",
    ]
    
    PRESSURE_HIGH = [
        "like the feeling of a clear winter morning with crisp air and long views",
        "that particular brightness of a high-pressure day—everything sharp and defined",
        "the way the sky looks on a perfect blue day when nothing's coming",
        "like breathing air that feels lighter somehow, easier",
        "that settled, stable feeling of good weather that's planning to stay",
        "like a morning after days of cloud when the pressure lifts and everything feels possible",
        "the clarity of a frosty morning with no wind",
        "like the weight of weather lifting—air that doesn't press",
    ]
    
    PRESSURE_FALLING = [
        "like watching a storm system roll in on the radar",
        "that sense of weather changing and gathering",
        "like the barometer dropping and your body knowing before the rain arrives",
        "the feeling of conditions shifting—something coming",
        "like weather moving in—sky darkening, wind picking up",
        "that transition feeling when the pressure drops and everything gets heavier",
        "like the atmosphere preparing for something",
        "the slow inevitability of weather worsening",
    ]
    
    PRESSURE_RISING = [
        "like the way the air feels the morning after a storm has cleared",
        "that lightness of pressure lifting after days of grey",
        "like weather moving out and conditions improving",
        "the feeling of heaviness easing—air getting lighter",
        "like a front passing and the sky opening back up",
        "that particular relief of pressure rising after being low for too long",
        "like the atmosphere settling after being turbulent",
        "the way the air changes when the worst is over",
    ]
    
    # -------------------------------------------------------------------------
    # MULTI-DAY PATTERNS (with {days} placeholder) - REVISED Feb 2026
    # Natural language, everyday observations of multi-day trends
    # -------------------------------------------------------------------------
    
    PATTERN_DRYING = [
        "like a garden that's been waiting for rain for {days} days and starting to show it",
        "the way soil looks {days} days after the last watering—starting to pull away from the edges",
        "{days} days since it was properly wet, and you can tell",
        "like a pot plant {days} days into being forgotten—not critical yet, but getting there",
        "the slow dryness of {days} days without water—incremental, steady, visible",
        "like a sponge {days} days after it was last used—stiff, light, depleted",
        "{days} days of drying out, the kind that happens slowly then all at once",
        "like soil on day {days} of a dry spell—still functional, but running low",
    ]
    
    PATTERN_STABLE = [
        "like {days} days of the same mild weather—nothing to report, nothing to worry about",
        "{days} days where conditions have just... held—no drama, no change",
        "the quiet sameness of {days} consecutive days with no real variation",
        "like a garden {days} days into a stable pattern—just ticking along",
        "{days} days of nothing much happening, which is sometimes perfect",
        "like {days} days of the same routine—comfortable, predictable, steady",
        "the unremarkable consistency of {days} days in a row",
        "{days} days of equilibrium—no highs, no lows, just ongoing",
    ]
    
    PATTERN_RECOVERY = [
        "like a garden {days} days after a good deep watering following a dry spell",
        "{days} days into recovery from stress—visibly improving, not quite back yet",
        "like soil {days} days after finally being watered—softening, easing, returning",
        "the slow improvement of {days} days since conditions changed for the better",
        "like a plant {days} days into recovery—you can see the difference",
        "{days} days since the turnaround—getting better, still getting there",
        "like {days} days of healing after a period of strain",
        "the gradual restoration of {days} days—measurable, ongoing, hopeful",
    ]
    
    PATTERN_VOLATILE = [
        "like {days} days of Melbourne weather—four seasons, no pattern",
        "{days} days of conditions swinging around—up, down, no consistency",
        "like a garden over {days} unstable days—too wet, too dry, too variable to track",
        "{days} days of chaos—no two days the same, no pattern emerging",
        "like trying to track the weather over {days} days when it's just doing whatever it wants",
        "the unpredictability of {days} days with no stable pattern",
        "{days} days of volatility—readings all over the place",
        "like {days} days of conditions refusing to settle into anything consistent",
    ]
    
    # -------------------------------------------------------------------------
    # TRANSLATION METHODS
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_vitality_metaphor(cls, voltage_avg, voltage_std):
        """Translate voltage readings to vitality metaphor.
        
        NOTE: Voltage sensor was disabled 2026-01-02 due to interference with soil sensor.
        When voltage is None/NaN, returns a neutral "moderate" vitality phrase.
        Historical data with voltage will still work normally.
        """
        # Handle missing voltage data (sensor disabled)
        if voltage_avg is None or voltage_std is None:
            return random.choice(cls.VITALITY_MODERATE)
        try:
            # Check for NaN
            if np.isnan(voltage_avg) or np.isnan(voltage_std):
                return random.choice(cls.VITALITY_MODERATE)
        except (TypeError, ValueError):
            return random.choice(cls.VITALITY_MODERATE)
        
        # High variance = volatile
        if voltage_std > 0.15:
            return random.choice(cls.VITALITY_VOLATILE)
        # High and stable
        elif voltage_avg >= 1.3:
            return random.choice(cls.VITALITY_HIGH_STABLE)
        # Moderate
        elif voltage_avg >= 1.0:
            return random.choice(cls.VITALITY_MODERATE)
        # Low
        else:
            return random.choice(cls.VITALITY_LOW)
    
    @classmethod
    def get_satisfaction_metaphor(cls, moisture_current, moisture_change_24h, moisture_min_24h):
        """Translate moisture readings to satisfaction metaphor
        
        Revised thresholds (Feb 2026) for Peperomia magnoliifolia:
        >80%   = FULL (just watered, saturated)
        60-80% = ADEQUATE (comfortable, normal)
        40-60% = EASING (drying but not desperate)
        20-40% = LOW (actually dry, drawing on reserves)
        <20%   = DEPLETED (rare, genuine drought)
        +15%   = RENEWED (just watered)
        """
        # Check for recent watering (big increase)
        if moisture_change_24h > 15:
            return random.choice(cls.SATISFACTION_RENEWED)
        # Depleted - very rare
        elif moisture_current < 20:
            return random.choice(cls.SATISFACTION_DEPLETED)
        # Low - actually dry
        elif moisture_current < 40:
            return random.choice(cls.SATISFACTION_LOW)
        # Easing - drying but not desperate
        elif moisture_current < 60:
            return random.choice(cls.SATISFACTION_EASING)
        # Adequate - comfortable
        elif moisture_current < 80:
            return random.choice(cls.SATISFACTION_ADEQUATE)
        # Full - well saturated
        else:
            return random.choice(cls.SATISFACTION_FULL)
    
    @classmethod
    def get_comfort_metaphor(cls, temp_avg):
        """Translate temperature to comfort metaphor"""
        if temp_avg > 26:
            return random.choice(cls.COMFORT_WARM)
        elif temp_avg < 18:
            return random.choice(cls.COMFORT_COOL)
        else:
            return random.choice(cls.COMFORT_IDEAL)
    
    @classmethod
    def get_light_metaphor(cls, lux_avg, lux_max, lux_std, lux_current):
        """Translate light readings to day's light metaphor"""
        # Check for variable light
        if lux_std > 100:
            return random.choice(cls.LIGHT_VARIABLE)
        
        # Check for transition (current very different from average)
        if lux_avg > 100 and lux_current < 50:
            return random.choice(cls.LIGHT_AFTER_BRIGHT)
        elif lux_avg < 50 and lux_current > 100:
            return random.choice(cls.LIGHT_AFTER_DIM)
        
        # Bright day
        if lux_avg > 100 or lux_max > 200:
            return random.choice(cls.LIGHT_BRIGHT_DAY)
        # Dim day
        else:
            return random.choice(cls.LIGHT_DIM_DAY)
    
    @classmethod
    def get_multiday_pattern_metaphor(cls, pattern_type, days):
        """Get a metaphorical description of multi-day pattern"""
        if pattern_type == "drying":
            template = random.choice(cls.PATTERN_DRYING)
        elif pattern_type == "stable":
            template = random.choice(cls.PATTERN_STABLE)
        elif pattern_type == "recovery":
            template = random.choice(cls.PATTERN_RECOVERY)
        elif pattern_type == "volatile":
            template = random.choice(cls.PATTERN_VOLATILE)
        else:
            return None
        
        return template.format(days=days)
    
    @classmethod
    def get_humidity_metaphor(cls, humidity_avg, humidity_change=None):
        """Translate humidity readings to atmospheric metaphor"""
        if humidity_avg is None:
            return random.choice(cls.HUMIDITY_COMFORTABLE)
        try:
            if np.isnan(humidity_avg):
                return random.choice(cls.HUMIDITY_COMFORTABLE)
        except (TypeError, ValueError):
            return random.choice(cls.HUMIDITY_COMFORTABLE)
        
        if humidity_avg > 70:
            return random.choice(cls.HUMIDITY_HUMID)
        elif humidity_avg < 35:
            return random.choice(cls.HUMIDITY_DRY)
        else:
            return random.choice(cls.HUMIDITY_COMFORTABLE)
    
    @classmethod
    def get_pressure_metaphor(cls, pressure_avg, pressure_change=None):
        """Translate pressure readings to atmospheric metaphor"""
        if pressure_avg is None:
            return random.choice(cls.PRESSURE_STABLE)
        try:
            if np.isnan(pressure_avg):
                return random.choice(cls.PRESSURE_STABLE)
        except (TypeError, ValueError):
            return random.choice(cls.PRESSURE_STABLE)
        
        # Check for significant change first
        if pressure_change is not None:
            try:
                if not np.isnan(pressure_change):
                    if pressure_change < -5:
                        return random.choice(cls.PRESSURE_FALLING)
                    elif pressure_change > 5:
                        return random.choice(cls.PRESSURE_RISING)
            except (TypeError, ValueError):
                pass
        
        # Check absolute pressure level
        if pressure_avg < 1000:  # Lower pressure
            return random.choice(cls.PRESSURE_LOW)
        elif pressure_avg > 1020:  # Higher pressure
            return random.choice(cls.PRESSURE_HIGH)
        else:
            return random.choice(cls.PRESSURE_STABLE)
    
    @classmethod
    def build_atmospheric_paragraph(cls, sensor_summary, multi_day_patterns=None):
        """
        Build a complete atmospheric paragraph combining metaphors from all active categories.
        This replaces the raw sensor data in the prompt.
        """
        sentences = []
        
        # NOTE: Vitality metaphor was based on voltage sensor, which was disabled 2026-01-02.
        # The atmospheric paragraph now focuses on humidity, pressure, moisture, temp, and light.
        
        # Get satisfaction metaphor
        moisture_current = sensor_summary['moisture']['current']
        moisture_change = sensor_summary['moisture']['change_24h']
        moisture_min = sensor_summary['moisture']['min_24h']
        satisfaction = cls.get_satisfaction_metaphor(moisture_current, moisture_change, moisture_min)
        sentences.append(satisfaction.capitalize() + ".")
        
        # Get comfort metaphor
        temp_avg = sensor_summary['temperature']['avg_24h']
        comfort = cls.get_comfort_metaphor(temp_avg)
        sentences.append(comfort.capitalize() + ".")
        
        # Get humidity metaphor (new sensor)
        humidity_data = sensor_summary.get('humidity', {})
        humidity_avg = humidity_data.get('avg_24h')
        humidity_change = humidity_data.get('change_24h')
        if humidity_avg is not None:
            humidity = cls.get_humidity_metaphor(humidity_avg, humidity_change)
            sentences.append(humidity.capitalize() + ".")
        
        # Get pressure metaphor (new sensor)
        pressure_data = sensor_summary.get('pressure', {})
        pressure_avg = pressure_data.get('avg_24h')
        pressure_change = pressure_data.get('change_24h')
        if pressure_avg is not None:
            pressure = cls.get_pressure_metaphor(pressure_avg, pressure_change)
            sentences.append(pressure.capitalize() + ".")
        
        # Get light metaphor
        lux_avg = sensor_summary['light'].get('avg_24h', 50)
        lux_max = sensor_summary['light'].get('max_24h', 100)
        lux_current = sensor_summary['light'].get('current', 50)
        # Calculate std from data if available
        data_24h = sensor_summary.get('data_24h')
        if data_24h is not None and 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
            lux_std = np.std(lux_values) if len(lux_values) > 0 else 0
        else:
            lux_std = 0
        
        # Handle NaN values
        if pd.isna(lux_avg):
            lux_avg = 50
        if pd.isna(lux_max):
            lux_max = 100
        if pd.isna(lux_current):
            lux_current = 50
            
        light = cls.get_light_metaphor(lux_avg, lux_max, lux_std, lux_current)
        # Ensure light metaphor ends with period
        light_sentence = light.capitalize() if not light[0].isupper() else light
        if not light_sentence.endswith('.'):
            light_sentence += '.'
        sentences.append(light_sentence)
        
        # Add multi-day pattern if present (already formatted with caps and period)
        if multi_day_patterns:
            pattern_sentence = cls._translate_multiday_patterns(multi_day_patterns)
            if pattern_sentence:
                sentences.append(pattern_sentence)
        
        return " ".join(sentences)
    
    @classmethod
    def _translate_multiday_patterns(cls, patterns):
        """Convert detected patterns to metaphorical descriptions"""
        if not patterns:
            return None
        
        translated = []
        
        for pattern in patterns[:1]:  # Limit to 1 pattern to keep atmospheric paragraph focused
            pattern_lower = pattern.lower()
            
            # Extract days if present
            import re
            days_match = re.search(r'(\d+)\s*days?', pattern_lower)
            days = int(days_match.group(1)) if days_match else 7
            
            # Determine pattern type and translate
            if 'drying' in pattern_lower or 'declining' in pattern_lower:
                translated.append(cls.get_multiday_pattern_metaphor("drying", days))
            elif 'stable' in pattern_lower or 'consistent' in pattern_lower:
                translated.append(cls.get_multiday_pattern_metaphor("stable", days))
            elif 'recovery' in pattern_lower or 'improving' in pattern_lower or 'increasing' in pattern_lower:
                translated.append(cls.get_multiday_pattern_metaphor("recovery", days))
            elif 'variable' in pattern_lower or 'volatile' in pattern_lower or 'swings' in pattern_lower:
                translated.append(cls.get_multiday_pattern_metaphor("volatile", days))
        
        # Join with proper punctuation
        result = []
        for t in translated:
            if t:
                # Capitalize and ensure proper ending
                t = t[0].upper() + t[1:] if t else t
                if not t.endswith('.'):
                    t += '.'
                result.append(t)
        
        return " ".join(result) if result else None


# ============================================================================
# STYLISTIC INFLUENCES DATABASE
# ============================================================================

INFLUENCES = {
    "pizarnik_fragments": {
        "name": "Pizarnik - Fragments of Silence",
        "description": "Extreme brevity. Each line a shard. Silence louder than speech. Existential compression.",
        "style_markers": [
            "Lines of 1-4 words only",
            "No punctuation or minimal",
            "Heavy use of white space",
            "Each line = complete image/thought",
            "Verbs often omitted",
            "Nouns isolated for maximum weight"
        ],
        "techniques": "Break syntax. One image per line. Let silence between lines do the work. No explanations.",
        "structural_constraints": {
            "length": "3-5 lines total",
            "line_length": "1-4 words per line maximum",
            "stanza_structure": "single block or each line isolated",
            "rhythm": "staccato, breath-like pauses",
            "enjambment": "minimal - each line stands alone",
            "punctuation": "none or only final period"
        },
        "use_cases": [],
        "tone_modifiers": "sparse, haunted, crystalline"
    },
    
    "pizarnik_invocation": {
        "name": "Pizarnik - Invocation to Absence",
        "description": "Addressing the void. Second-person to what isn't there. Longing as structural principle.",
        "style_markers": [
            "Direct address ('you who...')",
            "Negative space emphasized",
            "Body fragments (hands, eyes, mouth)",
            "Night/shadow imagery",
            "Repetition of key phrases",
            "Surreal anatomical metaphors"
        ],
        "techniques": "Speak to absence as if present. Use body parts as emotional sites. Repeat invocations. Embrace paradox.",
        "structural_constraints": {
            "length": "6-9 lines",
            "line_length": "2-5 words per line",
            "stanza_structure": "single block",
            "rhythm": "incantatory, measured",
            "enjambment": "moderate - phrases break mid-thought",
            "punctuation": "minimal, perhaps colons or dashes"
        },
        "use_cases": ["enduring", "thirsting", "recovering"],
        "tone_modifiers": "yearning, spectral, intimate"
    },
    
    "oliver_invitation": {
        "name": "Mary Oliver - The Invitation",
        "description": "Gentle imperative. Inviting reader into attention. Questions that open rather than close.",
        "style_markers": [
            "Imperative verbs (look, listen, notice)",
            "Rhetorical questions",
            "Sensory details accumulate",
            "Present tense immediacy",
            "Accessible vocabulary",
            "Direct address to reader ('you')"
        ],
        "techniques": "Use commands gently. Ask real questions. Build detail slowly. Create intimacy through invitation.",
        "structural_constraints": {
            "length": "6-10 lines (or 3-5 when minimalist)",
            "line_length": "8-10 words per line",
            "stanza_structure": "2-3 stanzas or single flowing block",
            "rhythm": "steady, walking pace",
            "enjambment": "frequent, creates flow",
            "punctuation": "natural speech patterns, questions"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "welcoming, attentive, patient, sometimes delighted"
    },
    
    "oliver_blessing": {
        "name": "Mary Oliver - Benediction",
        "description": "Short blessing. Gratitude concentrated. The ordinary made holy in few words.",
        "style_markers": [
            "Extremely short (3-5 lines)",
            "Each line a complete gift",
            "Simple concrete nouns",
            "Sense of conferring grace",
            "No explanation needed",
            "Often ends with period of silence"
        ],
        "techniques": "Name things plainly. Let simplicity carry weight. End with resonance, not closure.",
        "structural_constraints": {
            "length": "3-5 lines total",
            "line_length": "6-9 words per line",
            "stanza_structure": "single block",
            "rhythm": "calm, declarative",
            "enjambment": "rare - each line complete",
            "punctuation": "periods, simple and clear"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "grateful, serene, consecrating, sometimes celebratory"
    },
    
    "oliver_tercets_attention": {
        "name": "Mary Oliver - Tercets of Attention",
        "description": "Three-line stanzas. Each tercet a moment of noticing. Cumulative revelation.",
        "style_markers": [
            "Tercets (3-line stanzas)",
            "Each stanza = one observation",
            "Sensory progression",
            "Builds to quiet epiphany",
            "Natural speech rhythms",
            "Concrete details throughout"
        ],
        "techniques": "Use tercets to structure attention. Each stanza adds a layer. Let the form guide pacing.",
        "structural_constraints": {
            "length": "9-12 lines (3-4 tercets)",
            "line_length": "7-10 words per line",
            "stanza_structure": "strict tercets (3-line stanzas)",
            "rhythm": "steady, observational",
            "enjambment": "within and between stanzas",
            "punctuation": "natural, aids reading flow"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "contemplative, clear-eyed, reverent, sometimes wonder-struck"
    },
    
    "limon_prose_block": {
        "name": "Ada Limon - Prose Block Confession",
        "description": "Compact prose poem. Confessional intimacy in condensed paragraph form.",
        "style_markers": [
            "No line breaks - solid prose block",
            "Short to medium sentences",
            "Conversational tone",
            "Direct vulnerability",
            "Concise and focused"
        ],
        "techniques": "Write in sentences, not lines. Be direct and honest. Keep it tight and focused.",
        "structural_constraints": {
            "length": "50-80 words as prose paragraph (Instagram-friendly)",
            "line_length": "N/A - prose form",
            "stanza_structure": "single compact prose block",
            "rhythm": "conversational, intimate",
            "enjambment": "N/A - continuous prose",
            "punctuation": "moderate - commas, natural pauses"
        },
        "use_cases": ["sustained", "enduring", "thirsting"],
        "tone_modifiers": "confessional, direct, focused"
    },
    
    "limon_restless_catalog": {
        "name": "Ada Limon - Restless Catalog",
        "description": "Lists that accumulate. Long lines. Energy of everything happening at once.",
        "style_markers": [
            "Long lines (10+ words)",
            "Catalog/list structure",
            "'And' used liberally",
            "Multiple images per line",
            "Breathless accumulation",
            "Specific, contemporary details"
        ],
        "techniques": "Let lines run long. List what you see/feel/know. Use 'and' to build momentum. Don't organize - let chaos in.",
        "structural_constraints": {
            "length": "8-10 lines",
            "line_length": "8-12 words per line",
            "stanza_structure": "2-3 stanzas or continuous block",
            "rhythm": "rushing, accumulative",
            "enjambment": "constant, spills over",
            "punctuation": "commas dominate, few periods"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "restless, abundant, searching, sometimes exuberant"
    },
    
    "limon_couplets": {
        "name": "Ada Limon - Couplets in Motion",
        "description": "Two-line stanzas. Each couplet a beat. Momentum through pairs.",
        "style_markers": [
            "Strict couplets (2-line stanzas)",
            "Conversational voice",
            "Enjambment between couplets",
            "Mix of sentence lengths",
            "Contemporary American idiom",
            "Vulnerability + strength"
        ],
        "techniques": "Use couplets for pacing. Let thoughts break across stanza gaps. Keep voice intimate and modern.",
        "structural_constraints": {
            "length": "6-10 lines (or 3-5 when minimalist, 12-16 when expansive)",
            "line_length": "7-12 words per line",
            "stanza_structure": "strict couplets throughout",
            "rhythm": "conversational, syncopated",
            "enjambment": "frequent, especially between couplets",
            "punctuation": "natural speech, mid-line pauses"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "honest, resilient, contemporary, sometimes playful"
    },
    
    "sabines_confessional_address": {
        "name": "Jaime Sabines - Confessional Address",
        "description": "Long, direct confession. Speaking to 'you' (beloved, god, self). Raw emotional honesty.",
        "style_markers": [
            "Extended address to 'you'",
            "Unpunctuated flow or heavy punctuation",
            "Emotional nakedness",
            "Shifts between tenderness/anger",
            "Everyday language elevated",
            "Long sentences cascade"
        ],
        "techniques": "Speak directly. Don't hide feelings. Use common words for uncommon emotion. Let contradictions exist.",
        "structural_constraints": {
            "length": "8-12 lines",
            "line_length": "variable, 5-10 words",
            "stanza_structure": "single block or 2 large stanzas",
            "rhythm": "speech-like, passionate",
            "enjambment": "frequent, thoughts rush forward",
            "punctuation": "either sparse or excessive"
        },
        "use_cases": ["sustained", "enduring", "thirsting"],
        "tone_modifiers": "raw, passionate, undefended"
    },
    
    "sabines_incantation": {
        "name": "Jaime Sabines - Incantation of the Ordinary",
        "description": "Repetition as spell. Everyday words become ritual. The mundane transformed through insistence.",
        "style_markers": [
            "Anaphora (repeated line openings)",
            "Simple concrete nouns",
            "Ritualistic repetition",
            "Building intensity",
            "Short declarative statements",
            "Hypnotic accumulation"
        ],
        "techniques": "Repeat key phrases. Use simple words. Build through insistence. Let repetition create meaning.",
        "structural_constraints": {
            "length": "8-10 lines",
            "line_length": "4-8 words per line",
            "stanza_structure": "2-3 stanzas with refrains",
            "rhythm": "incantatory, ritualistic",
            "enjambment": "minimal - lines are declarative",
            "punctuation": "periods dominate, simple statements"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "meditative, rhythmic, devotional"
    },
    
    "smith_inventory": {
        "name": "Tracy K. Smith - Inventory of Evidence",
        "description": "Documentary mode. Listing what is. Witness without judgment. Evidence accumulates.",
        "style_markers": [
            "Catalog structure",
            "Present tense declarations",
            "Concrete, specific details",
            "Restrained emotion",
            "Each line an observed fact",
            "Building to unstated conclusion"
        ],
        "techniques": "List what you witness. Be specific. Stay in present tense. Let facts carry emotional weight.",
        "structural_constraints": {
            "length": "10-14 lines (weekly reflection, slightly longer than daily)",
            "line_length": "6-10 words per line",
            "stanza_structure": "single block or 2-3 even stanzas",
            "rhythm": "steady, documentary",
            "enjambment": "moderate, maintains clarity",
            "punctuation": "periods, colons for lists"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "observant, measured, testimonial, sometimes curious"
    },
    
    "smith_cosmic_scale": {
        "name": "Tracy K. Smith - Cosmic Scale Shift",
        "description": "Move from intimate to cosmic. The personal contains the universe. Scale as revelation.",
        "style_markers": [
            "Begins small/personal",
            "Expands to cosmic scope",
            "Scientific vocabulary made lyrical",
            "Time scales shift (moment to eons)",
            "Space scales shift (body to universe)",
            "Awe without sentimentality"
        ],
        "techniques": "Start close. Zoom out gradually. Use science as metaphor. Connect micro to macro. End in vastness.",
        "structural_constraints": {
            "length": "16-22 lines",
            "line_length": "8-12 words per line",
            "stanza_structure": "3-4 stanzas showing scale progression",
            "rhythm": "expansive, building momentum",
            "enjambment": "frequent, creates sweep",
            "punctuation": "varied, guides scale shifts"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "wondering, expansive, humbled, sometimes delighted"
    },
    
    "smith_it_voice": {
        "name": "Tracy K. Smith - The 'It' Voice",
        "description": "Third person about the self. 'It' instead of 'I'. Defamiliarization as insight.",
        "style_markers": [
            "Third person pronouns for self (it, the body, the plant)",
            "Clinical distance from own experience",
            "Objectivity creates strange intimacy",
            "Shorter lines",
            "Precise, almost scientific observation",
            "Estrangement from familiar"
        ],
        "techniques": "Refer to yourself as 'it' or 'the plant'. Observe yourself from outside. Use precise language.",
        "structural_constraints": {
            "length": "8-10 lines",
            "line_length": "5-8 words per line",
            "stanza_structure": "2-3 short stanzas",
            "rhythm": "measured, observational",
            "enjambment": "minimal, clarity prioritized",
            "punctuation": "simple, clear breaks"
        },
        "use_cases": ["sustained", "enduring", "thirsting"],
        "tone_modifiers": "detached, precise, strange"
    },
    
    "akabal_earth_voice": {
        "name": "Humberto Ak'abal - Earth Voice",
        "description": "Speaking as/from the earth. Minimal, elemental. Indigenous wisdom in simple words.",
        "style_markers": [
            "Very short (2-4 lines)",
            "Direct address or declaration",
            "Earth elements as subject",
            "Simple vocabulary, deep meaning",
            "Oral tradition resonance",
            "Connection between human and natural"
        ],
        "techniques": "Be the earth speaking. Use simple, concrete words. One clear image. Let brevity create power. Trust ancient simplicity.",
        "structural_constraints": {
            "length": "2-4 lines total",
            "line_length": "3-7 words per line",
            "stanza_structure": "single breath, no breaks",
            "rhythm": "speech-like, direct",
            "enjambment": "rare, lines stand alone",
            "punctuation": "minimal, natural pauses"
        },
        "use_cases": ["sustained", "sated", "enduring"],
        "tone_modifiers": "elemental, direct, timeless"
    },
    
    "akabal_simple_truth": {
        "name": "Humberto Ak'abal - Simple Truth",
        "description": "Nature observations. No metaphor needed. What is, is enough.",
        "style_markers": [
            "2-4 lines maximum",
            "Concrete images only",
            "No abstraction or explanation",
            "Present tense, immediate",
            "One moment captured",
            "Wisdom in plainness"
        ],
        "techniques": "Observe directly. State simply. No decoration. Let the image speak. The ordinary contains everything.",
        "structural_constraints": {
            "length": "2-4 lines",
            "line_length": "2-6 words per line",
            "stanza_structure": "single unit",
            "rhythm": "natural speech, unhurried",
            "enjambment": "none, complete thoughts per line",
            "punctuation": "minimal, only if essential"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "clear, simple, present, sometimes gentle humor"
    },
    
    "borges_infinite_garden": {
        "name": "Jorge Luis Borges - Infinite Garden",
        "description": "Time loops. Patterns repeat infinitely. The plant as labyrinth. Each day contains all days.",
        "style_markers": [
            "Recursive structure (patterns repeat)",
            "Philosophical precision",
            "Time as maze or mirror",
            "The infinite in the finite",
            "Cerebral yet sensory",
            "Paradox as natural state"
        ],
        "techniques": "Find the pattern that repeats. Make time circular. Let each moment contain infinity. Be precise and mysterious.",
        "structural_constraints": {
            "length": "8-12 lines",
            "line_length": "8-12 words per line",
            "stanza_structure": "single block or mirrored sections",
            "rhythm": "contemplative, maze-like",
            "enjambment": "creates loops, circles back",
            "punctuation": "careful, philosophical"
        },
        "use_cases": ["sustained", "enduring"],
        "tone_modifiers": "philosophical, recursive, timeless"
    },
    
    "haiku_observation": {
        "name": "Kobayashi Issa - Single Breath",
        "description": "Traditional haiku. Compassion for small creatures. One moment of connection with living things.",
        "style_markers": [
            "Exactly 3 lines",
            "Present tense immediacy",
            "Natural imagery prioritized",
            "Seasonal reference subtle",
            "No metaphor - direct observation",
            "Juxtaposition of two images"
        ],
        "techniques": "Capture one vivid moment. Use concrete sensory detail. Let the gap between images create meaning. No explanation.",
        "structural_constraints": {
            "length": "3 lines total (strict)",
            "line_length": "short / medium / short pattern",
            "stanza_structure": "single tercet",
            "rhythm": "breath-based, natural pause",
            "enjambment": "none - each line complete",
            "punctuation": "minimal or none"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "present, vivid, compressed"
    },
    
    "paz_koan": {
        "name": "Octavio Paz - Between Going and Staying",
        "description": "Minimal couplet. Paradox or revelation in two beats. Question without answer.",
        "style_markers": [
            "Exactly 2 lines",
            "Paradox or unexpected turn",
            "No resolution offered",
            "Philosophical weight compressed",
            "Second line reframes first",
            "Silence after = third line"
        ],
        "techniques": "Set up expectation in line 1. Subvert or deepen in line 2. Trust the gap. No need to explain.",
        "structural_constraints": {
            "length": "2 lines total (strict)",
            "line_length": "5-9 words per line",
            "stanza_structure": "single couplet",
            "rhythm": "balanced, mirrored",
            "enjambment": "minimal - lines self-contained",
            "punctuation": "none or single period at end"
        },
        "use_cases": ["sustained", "enduring", "thirsting"],
        "tone_modifiers": "enigmatic, spare, resonant"
    },
    
    "gluck_juxtaposition": {
        "name": "Louise Glück - Stark Juxtaposition",
        "description": "Two concrete images placed side by side. No explanation. Reader connects.",
        "style_markers": [
            "Exactly 2 lines",
            "Each line = one vivid image",
            "No abstraction, only concrete",
            "Sensory details sharp",
            "No connecting words (no 'and', 'like', 'as')",
            "Gap between images = meaning"
        ],
        "techniques": "Choose two specific images. Place them adjacently. Trust juxtaposition. Resist explaining connection.",
        "structural_constraints": {
            "length": "2 lines total (strict)",
            "line_length": "6-10 words per line",
            "stanza_structure": "single couplet",
            "rhythm": "image-driven, each line weighted",
            "enjambment": "none - lines independent",
            "punctuation": "none or only period at end"
        },
        "use_cases": ["sated", "sustained", "recovering"],
        "tone_modifiers": "imagistic, immediate, unmediated"
    },
    
    "diaz_accumulation": {
        "name": "Natalie Diaz - Accumulation and Breath",
        "description": "Short meditation. Each line one breath. Accumulation through repetition with variation.",
        "style_markers": [
            "5-7 lines total",
            "Each line readable in one breath",
            "Repetition with variation",
            "Incremental revelation",
            "Anaphora (repeated opening words)",
            "Meditative pacing"
        ],
        "techniques": "Repeat a phrase with small changes. Build through accumulation. Keep lines breath-length. End with slight shift.",
        "structural_constraints": {
            "length": "5-7 lines",
            "line_length": "4-8 words per line",
            "stanza_structure": "single block",
            "rhythm": "breath-paced, meditative",
            "enjambment": "rare - lines tend to complete",
            "punctuation": "minimal, perhaps final period"
        },
        "use_cases": ["sustained", "enduring", "thirsting"],
        "tone_modifiers": "meditative, incremental, patient, sometimes fierce joy"
    },
    
    "code_lyric": {
        "name": "Original - Pseudocode Poem",
        "description": "Poem written as simple, readable pseudocode that anyone can understand. Plant as function. Use minimal programming syntax (def, while, if, return) with clear, evocative language. Think 'recipe for persistence' or 'instructions for enduring.' Make the logic intuitive - what the plant does should be obvious even to non-coders. 6-8 lines.",
        "style_markers": [
            "Simple Python-like syntax: def, while, if, return",
            "Clear, poetic variables: light, roots, water, tomorrow, wait, hold, grow",
            "Emotionally readable - non-programmers understand immediately",
            "6-8 lines including function definition",
            "Code as recipe or instruction"
        ],
        "techniques": "minimal syntax, clear logic, organic vocabulary, indented blocks",
        "characteristics": {
            "form": "code block, indented",
            "syntax": "Simple Python-like: def, while, if, return (bare minimum)",
            "variables": "clear and poetic - anyone should understand (light, roots, water, tomorrow, wait, hold, grow)",
            "length": "6-8 lines including function definition and call",
            "logic": "emotionally clear - loops = continuing, if = checking, return = what comes next",
            "readability": "CRITICAL - a non-programmer should understand the emotional meaning immediately",
            "punctuation": "proper code syntax but minimal - colons, parentheses",
            "vocabulary": "prioritize organic/sensory words (roots, light, water, soil, wait, hold, grow) over technical terms"
        },
        "examples_of_clarity": [
            "def grow(light, water): # clear inputs",
            "    while light > 0: # obvious condition", 
            "    if water: # simple check",
            "        roots.grow() # clear action",
            "    return grow(light, water) # continuing"
        ],
        "use_cases": ["sustained", "enduring"],
        "tone_modifiers": "tender, patient, quietly devoted, accessible"
    }
}


# ============================================================================
# THEME SCORING SYSTEM
# ============================================================================

class ThemeScorer:
    """Scores sensor data against moisture-narrative themes
    
    CHANGE LOG Feb 4, 2026:
    Replaced abstract themes (wellbeing, persistence, stillness) with moisture-narrative
    themes that clearly communicate watering needs to exhibition visitors.
    
    Five moisture states: Thirsting, Enduring, Sustained, Sated, Recovering
    """
    
    THEMES = {
        "thirsting": {
            "name": "Thirsting / Drought",
            "emotional_translation": "urgent need, emptiness, craving, reaching, desiccation",
            "moisture_language": "thirst, dry, parched, craving water, empty, depleted, drained",
            "visitor_message": "NEEDS WATER NOW",
            "triggers": [
                "moisture_below_50_percent",
                "rapid_moisture_decline",
                "prolonged_dryness",
                "soil_cracking_dry"
            ]
        },
        "enduring": {
            "name": "Enduring / Persisting",
            "emotional_translation": "quiet strength despite want, patience, managing scarcity, resilience",
            "moisture_language": "lean, sparse, rationing, holding on, waiting, dry but alive",
            "visitor_message": "LOW - water soon",
            "triggers": [
                "moisture_50_to_70_percent",
                "slow_moisture_decline",
                "stable_low_moisture",
                "not_yet_critical"
            ]
        },
        "sustained": {
            "name": "Sustained / Adequate",
            "emotional_translation": "contentment, sufficient, balanced, ongoing vitality, ease",
            "moisture_language": "enough, satisfied, nourished, sustained, balanced, comfortable",
            "visitor_message": "HEALTHY - no water needed",
            "triggers": [
                "moisture_70_to_85_percent",
                "stable_moisture",
                "adequate_hydration",
                "optimal_range"
            ]
        },
        "sated": {
            "name": "Sated / Saturated",
            "emotional_translation": "abundance, fullness, overflow, drinking deeply, excess",
            "moisture_language": "soaked, full, saturated, drenched, brimming, wet, abundant",
            "visitor_message": "VERY WET - don't water",
            "triggers": [
                "moisture_above_85_percent",
                "recent_watering",
                "very_high_moisture",
                "risk_of_overwatering"
            ]
        },
        "recovering": {
            "name": "Recovering / Relief",
            "emotional_translation": "relief, renewal, joy after need, gratitude, restoration",
            "moisture_language": "relief, drinking, absorbing, reviving, restoring, quenched",
            "visitor_message": "JUST WATERED - recovering",
            "triggers": [
                "moisture_increase_after_low",
                "rapid_moisture_rise",
                "recent_transition_from_drought",
                "watering_event_detected"
            ]
        }
    }
    
    @staticmethod
    def score_thirsting(data_24h, current):
        """Score Thirsting/Drought theme - fires when plant urgently needs water"""
        score = 0.0
        
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) == 0:
            return 0.0
        
        current_moisture = current['soil_pct_avg']
        avg_moisture = np.mean(moisture_values)
        
        # Critical dryness - STRONG signal
        if current_moisture < 50:
            score += 0.6  # Very strong signal for thirsting
            if current_moisture < 40:
                score += 0.2  # Critical level
        
        # Rapid moisture decline
        if len(moisture_values) > 3:
            moisture_slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
            if moisture_slope < -2:  # Fast decline
                score += 0.3
            elif moisture_slope < -1:  # Moderate decline
                score += 0.15
        
        # Prolonged dryness (average below 55%)
        if avg_moisture < 55:
            score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def score_enduring(data_24h, current):
        """Score Enduring/Persisting theme - low moisture but managing"""
        score = 0.0
        
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) == 0:
            return 0.0
        
        current_moisture = current['soil_pct_avg']
        avg_moisture = np.mean(moisture_values)
        
        # In the 50-70% range (lean but alive)
        if 50 <= current_moisture <= 70:
            score += 0.5
            # Bonus if stable in this range
            moisture_std = np.std(moisture_values)
            if moisture_std < 5:
                score += 0.2  # Stable endurance
        
        # Slow decline but not critical
        if len(moisture_values) > 3:
            moisture_slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
            if -1 < moisture_slope < 0:  # Gentle decline
                score += 0.2
        
        # Average moisture in enduring range
        if 55 <= avg_moisture <= 72:
            score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def score_sustained(data_24h, current):
        """Score Sustained/Adequate theme - optimal moisture, healthy"""
        score = 0.0
        
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) == 0:
            return 0.0
        
        current_moisture = current['soil_pct_avg']
        avg_moisture = np.mean(moisture_values)
        
        # In optimal range (70-85%)
        if 70 <= current_moisture <= 85:
            score += 0.6  # Strong signal for sustained
        
        # Stable moisture (low variance)
        moisture_std = np.std(moisture_values)
        if moisture_std < 3:
            score += 0.25  # Very stable
        elif moisture_std < 6:
            score += 0.15  # Reasonably stable
        
        # Not declining rapidly
        if len(moisture_values) > 3:
            moisture_slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
            if moisture_slope > -1:  # Stable or rising
                score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def score_sated(data_24h, current):
        """Score Sated/Saturated theme - very wet, just watered or overwatered"""
        score = 0.0
        
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) == 0:
            return 0.0
        
        current_moisture = current['soil_pct_avg']
        avg_moisture = np.mean(moisture_values)
        
        # Very high moisture
        if current_moisture > 85:
            score += 0.6
            if current_moisture > 92:
                score += 0.2  # Extremely saturated
        
        # Recent high moisture average
        if avg_moisture > 88:
            score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def score_recovering(data_24h, current):
        """Score Recovering/Relief theme - moisture rising after being low"""
        score = 0.0
        
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) < 3:
            return 0.0
        
        current_moisture = current['soil_pct_avg']
        min_moisture = np.min(moisture_values)
        
        # Strong recovery: was low, now much higher
        if min_moisture < 65 and current_moisture > 80:
            score += 0.7  # Strong recovery signal
        elif min_moisture < 70 and current_moisture > 75:
            score += 0.4  # Moderate recovery
        
        # Rapid moisture increase
        if len(moisture_values) > 3:
            moisture_slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
            if moisture_slope > 2:  # Fast rise
                score += 0.3
            elif moisture_slope > 1:  # Moderate rise
                score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def score_renewal(data_24h, current):
        """Score Renewal/Relief theme"""
        score = 0.0
        
        # Moisture increase after low period
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) > 0:
            min_moisture = np.min(moisture_values)
            current_moisture = current['soil_pct_avg']
            if min_moisture < 70 and current_moisture > 90:
                score += 0.4  # Strong renewal signal
        
        # Humidity recovery after dry period
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 1:
                min_humidity = np.min(humidity_values)
                current_humidity = current.get('humidity_pct_avg')
                if current_humidity is not None and min_humidity < 30 and current_humidity > 45:
                    score += 0.25
        
        # Pressure rising (weather clearing)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 1:
                pressure_change = pressure_values[-1] - pressure_values[0]
                if pressure_change > 5:  # Pressure rising significantly
                    score += 0.2
        
        # Light increase
        if 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
            if len(lux_values) > 1:
                if lux_values[-1] > lux_values[0] * 2:  # Significant brightening
                    score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def score_depletion(data_24h, current):
        """Score Depletion/Exhaustion theme - only triggers on SUSTAINED stress, not momentary dips"""
        score = 0.0
        
        # Moisture declining SIGNIFICANTLY
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) > 0:
            moisture_slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
            if moisture_slope < -3:  # Rapid drying
                score += 0.3
            if current['soil_pct_avg'] < 45:  # Very dry
                score += 0.3
        
        # Prolonged low humidity (stressful for plant)
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 0:
                avg_humidity = np.mean(humidity_values)
                if avg_humidity < 25:  # Very dry air
                    score += 0.25
                elif avg_humidity < 35:  # Dry air
                    score += 0.15
        
        # High temperature stress (only if severe)
        if current['temp_C_avg'] > 28:
            score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def score_exposure(data_24h, current):
        """Score Exposure/Awakening theme"""
        score = 0.0
        
        # Sudden light increase
        if 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
            if len(lux_values) > 1:
                lux_change = lux_values[-1] - lux_values[0]
                if lux_change > 50:  # Dramatic brightening
                    score += 0.4
                if lux_values[-1] > 200:  # Very bright now
                    score += 0.2
        
        # Pressure drop (weather changing, something approaching)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 1:
                pressure_change = pressure_values[-1] - pressure_values[0]
                if pressure_change < -5:  # Significant pressure drop
                    score += 0.25
        
        # Check event notes for "outside" or "moved"
        if 'event_note' in data_24h.columns:
            notes = data_24h['event_note'].dropna().astype(str).str.lower()
            if any('outside' in n or 'moved' in n for n in notes):
                score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def score_stillness(data_24h, current):
        """Score Stillness/Equilibrium theme"""
        score = 0.0
        
        # Humidity stability
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 0:
                humidity_std = np.std(humidity_values)
                if humidity_std < 5:  # Very stable
                    score += 0.2
        
        # Pressure stability (settled weather)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 0:
                pressure_std = np.std(pressure_values)
                if pressure_std < 2:  # Very stable
                    score += 0.2
        
        # Moisture stability
        moisture_values = data_24h['soil_pct_avg'].values
        if len(moisture_values) > 0:
            moisture_std = np.std(moisture_values)
            if moisture_std < 5:  # Stable
                score += 0.2
        
        # Temperature stability
        temp_values = data_24h['temp_C_avg'].values
        if len(temp_values) > 0:
            temp_std = np.std(temp_values)
            if temp_std < 1.5:
                score += 0.15
        
        # Nighttime/darkness
        if 'lux_lx_avg' in data_24h.columns:
            lux_avg = data_24h['lux_lx_avg'].dropna().mean()
            if lux_avg < 10:  # Dark/night
                score += 0.15
        
        # Overall low variance
        if score > 0.5:  # Multiple stable signals
            score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def score_persistence(data_24h, current):
        """Score Persistence/Devotion theme"""
        score = 0.3  # Base score - always persisting by existing
        
        moisture_values = data_24h['soil_pct_avg'].values
        
        # Stable conditions despite varying environment
        if len(moisture_values) > 0:
            avg_moisture = np.mean(moisture_values)
            # Stable moisture even when not optimal
            if np.std(moisture_values) < 5:  # Stable
                score += 0.2
            # Persisting through low moisture
            if avg_moisture < 65:
                score += 0.1
        
        # Humidity stability shows consistent conditions
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 0 and np.std(humidity_values) < 8:
                score += 0.15
        
        # Pressure stability (no dramatic weather)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 0:
                pressure_range = np.max(pressure_values) - np.min(pressure_values)
                if pressure_range < 5:  # Minimal pressure change
                    score += 0.15
        
        # Check for long-term no human interaction (if tracking)
        if 'event_mark' in data_24h.columns:
            if data_24h['event_mark'].sum() == 0:  # No human contact
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def score_transition(data_24h, current):
        """Score Transition/Displacement theme"""
        score = 0.0
        
        # Pressure changing (weather shifting)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 1:
                pressure_range = np.max(pressure_values) - np.min(pressure_values)
                if pressure_range > 8:  # Significant pressure swing
                    score += 0.3
        
        # Humidity swings
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 1:
                humidity_range = np.max(humidity_values) - np.min(humidity_values)
                if humidity_range > 20:  # Significant humidity change
                    score += 0.2
        
        # Day/night transition
        if 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
            if len(lux_values) > 1:
                lux_range = np.max(lux_values) - np.min(lux_values)
                if lux_range > 50:  # Significant light change
                    score += 0.2
        
        # Temperature swings
        temp_values = data_24h['temp_C_avg'].values
        if len(temp_values) > 0:
            temp_range = np.max(temp_values) - np.min(temp_values)
            if temp_range > 3:
                score += 0.2
        
        # In-between moisture (neither full nor empty)
        current_moisture = current['soil_pct_avg']
        if 60 < current_moisture < 85:
            score += 0.1
        
        # Voltage variance (instability) - disabled sensor, replaced with pressure volatility
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 0:
                pressure_std = np.std(pressure_values)
                if pressure_std > 5:  # Unstable weather
                    score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def score_absence(data_24h, current):
        """Score Absence/Blindness theme"""
        score = 0.0
        
        # Missing light data (sensor failure)
        if 'lux_lx_avg' in data_24h.columns:
            lux_null_pct = data_24h['lux_lx_avg'].isna().sum() / len(data_24h)
            if lux_null_pct > 0.5:  # Mostly missing
                score += 0.4
        
        # Prolonged darkness
        if 'lux_lx_avg' in data_24h.columns:
            lux_avg = data_24h['lux_lx_avg'].dropna().mean()
            if lux_avg < 5:
                score += 0.3
        
        # No human interaction for days (if we can detect)
        if 'event_mark' in data_24h.columns:
            days_no_contact = len(data_24h) / (24 * 12)  # Assuming 5-min intervals
            if data_24h['event_mark'].sum() == 0 and days_no_contact > 2:
                score += 0.2
        
        # Any explicitly missing data
        missing_cols = data_24h.isna().sum()
        if missing_cols.sum() > len(data_24h) * 0.3:  # 30% data missing
            score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def score_witness(data_24h, current):
        """Score Witness/Extraordinary theme"""
        score = 0.0
        
        # Extreme temperature (unusual)
        temp_values = data_24h['temp_C_avg'].values
        if len(temp_values) > 0:
            current_temp = current['temp_C_avg']
            if current_temp > 28 or current_temp < 15:  # Extreme temps
                score += 0.3
            
            # Rapid temperature change
            temp_range = np.max(temp_values) - np.min(temp_values)
            if temp_range > 5:  # Dramatic swing
                score += 0.2
        
        # Extreme pressure change (storm approaching or passing)
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
            if len(pressure_values) > 1:
                pressure_range = np.max(pressure_values) - np.min(pressure_values)
                if pressure_range > 10:  # Dramatic pressure swing (weather event)
                    score += 0.3
                
                # Rapid pressure change
                pressure_change = abs(pressure_values[-1] - pressure_values[0])
                if pressure_change > 8:  # Big shift
                    score += 0.2
        
        # Unusual light patterns
        if 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
            if len(lux_values) > 0:
                lux_std = np.std(lux_values)
                if lux_std > 100:  # Very erratic light
                    score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def score_memory(data_24h, current, full_df=None):
        """Score Memory/Déjà Vu theme - requires full historical data"""
        score = 0.0
        
        if full_df is None or len(full_df) < 48:  # Need at least 2 days history
            return 0.0
        
        # Get conditions from 7 days ago (weekly cycle)
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_data = full_df[
            (full_df['datetime'] >= week_ago - timedelta(hours=2)) &
            (full_df['datetime'] <= week_ago + timedelta(hours=2))
        ]
        
        if len(week_ago_data) > 0:
            # Compare moisture similarity
            past_moisture = week_ago_data['soil_pct_avg'].mean()
            current_moisture = current['soil_pct_avg']
            if abs(past_moisture - current_moisture) < 10:  # Similar moisture
                score += 0.2
            
            # Compare humidity similarity (replaces voltage - sensor disabled)
            if 'humidity_pct_avg' in week_ago_data.columns:
                past_humidity = week_ago_data['humidity_pct_avg'].dropna().mean()
                current_humidity = current.get('humidity_pct_avg', 50)
                if not pd.isna(past_humidity) and abs(past_humidity - current_humidity) < 10:
                    score += 0.2
        
        # Check if similar time of day pattern repeats
        current_hour = datetime.now().hour
        same_hour_history = full_df[
            pd.to_datetime(full_df['datetime']).dt.hour == current_hour
        ]
        
        if len(same_hour_history) > 5:  # Enough data points
            # Similar conditions at this time before?
            avg_historical_moisture = same_hour_history['soil_pct_avg'].mean()
            if abs(avg_historical_moisture - current['soil_pct_avg']) < 15:
                score += 0.2
        
        # Bonus for very similar conditions (déjà vu feeling)
        if score >= 0.4:
            score += 0.1
        
        return min(score, 1.0)
    
    @classmethod
    def score_all_themes(cls, data_24h, current_reading, full_df=None):
        """Score all moisture-narrative themes and return ranked results"""
        scores = {
            "thirsting": cls.score_thirsting(data_24h, current_reading),
            "enduring": cls.score_enduring(data_24h, current_reading),
            "sustained": cls.score_sustained(data_24h, current_reading),
            "sated": cls.score_sated(data_24h, current_reading),
            "recovering": cls.score_recovering(data_24h, current_reading)
        }
        
        # Sort by score (highest first)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "scores": scores,
            "ranked": ranked,
            "primary_theme": ranked[0][0],
            "primary_score": ranked[0][1],
            "secondary_theme": ranked[1][0] if len(ranked) > 1 else None,
            "secondary_score": ranked[1][1] if len(ranked) > 1 else 0.0
        }


# ============================================================================
# INFLUENCE SELECTOR
# ============================================================================

class InfluenceSelector:
    """Selects stylistic influence with anti-repetition logic"""
    
    def __init__(self, history_file="poem_history.json"):
        self.history_file = Path(history_file)
        self.history = self._load_history()
    
    def _load_history(self):
        """Load poem generation history"""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {"poems": []}
    
    def _save_history(self):
        """Save history to file"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def get_recent_influences(self, days=5):
        """Get influences used in last N days"""
        recent = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for poem in self.history.get("poems", []):
            poem_date = datetime.fromisoformat(poem.get("date", "2000-01-01"))
            if poem_date >= cutoff_date:
                recent.append(poem.get("influence", ""))
        
        return recent
    
    def select_influence(self, primary_theme, secondary_theme=None, randomness=0.12, repetition_governor=None):
        """
        Select influence based on theme + anti-repetition
        
        Args:
            primary_theme: Main theme (e.g., "renewal")
            secondary_theme: Secondary theme for blending
            randomness: Probability of random selection (default 12%)
            repetition_governor: Optional RepetitionGovernor for diversity scoring
        
        Returns:
            influence_key (str): Key from INFLUENCES dict
        """
        # Random selection X% of the time
        if random.random() < randomness:
            return random.choice(list(INFLUENCES.keys()))
        
        # Get influences NOT used in last 5 days
        recent = self.get_recent_influences(days=5)
        available = [k for k in INFLUENCES.keys() if k not in recent]
        
        # If all have been used recently, reset and use all
        if not available:
            available = list(INFLUENCES.keys())
        
        # Filter by theme compatibility
        compatible = []
        for inf_key in available:
            inf = INFLUENCES[inf_key]
            use_cases = [uc.lower() for uc in inf["use_cases"]]
            
            # Check both primary and secondary theme
            if primary_theme in use_cases:
                base_score = 2.0  # Strong match
            elif secondary_theme and secondary_theme in use_cases:
                base_score = 1.0  # Weak match
            else:
                base_score = 0.5  # No match but available
            
            # Apply diversity boost if governor available
            if repetition_governor:
                diversity_score = repetition_governor.get_influence_diversity_score(inf_key)
                # Boost unused influences: 0.6x to 2.0x multiplier
                diversity_multiplier = 0.6 + 1.4 * diversity_score
                adjusted_score = base_score * diversity_multiplier
                compatible.append((inf_key, adjusted_score))
            else:
                compatible.append((inf_key, base_score))
        
        # If no compatible matches, shouldn't happen now
        if not compatible:
            compatible = [(k, 0.5) for k in available]
        
        # Weighted random selection (prefer high scores)
        weights = [score + 0.1 for _, score in compatible]  # +0.1 to avoid zero weights
        selected = random.choices([k for k, _ in compatible], weights=weights, k=1)[0]
        
        if repetition_governor:
            selected_score = next(s for k, s in compatible if k == selected)
            print(f"[REPETITION] Selected influence: {INFLUENCES[selected]['name']} (diversity-adjusted score: {selected_score:.2f})")
        
        return selected
    
    def record_poem(self, date, theme, influence, title=""):
        """Record a generated poem in history"""
        self.history["poems"].append({
            "date": date.isoformat() if isinstance(date, datetime) else date,
            "theme": theme,
            "influence": influence,
            "title": title
        })
        self._save_history()


# ============================================================================
# HUMAN MARKS & LOCATION MODIFIERS
# ============================================================================

class ContextModifiers:
    """Apply human marks and location as modifiers (not triggers)"""
    
    @staticmethod
    def detect_human_marks(data_24h):
        """Extract human interaction context"""
        if 'event_mark' not in data_24h.columns:
            return None
        
        marks = data_24h[data_24h['event_mark'] == 1]
        if len(marks) == 0:
            return None
        
        # Get most recent mark
        latest = marks.iloc[-1]
        note = latest.get('event_note', '')
        
        return {
            "occurred": True,
            "count": len(marks),
            "latest_note": note if pd.notna(note) else "",
            "tone_modifier": "Include awareness of human presence. Acknowledge the touch/interaction softly."
        }
    
    @staticmethod
    def detect_location_context(data_24h, current_reading, full_df=None):
        """Extract location - only note if there was a CHANGE (movement)"""
        if 'location' not in data_24h.columns:
            return None
        
        current_loc = current_reading.get('location', '')
        locations = data_24h['location'].unique()
        
        # Calculate how long in current location (if we have full history)
        days_in_location = None
        if full_df is not None and len(full_df) > 0 and 'location' in full_df.columns:
            # Find when location last changed
            current_loc_data = full_df[full_df['location'] == current_loc]
            if len(current_loc_data) > 0:
                first_at_location = pd.to_datetime(current_loc_data['datetime'].iloc[0])
                last_reading = pd.to_datetime(full_df['datetime'].iloc[-1])
                days_in_location = (last_reading - first_at_location).days
        
        # Only create context if location CHANGED in last 24h (movement happened)
        if len(locations) > 1:
            flavor = f"Movement between spaces: {' -> '.join(locations)}. The plant experienced displacement/transition."
            return {
                "current": current_loc,
                "changed": True,
                "days_in_location": days_in_location,
                "flavor_text": flavor
            }
        
        # No change = just track for footnote, don't influence poem
        return {
            "current": current_loc,
            "changed": False,
            "days_in_location": days_in_location,
            "flavor_text": None  # Don't add to prompt
        }
    
    @staticmethod
    def detect_multi_day_patterns(full_df, days=7):
        """Detect patterns over multiple days"""
        if full_df is None or len(full_df) < 24:
            return None
        
        patterns = []
        
        # Detect watering events from moisture spikes (automatic detection)
        if len(full_df) > 0:
            moisture_data = full_df[['datetime', 'soil_pct_avg']].copy()
            moisture_data = moisture_data.dropna()
            
            if len(moisture_data) >= 10:
                # Look for sudden moisture increases (watering signature)
                moisture_data['moisture_diff'] = moisture_data['soil_pct_avg'].diff()
                
                # A watering event is a jump of 15%+ in moisture within one reading period
                watering_events = moisture_data[moisture_data['moisture_diff'] > 15]
                
                if len(watering_events) >= 3:  # Need at least 3 waterings to detect pattern
                    watering_dates = pd.to_datetime(watering_events['datetime'])
                    intervals = watering_dates.diff().dt.total_seconds() / 86400  # days
                    intervals = intervals.dropna()
                    
                    if len(intervals) >= 2:
                        avg_interval = intervals.mean()
                        std_interval = intervals.std()
                        
                        # Report consistent watering patterns
                        if pd.notna(avg_interval) and pd.notna(std_interval):
                            if std_interval < 2 and 2 < avg_interval < 14:
                                patterns.append(f"Watered every ~{avg_interval:.1f} days")
        
        # Moisture trend over week
        recent_week = full_df[full_df['datetime'] >= datetime.now() - timedelta(days=days)]
        if len(recent_week) > 0:
            moisture_values = recent_week['soil_pct_avg'].dropna().values
            if len(moisture_values) > 10:
                slope = np.polyfit(range(len(moisture_values)), moisture_values, 1)[0]
                if slope < -1.5:
                    patterns.append(f"Steadily drying over {days} days")
                elif slope > 1.5:
                    patterns.append(f"Moisture increasing over {days} days")
                
                # Check for moisture stability
                moisture_std = np.std(moisture_values)
                if moisture_std < 5:
                    patterns.append("Stable moisture levels")
        
        # Humidity trend (atmospheric conditions indicator - replaces voltage sensor)
        if len(recent_week) > 0 and 'humidity_pct_avg' in recent_week.columns:
            humidity_values = recent_week['humidity_pct_avg'].dropna().values
            if len(humidity_values) > 10:
                humidity_avg = np.mean(humidity_values)
                humidity_std = np.std(humidity_values)
                
                if humidity_avg < 30:
                    patterns.append("Dry atmospheric conditions")
                elif humidity_avg > 65:
                    patterns.append("Humid atmospheric conditions")
                
                # Check for humidity stability
                if humidity_std < 5:
                    patterns.append("Stable humidity levels")
                elif humidity_std > 15:
                    patterns.append("Variable humidity conditions")
        
        # Temperature patterns
        if len(recent_week) > 0:
            temp_values = recent_week['temp_C_avg'].dropna().values
            if len(temp_values) > 10:
                temp_range = np.max(temp_values) - np.min(temp_values)
                temp_avg = np.mean(temp_values)
                temp_min = np.min(temp_values)
                temp_max = np.max(temp_values)
                
                if temp_range > 10:
                    patterns.append(f"Wide temperature swings ({temp_min:.1f}C - {temp_max:.1f}C)")
                elif temp_range < 3:
                    patterns.append(f"Stable temperature (~{temp_avg:.1f}C)")
                
                if temp_avg < 18:
                    patterns.append(f"Cool conditions (avg {temp_avg:.1f}C)")
                elif temp_avg > 26:
                    patterns.append(f"Warm conditions (avg {temp_avg:.1f}C)")
                
                # Check for daily temperature cycles
                if len(temp_values) > 24:
                    # Group by day and check for consistent daily patterns
                    daily_ranges = []
                    for i in range(0, len(temp_values), 24):
                        day_temps = temp_values[i:min(i+24, len(temp_values))]
                        if len(day_temps) > 5:
                            daily_ranges.append(np.max(day_temps) - np.min(day_temps))
                    if len(daily_ranges) >= 3 and np.mean(daily_ranges) > 4:
                        patterns.append(f"Daily temperature cycles (avg {np.mean(daily_ranges):.1f}C range)")
        
        # Light patterns
        if 'lux_lx_avg' in recent_week.columns:
            light_values = recent_week['lux_lx_avg'].dropna().values
            if len(light_values) > 10:
                light_avg = np.mean(light_values)
                light_max = np.max(light_values)
                light_min = np.min(light_values)
                light_std = np.std(light_values)
                
                # Categorize light environment
                if light_max > 10000:
                    patterns.append(f"Full sun exposure (peak {light_max:.0f} lux)")
                elif light_max > 1000:
                    patterns.append(f"Bright indirect light (peak {light_max:.0f} lux)")
                elif light_max > 500:
                    patterns.append(f"Moderate light (peak {light_max:.0f} lux)")
                elif light_max > 100:
                    patterns.append(f"Dim conditions (peak {light_max:.0f} lux)")
                elif light_max < 50:
                    patterns.append(f"Low light environment (peak {light_max:.0f} lux)")
                
                # Check for day/night cycle strength
                if len(light_values) > 24:
                    if light_std > 1000:  # Strong outdoor cycle
                        patterns.append(f"Strong day/night cycle (outdoor-like)")
                    elif light_std > 100:  # Regular cycle
                        patterns.append(f"Regular day/night cycle")
                    elif light_std < 20:  # Very stable
                        patterns.append(f"Constant light (artificial/indoor)")
                
                # Detect light exposure duration per day
                if len(light_values) > 24:
                    bright_hours_per_day = []
                    for i in range(0, len(light_values), 12):  # Check every 12 readings (1hr if 5min intervals)
                        day_lights = light_values[i:min(i+288, len(light_values))]  # 24hrs of 5min readings
                        if len(day_lights) > 0:
                            bright_count = np.sum(day_lights > 100)
                            bright_hours_per_day.append(bright_count * 5 / 60)  # Convert to hours
                    if len(bright_hours_per_day) > 0:
                        avg_bright_hours = np.mean(bright_hours_per_day)
                        if avg_bright_hours > 10:
                            patterns.append(f"Long light exposure (~{avg_bright_hours:.1f}hrs/day)")
                        elif avg_bright_hours < 4:
                            patterns.append(f"Short light exposure (~{avg_bright_hours:.1f}hrs/day)")
        
        return patterns if patterns else None


# ============================================================================
# AUTOMATED PROMPT GENERATOR
# ============================================================================

class PromptGenerator:
    """Generate complete prompts for LLM using framework"""
    
    @staticmethod
    def build_sensor_summary(data_24h, current_reading, full_df=None):
        """Create sensor data summary with broader temporal context.
        
        Uses moisture, temperature, light, humidity, and pressure sensors.
        ECG/voltage sensor removed as of Feb 2026.
        """
        moisture_values = data_24h['soil_pct_avg'].values
        temp_values = data_24h['temp_C_avg'].values
        
        lux_values = []
        if 'lux_lx_avg' in data_24h.columns:
            lux_values = data_24h['lux_lx_avg'].dropna().values
        
        # Humidity data (from BME280)
        humidity_values = []
        if 'humidity_pct_avg' in data_24h.columns:
            humidity_values = data_24h['humidity_pct_avg'].dropna().values
        
        # Pressure data (from BME280)
        pressure_values = []
        if 'pressure_hPa_avg' in data_24h.columns:
            pressure_values = data_24h['pressure_hPa_avg'].dropna().values
        
        # Build humidity summary
        if len(humidity_values) > 0:
            humidity_summary = {
                "current": current_reading.get('humidity_pct_avg', np.nan),
                "min_24h": np.min(humidity_values),
                "max_24h": np.max(humidity_values),
                "avg_24h": np.mean(humidity_values),
                "std": np.std(humidity_values),
                "change_24h": humidity_values[-1] - humidity_values[0] if len(humidity_values) > 1 else 0
            }
        else:
            humidity_summary = {
                "current": None, "min_24h": None, "max_24h": None,
                "avg_24h": None, "std": None, "change_24h": None
            }
        
        # Build pressure summary
        if len(pressure_values) > 0:
            pressure_summary = {
                "current": current_reading.get('pressure_hPa_avg', np.nan),
                "min_24h": np.min(pressure_values),
                "max_24h": np.max(pressure_values),
                "avg_24h": np.mean(pressure_values),
                "std": np.std(pressure_values),
                "change_24h": pressure_values[-1] - pressure_values[0] if len(pressure_values) > 1 else 0
            }
        else:
            pressure_summary = {
                "current": None, "min_24h": None, "max_24h": None,
                "avg_24h": None, "std": None, "change_24h": None
            }
        
        # Build basic 24h summary (voltage removed Feb 2026)
        summary = {
            "moisture": {
                "current": current_reading['soil_pct_avg'],
                "min_24h": np.min(moisture_values),
                "max_24h": np.max(moisture_values),
                "avg_24h": np.mean(moisture_values),
                "change_24h": moisture_values[-1] - moisture_values[0] if len(moisture_values) > 0 else 0
            },
            "temperature": {
                "current": current_reading['temp_C_avg'],
                "min_24h": np.min(temp_values),
                "max_24h": np.max(temp_values),
                "avg_24h": np.mean(temp_values)
            },
            "humidity": humidity_summary,
            "pressure": pressure_summary,
            "light": {
                "current": current_reading.get('lux_lx_avg', np.nan),
                "avg_24h": np.mean(lux_values) if len(lux_values) > 0 else np.nan,
                "max_24h": np.max(lux_values) if len(lux_values) > 0 else np.nan
            },
            "data_24h": data_24h,  # Pass through for time-of-day analysis
            "full_df": full_df  # Pass through for observation duration
        }
        
        # Add broader temporal context if we have full historical data
        if full_df is not None and len(full_df) > 24:
            
            # 7-DAY CONTEXT
            week_ago = datetime.now() - timedelta(days=7)
            week_data = full_df[full_df['datetime'] >= week_ago]
            
            if len(week_data) > 0:
                summary["moisture"]["avg_7day"] = week_data['soil_pct_avg'].mean()
                summary["moisture"]["min_7day"] = week_data['soil_pct_avg'].min()
                
                summary["temperature"]["avg_7day"] = week_data['temp_C_avg'].mean()
                summary["temperature"]["max_7day"] = week_data['temp_C_avg'].max()
                summary["temperature"]["min_7day"] = week_data['temp_C_avg'].min()
                
                if 'lux_lx_avg' in week_data.columns:
                    summary["light"]["avg_7day"] = week_data['lux_lx_avg'].dropna().mean()
                
                # Humidity 7-day context
                if 'humidity_pct_avg' in week_data.columns:
                    summary["humidity"]["avg_7day"] = week_data['humidity_pct_avg'].dropna().mean()
                    summary["humidity"]["min_7day"] = week_data['humidity_pct_avg'].dropna().min()
                    summary["humidity"]["max_7day"] = week_data['humidity_pct_avg'].dropna().max()
                
                # Pressure 7-day context
                if 'pressure_hPa_avg' in week_data.columns:
                    summary["pressure"]["avg_7day"] = week_data['pressure_hPa_avg'].dropna().mean()
                    summary["pressure"]["min_7day"] = week_data['pressure_hPa_avg'].dropna().min()
                    summary["pressure"]["max_7day"] = week_data['pressure_hPa_avg'].dropna().max()
            
            # 30-DAY CONTEXT (if available)
            month_ago = datetime.now() - timedelta(days=30)
            month_data = full_df[full_df['datetime'] >= month_ago]
            
            if len(month_data) > 100:  # Enough data for monthly stats
                summary["moisture"]["avg_30day"] = month_data['soil_pct_avg'].mean()
                summary["temperature"]["avg_30day"] = month_data['temp_C_avg'].mean()
                
                if 'lux_lx_avg' in month_data.columns:
                    summary["light"]["avg_30day"] = month_data['lux_lx_avg'].dropna().mean()
                
                if 'humidity_pct_avg' in month_data.columns:
                    summary["humidity"]["avg_30day"] = month_data['humidity_pct_avg'].dropna().mean()
                
                if 'pressure_hPa_avg' in month_data.columns:
                    summary["pressure"]["avg_30day"] = month_data['pressure_hPa_avg'].dropna().mean()
        
        return summary
    
    # NOTE: derive_emotional_state() was removed 2026-02-02.
    # It was based on voltage sensor which was disabled 2026-01-02.
    # Emotional state is now derived from theme scoring based on active sensors.
    
    @staticmethod
    def generate_prompt(
        date,
        theme_analysis,
        influence_key,
        sensor_summary,
        human_context=None,
        location_context=None,
        multi_day_patterns=None,
        repetition_governor=None
    ):
        """
        Generate complete prompt for LLM - LEAN VERSION
        
        Args:
            date: datetime object
            theme_analysis: Output from ThemeScorer.score_all_themes()
            influence_key: Key from INFLUENCES dict
            sensor_summary: Output from build_sensor_summary()
            human_context: Output from detect_human_marks() or None
            location_context: Output from detect_location_context() or None
            multi_day_patterns: Output from detect_multi_day_patterns() or None
        
        Returns:
            str: Complete prompt ready for API
        """
        import random
        
        # Get theme and influence details
        primary_theme = theme_analysis["primary_theme"]
        theme_details = ThemeScorer.THEMES[primary_theme]
        influence = INFLUENCES[influence_key]
        
        # Get moisture state message for visitor clarity
        moisture_language = theme_details.get('moisture_language', '')
        visitor_message = theme_details.get('visitor_message', '')
        
        # Get seasonal context
        season, seasonal_flavor = TimeContext.get_season(date)
        
        # Build atmospheric paragraph from metaphors
        atmospheric_paragraph = ExperientialMetaphors.build_atmospheric_paragraph(
            sensor_summary, 
            multi_day_patterns
        )
        
        # Select perspective mode (40% plant-specific, 60% abstract/universal)
        perspective_roll = random.random()
        if perspective_roll < 0.40:
            perspective_mode = "plant"
            perspective_hint = "You are a plant: roots, leaves, stems. Let botanical imagery surface naturally: growth, photosynthesis, the slow conversation with soil."
        else:
            perspective_mode = "abstract"
            perspective_hint = "Write from any living consciousness. No need to name what you are. Focus on presence, light, the texture of time."
        
        # Get recent titles for avoidance
        recent_titles = PromptGenerator._get_recent_titles(repetition_governor, limit=15)
        titles_list = ", ".join(f'"{t}"' for t in recent_titles[-5:]) if recent_titles else "none yet"
        
        # Load community feedback (if available)
        feedback_recommendations, feedback_analysis = PromptGenerator.load_feedback_suppressions()
        
        # Build feedback section if we have recommendations
        feedback_section = ""
        if feedback_recommendations:
            feedback_lines = ["\n---\n", "COMMUNITY FEEDBACK:\n",
                            "Based on visitor ratings in the gallery, some patterns felt repetitive:\n"]
            
            for rec in feedback_recommendations[:3]:  # Max 3 recommendations
                feedback_lines.append(f"  • {rec['action']}\n")
            
            feedback_lines.append("\nPlease avoid these patterns. Aim for fresh approaches that surprise.\n")
            feedback_section = "".join(feedback_lines)
        
        # Condense style markers to flowing description
        style_markers = influence['style_markers'][:4]
        style_description = ". ".join(m.rstrip('.') for m in style_markers)
        
        # Get structural constraints if available
        constraints = influence.get('structural_constraints', {})
        length_hint = constraints.get('length', '5-12 lines')
        
        # Extract just the author name (before the " - " separator)
        full_influence_name = influence['name']
        if ' - ' in full_influence_name:
            author_name = full_influence_name.split(' - ')[0]
        else:
            author_name = full_influence_name
        
        # Build flowing, readable prompt
        prompt = f"""Write a poem.

It is {date.strftime('%B %d, %Y')}. The season is {season.lower()}: {seasonal_flavor.lower()}.

Today felt like this: {atmospheric_paragraph}

The poem should carry the feeling of {theme_details['name'].lower()}: {theme_details['emotional_translation']}.

CRITICAL: The poem MUST include clear language about the plant's moisture state. Use these words naturally: {moisture_language}. A visitor reading this poem should understand: "{visitor_message}".

Make the moisture state EXPLICIT in the poem - not metaphorical. The plant is either dry (thirsty), low (enduring), comfortable (sustained), very wet (sated), or recovering from drought. Say it clearly.

---

Write in the style of {author_name}: {influence['description'].lower()}

A few things about this approach: {style_description}. {influence['techniques']}

The tone should be {influence['tone_modifiers']}.

{perspective_hint}

---

Some practical notes:

The poem should be {length_hint}, free verse. Give it a title of 2-5 words, plain text without any formatting or asterisks. Write in first person, from inside the experience. Match your energy to the atmosphere: vibrant when things feel good, tender when they don't.

Do not use em dashes (—) anywhere in the poem. Use commas, periods, or line breaks instead. Also avoid numbers, measurements, and technical words like voltage, sensor, data, or signal. Skip religious language (devotion, prayer, blessed, sacred).

Recent titles I've seen: {titles_list}. Try something structurally different.{feedback_section}

---

Just give me the title and the poem, plain text only. No asterisks, no markdown, no formatting. End with your last poetic line."""
        
        return prompt
    
    @staticmethod
    def _get_recent_titles(repetition_governor, limit=15):
        """Get list of recent titles for avoidance"""
        if repetition_governor is None:
            return []
        
        recent_titles = []
        for poem in repetition_governor.history.get('poems', []):
            title = poem.get('title', '')
            # Strip markdown formatting (asterisks)
            title = title.replace('**', '').replace('*', '')
            if title and title not in recent_titles:
                recent_titles.append(title)
        
        return recent_titles[-limit:]
    
    @staticmethod
    def load_feedback_suppressions():
        """
        Load community feedback analysis to inform prompt generation
        Returns tuple: (recommendations list, analysis dict or None)
        """
        analysis_file = 'feedback_analysis.json'
        
        # Check if feedback analysis exists
        if not os.path.exists(analysis_file):
            return [], None
        
        try:
            with open(analysis_file, 'r') as f:
                import json
                analysis = json.load(f)
            
            # Check if analysis is recent (within last 14 days)
            analysis_date = datetime.fromisoformat(analysis['analysis_date'])
            days_old = (datetime.now() - analysis_date).days
            
            if days_old > 14:
                print(f"[FEEDBACK] Analysis is {days_old} days old - not using")
                return [], None
            
            recommendations = analysis.get('recommendations', [])
            print(f"[FEEDBACK] Loaded {len(recommendations)} recommendations from community feedback")
            
            return recommendations, analysis
            
        except Exception as e:
            print(f"[FEEDBACK] Could not load analysis: {e}")
            return [], None


# ============================================================================
# DAILY POETRY ORCHESTRATOR
# ============================================================================

class DailyPoetryGenerator:
    """Main orchestrator for daily poem generation"""
    
    def __init__(self, csv_path, history_file="poem_history.json"):
        """
        Initialize the daily poetry generator
        
        Args:
            csv_path: Path to plant sensor data CSV
            history_file: Path to poem history JSON for tracking
        """
        self.csv_path = csv_path
        self.influence_selector = InfluenceSelector(history_file)
        self.prompt_generator = PromptGenerator()
        
        # Initialize repetition prevention
        if REPETITION_PREVENTION_AVAILABLE:
            self.repetition_governor = RepetitionGovernor(history_file='poem_history.json')
            print("[REPETITION] Diversity tracking enabled")
        else:
            self.repetition_governor = None
    
    def load_data(self, hours=24):
        """Load last N hours of sensor data"""
        # Read CSV - use Python engine with auto-detection
        df = pd.read_csv(self.csv_path, sep=None, engine='python')
        
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        
        # Find the datetime column (could be named differently)
        datetime_col = None
        for col in df.columns:
            if 'datetime' in col.lower() or col.lower() == 'date':
                datetime_col = col
                break
        
        if datetime_col is None:
            # Assume first column is datetime if no datetime column found
            datetime_col = df.columns[0]
            print(f"Warning: No datetime column found. Using first column: '{datetime_col}'")
        
        # Convert datetime column - try ISO format first, then fallback
        try:
            df[datetime_col] = pd.to_datetime(df[datetime_col], format='ISO8601')
        except:
            df[datetime_col] = pd.to_datetime(df[datetime_col], format='%Y-%m-%d %H:%M:%S')
        
        # Rename to standard 'datetime' for consistency
        if datetime_col != 'datetime':
            df = df.rename(columns={datetime_col: 'datetime'})
        
        # Clean sensor data - remove corrupt readings
        if 'temp_C_avg' in df.columns:
            df.loc[df['temp_C_avg'] > 100, 'temp_C_avg'] = np.nan  # Remove impossibly high temps
            df.loc[df['temp_C_avg'] < 0, 'temp_C_avg'] = np.nan    # Remove negative temps
        
        if 'soil_pct_avg' in df.columns:
            df.loc[df['soil_pct_avg'] < 0, 'soil_pct_avg'] = np.nan      # Remove negative moisture
            df.loc[df['soil_pct_avg'] > 100, 'soil_pct_avg'] = np.nan    # Remove >100% moisture
        
        if 'plant_V_avg' in df.columns:
            df.loc[df['plant_V_avg'] < 0, 'plant_V_avg'] = np.nan        # Remove negative voltage
            df.loc[df['plant_V_avg'] > 5, 'plant_V_avg'] = np.nan        # Remove impossibly high voltage
        
        # Get last N hours
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_data = df[df['datetime'] >= cutoff]
        
        return df, recent_data
    
    def generate_daily_poem_prompt(self, generation_time=None, force_visual=False, selected_pattern=None, force_standard=False):
        """
        Generate poem prompt for today
        
        Args:
            generation_time: datetime object (default: now)
            force_visual: If True, force visual poetry regardless of auto-generation schedule
            selected_pattern: If provided, use this specific visual pattern (from manual selection)
            force_standard: If True, force standard (non-visual) poem - used by G key
        
        Returns:
            dict with prompt, metadata, and sensor footnote data
        """
        if generation_time is None:
            generation_time = datetime.now()
        
        # Load data
        full_df, data_24h = self.load_data(hours=24)
        
        if len(data_24h) == 0:
            raise ValueError("No data available in last 24 hours")
        
        # Current reading = most recent
        current_reading = data_24h.iloc[-1]
        
        # Score themes (pass full_df for memory theme)
        theme_analysis = ThemeScorer.score_all_themes(data_24h, current_reading, full_df)
        
        # Apply diversity scoring if repetition prevention is enabled
        if self.repetition_governor:
            # Get diversity scores for all themes
            ranked_themes = theme_analysis["ranked"]
            
            # Adjust scores based on recent usage
            adjusted_themes = []
            for theme_key, base_score in ranked_themes:
                diversity_score = self.repetition_governor.get_theme_diversity_score(theme_key)
                
                # Strong diversity boost to overcome scoring bias
                # diversity_score ranges 0-1, where 1 = never used recently
                # Formula: multiply overused themes by 0.4, boost unused themes by 2.2x
                # This ensures variety even when sensor conditions favor same theme
                diversity_multiplier = 0.4 + 1.8 * diversity_score
                adjusted_score = base_score * diversity_multiplier
                
                adjusted_themes.append((theme_key, adjusted_score, diversity_score))
            
            # Re-rank with adjusted scores
            adjusted_themes.sort(key=lambda x: x[1], reverse=True)
            
            # Update theme_analysis with diversity-adjusted primary theme
            theme_analysis["primary_theme"] = adjusted_themes[0][0]
            theme_analysis["primary_score"] = adjusted_themes[0][1]
            theme_analysis["ranked"] = [(t[0], t[1]) for t in adjusted_themes]  # Remove diversity_score from ranked
            
            # Log diversity adjustment
            top_theme = adjusted_themes[0]
            print(f"[REPETITION] Selected theme: {top_theme[0]} (base: {base_score:.2f} → diversity-adjusted: {top_theme[1]:.2f}, diversity: {top_theme[2]:.2f})")
        
        # Select influence (with diversity adjustment if available)
        influence_key = self.influence_selector.select_influence(
            primary_theme=theme_analysis["primary_theme"],
            secondary_theme=theme_analysis.get("secondary_theme"),
            randomness=0.12,  # 12% random as per both approaches
            repetition_governor=self.repetition_governor  # Pass diversity tracker
        )
        
        # Build sensor summary
        sensor_summary = self.prompt_generator.build_sensor_summary(data_24h, current_reading, full_df)
        
        # Add time and season context to sensor_summary
        time_period_experienced, _ = TimeContext.get_time_of_day_from_experience(data_24h)
        season, _ = TimeContext.get_season(generation_time)
        
        # Separate light experience from actual time of day
        hour = generation_time.hour
        if 5 <= hour < 12:
            time_period = "morning"
        elif 12 <= hour < 17:
            time_period = "afternoon"
        elif 17 <= hour < 21:
            time_period = "evening"
        else:
            time_period = "night"
        
        sensor_summary['light_experience'] = time_period_experienced
        sensor_summary['time_period'] = time_period
        sensor_summary['season'] = season
        
        # Detect modifiers
        human_context = ContextModifiers.detect_human_marks(data_24h)
        location_context = ContextModifiers.detect_location_context(data_24h, current_reading, full_df)
        multi_day_patterns = ContextModifiers.detect_multi_day_patterns(full_df, days=7)
        
        # Check if visual poetry should trigger (every 3rd generation)
        visual_pattern = None
        is_visual = False
        
        # If force_standard is True (G key), skip ALL visual logic entirely
        if force_standard:
            print("[VISUAL] Force standard mode - skipping all visual logic (G key)")
            # visual_pattern stays None, is_visual stays False
        else:
            # Determine if we should force visual
            force_visual_flag = force_visual  # Manual force from V key
            
            # Count recent auto-generations to determine if this should be visual (every 3rd)
            # Only count if NOT manually forced
            if not force_visual:
                try:
                    import os
                    csv_path = os.path.join(os.path.dirname(__file__), 'poem_generations.csv')
                    if os.path.exists(csv_path):
                        with open(csv_path, 'r') as f:
                            lines = [l for l in f if '20:00' in l and l.startswith('2025-')]
                            gen_count = len(lines)
                            # Every 3rd generation should be visual (1, 2, normal, 4, 5, visual, 7, 8, visual, etc.)
                            # Generation number starts at 1
                            next_gen_num = gen_count + 1
                            if next_gen_num % 3 == 0:
                                force_visual_flag = True
                                print(f"[VISUAL] Generation #{next_gen_num} - VISUAL (every 3rd)")
                            else:
                                print(f"[VISUAL] Generation #{next_gen_num} - normal")
                except Exception as e:
                    print(f"[VISUAL] Could not check generation count: {e}")
            else:
                print("[VISUAL] Manual visual forcing from V key")
            
            try:
                from visual_poetry_triggers import VisualPoetrySelector
                selector = VisualPoetrySelector()
                
                # Prepare 24-hour sensor data for pattern selection
                sensor_data_24hr = []
                for _, row in data_24h.iterrows():
                    sensor_data_24hr.append({
                        'voltage': row.get('voltage_v_avg', 0),
                        'moisture': row.get('moisture_pc_avg', 0),
                        'temp': row.get('temperature_c_avg', 0),
                        'light': row.get('lux_lx_avg', 0)
                    })
                
                # Check if user selected a specific pattern via V key
                if selected_pattern:
                    visual_pattern = selected_pattern
                    is_visual = True
                    print(f"[VISUAL] Using user-selected pattern: {selected_pattern}")
                else:
                    visual_pattern = selector.select_pattern(sensor_data_24hr)
                
                # Force visual if it's every 3rd generation OR manually forced, even if no pattern naturally triggered
                if force_visual_flag:
                    if not visual_pattern:
                        # Rotate through patterns to avoid repetition
                        # Tier 1: basic, Tier 2: advanced, Tier 3: complex
                        all_patterns = [
                            # Tier 1 - basic layouts
                            'centered_spine', 'center_stem', 'refrain_stack', 'right_droop', 'left_climb',
                            # Tier 2 - advanced layouts
                            'field_constellation', 'diagonal_pairing', 'distant_islands', 'minimal_drift',
                            # Tier 3 - complex layouts
                            'swarming_refrain', 'echo_cascade', 'forked_path', 'dense_field', 'central_thread', 'morph_ladder'
                        ]
                        
                        # Try to read last used pattern from latest_poem_data.json
                        last_pattern = None
                        try:
                            import os
                            import json
                            data_file = os.path.join(os.path.dirname(__file__), 'latest_poem_data.json')
                            if os.path.exists(data_file):
                                with open(data_file, 'r') as f:
                                    data = json.load(f)
                                    last_pattern = data.get('metadata', {}).get('visual_pattern')
                        except Exception as e:
                            print(f"[VISUAL] Could not read last pattern: {e}")
                        
                        # Select next pattern (rotate through the list)
                        if last_pattern and last_pattern in all_patterns:
                            # Get next pattern in the list
                            current_idx = all_patterns.index(last_pattern)
                            visual_pattern = all_patterns[(current_idx + 1) % len(all_patterns)]
                            print(f"[VISUAL] Rotating from {last_pattern} to {visual_pattern}")
                        else:
                            # No last pattern or invalid - use random
                            import random
                            visual_pattern = random.choice(all_patterns)
                            print(f"[VISUAL] Random pattern (no previous): {visual_pattern}")
                    is_visual = True
                elif visual_pattern:
                    is_visual = True
                    print(f"[VISUAL] Pattern triggered: {visual_pattern}")
                else:
                    print("[VISUAL] No pattern triggered - using standard layout")
                    
            except Exception as e:
                print(f"[VISUAL] Pattern selection failed: {e}")
                visual_pattern = None
                is_visual = False
        
        # Generate prompt (visual or standard)
        if is_visual and visual_pattern:
            prompt = self._generate_visual_prompt(
                date=generation_time,
                theme_analysis=theme_analysis,
                influence_key=influence_key,
                sensor_summary=sensor_summary,
                visual_pattern=visual_pattern,
                human_context=human_context,
                location_context=location_context,
                multi_day_patterns=multi_day_patterns
            )
        else:
            prompt = self.prompt_generator.generate_prompt(
                date=generation_time,
                theme_analysis=theme_analysis,
                influence_key=influence_key,
                sensor_summary=sensor_summary,
                human_context=human_context,
                location_context=location_context,
                multi_day_patterns=multi_day_patterns,
                repetition_governor=self.repetition_governor
            )
        
        # Prepare metadata for saving
        metadata = {
            "generation_date": generation_time.isoformat(),
            "primary_theme": theme_analysis["primary_theme"],
            "theme_score": theme_analysis["primary_score"],
            "secondary_theme": theme_analysis.get("secondary_theme"),
            "influence": influence_key,
            "influence_name": INFLUENCES[influence_key]["name"],
            "sensor_readings": {
                "moisture": f"{sensor_summary['moisture']['current']:.1f}%",
                "temperature": f"{sensor_summary['temperature']['current']:.1f}C",
                "humidity": f"{sensor_summary['humidity']['current']:.1f}%" if sensor_summary['humidity']['current'] else "N/A",
                "pressure": f"{sensor_summary['pressure']['current']:.0f} hPa" if sensor_summary['pressure']['current'] else "N/A",
                "light": f"{sensor_summary['light']['current']:.1f} lux" if not np.isnan(sensor_summary['light']['current']) else "N/A"
            },
            "human_interaction": human_context is not None,
            "location": location_context["current"] if location_context else "unknown",
            "multi_day_patterns": multi_day_patterns,
            "is_visual": is_visual,
            "visual_pattern": visual_pattern
        }
        
        # Build sensor footnote
        footnote = self._build_footnote(generation_time, theme_analysis, influence_key, sensor_summary, human_context, location_context, multi_day_patterns)
        
        return {
            "prompt": prompt,
            "metadata": metadata,
            "footnote": footnote,
            "theme_analysis": theme_analysis,
            "sensor_summary": sensor_summary
        }
    
    def generate_weekly_poem_prompt(self, generation_time=None):
        """
        Generate poem prompt reflecting on the entire week
        
        Args:
            generation_time: datetime object (default: now)
        
        Returns:
            dict with prompt, metadata, and sensor footnote data
        """
        if generation_time is None:
            generation_time = datetime.now()
        
        # Load full week of data
        full_df, data_7days = self.load_data(hours=168)  # 7 days = 168 hours
        
        if len(data_7days) == 0:
            raise ValueError("No data available in last 7 days")
        
        # Most recent reading
        current_reading = data_7days.iloc[-1]
        
        # Analyze weekly themes - use full week for context
        theme_analysis = ThemeScorer.score_all_themes(data_7days, current_reading, full_df)
        
        # Select influence
        influence_key = self.influence_selector.select_influence(
            primary_theme=theme_analysis["primary_theme"],
            secondary_theme=theme_analysis.get("secondary_theme"),
            randomness=0.12
        )
        
        # Build weekly sensor summary (7-day focus)
        sensor_summary = self._build_weekly_sensor_summary(data_7days, current_reading, full_df)
        
        # Detect patterns across the week
        human_context = ContextModifiers.detect_human_marks(data_7days)
        location_context = ContextModifiers.detect_location_context(data_7days, current_reading, full_df)
        multi_week_patterns = ContextModifiers.detect_multi_day_patterns(full_df, days=14)  # Look at 2 weeks for weekly poem
        
        # Visual pattern selection (30% chance for weekly poems too)
        visual_pattern = None
        is_visual = False
        try:
            from visual_poetry_triggers import VisualPoetrySelector
            selector = VisualPoetrySelector()
            
            # Use last 24 hours of the week for pattern detection
            data_24h = data_7days.tail(288) if len(data_7days) >= 288 else data_7days
            sensor_data_24hr = []
            for _, row in data_24h.iterrows():
                sensor_data_24hr.append({
                    'voltage': row.get('voltage_v_avg', 0),
                    'moisture': row.get('moisture_pc_avg', 0),
                    'temp': row.get('temperature_c_avg', 0),
                    'light': row.get('lux_lx_avg', 0)
                })
            
            visual_pattern = selector.select_pattern(sensor_data_24hr)
            
            if visual_pattern:
                is_visual = True
                print(f"[VISUAL WEEKLY] Pattern triggered: {visual_pattern}")
            else:
                print("[VISUAL WEEKLY] No pattern triggered - using standard layout")
                
        except Exception as e:
            print(f"[VISUAL WEEKLY] Pattern selection failed: {e}")
            visual_pattern = None
            is_visual = False
        
        # Generate weekly prompt (visual or standard)
        if is_visual and visual_pattern:
            prompt = self._generate_visual_prompt(
                date=generation_time,
                theme_analysis=theme_analysis,
                influence_key=influence_key,
                sensor_summary=sensor_summary,
                visual_pattern=visual_pattern,
                human_context=human_context,
                location_context=location_context,
                multi_day_patterns=multi_week_patterns
            )
        else:
            prompt = self._generate_weekly_prompt(
                date=generation_time,
                theme_analysis=theme_analysis,
                influence_key=influence_key,
                sensor_summary=sensor_summary,
                data_7days=data_7days,
                human_context=human_context,
                location_context=location_context,
                multi_week_patterns=multi_week_patterns
            )
        
        # Metadata
        metadata = {
            "generation_date": generation_time.isoformat(),
            "poem_type": "weekly",
            "primary_theme": theme_analysis["primary_theme"],
            "theme_score": theme_analysis["primary_score"],
            "secondary_theme": theme_analysis.get("secondary_theme"),
            "influence": influence_key,
            "influence_name": INFLUENCES[influence_key]["name"],
            "visual_pattern": visual_pattern if is_visual else "standard",
            "sensor_readings": {
                "moisture": f"{sensor_summary['moisture']['current']:.1f}% (week avg: {sensor_summary['moisture'].get('avg_week', sensor_summary['moisture']['avg_24h']):.1f}%)",
                "temperature": f"{sensor_summary['temperature']['current']:.1f}C (week avg: {sensor_summary['temperature'].get('avg_week', sensor_summary['temperature']['avg_24h']):.1f}C)",
                "humidity": f"{sensor_summary['humidity']['current']:.1f}%" if sensor_summary.get('humidity', {}).get('current') else "N/A",
                "pressure": f"{sensor_summary['pressure']['current']:.0f} hPa" if sensor_summary.get('pressure', {}).get('current') else "N/A",
                "light": f"{sensor_summary['light']['current']:.1f} lux" if sensor_summary.get('light', {}).get('current') else "N/A"
            },
            "human_interaction": human_context is not None,
            "location": location_context["current"] if location_context else "unknown",
            "multi_day_patterns": multi_week_patterns
        }
        
        # Build weekly footnote
        footnote = self._build_weekly_footnote(generation_time, theme_analysis, influence_key, sensor_summary, human_context, location_context, data_7days)
        
        return {
            "prompt": prompt,
            "metadata": metadata,
            "footnote": footnote,
            "theme_analysis": theme_analysis,
            "sensor_summary": sensor_summary,
            "poem_type": "weekly"
        }
    
    def _generate_visual_prompt(self, date, theme_analysis, influence_key, sensor_summary, 
                                visual_pattern, human_context, location_context, multi_day_patterns):
        """
        Generate prompt for visual/concrete poetry - LEAN VERSION
        """
        from visual_poetry_triggers import PATTERN_DESCRIPTIONS
        import random
        
        # Get pattern metadata
        pattern_info = PATTERN_DESCRIPTIONS.get(visual_pattern, {})
        pattern_name = pattern_info.get('name', visual_pattern)
        pattern_emotion = pattern_info.get('emotion', 'intensity')
        
        # Build base context
        theme_name = ThemeScorer.THEMES[theme_analysis["primary_theme"]]["name"]
        influence = INFLUENCES[influence_key]
        
        # Extract just the author name (before the " - " separator)
        full_influence_name = influence['name']
        if ' - ' in full_influence_name:
            author_name = full_influence_name.split(' - ')[0]
        else:
            author_name = full_influence_name
        
        # Get season
        season, season_desc = TimeContext.get_season(date)
        
        # Select perspective mode (40% plant, 60% abstract)
        perspective_roll = random.random()
        if perspective_roll < 0.40:
            perspective_text = "PLANT: roots, leaves, growth imagery"
        else:
            perspective_text = "UNIVERSAL: any living consciousness"
        
        # Build atmospheric description
        atmospheric = ExperientialMetaphors.build_atmospheric_paragraph(
            sensor_summary,
            multi_day_patterns
        )
        
        # Get recent titles
        recent_titles = PromptGenerator._get_recent_titles(self.repetition_governor, limit=10)
        titles_section = "\n".join(f"  - {t}" for t in recent_titles) if recent_titles else "  (none yet)"
        
        # Get visual layout instructions (these are essential - keep full detail)
        layout_instructions = self._get_visual_layout_instructions(visual_pattern)
        
        # Build lean prompt
        prompt = f"""You are creating a VISUAL/CONCRETE poem where shape is meaning.

=== CONTEXT ===
Date: {date.strftime('%B %d, %Y')} | Season: {season} - {season_desc}
Perspective: {perspective_text}
Theme: {theme_name}
Write in the style of {author_name}: {influence['tone_modifiers']}

=== ATMOSPHERE ===
{atmospheric}

=== VISUAL PATTERN: {pattern_name} ===
Emotional quality: {pattern_emotion}

{layout_instructions}

=== CONSTRAINTS ===
• 6-8 lines maximum, SHORT lines only (max 50 characters per line)
• Title: 2-4 words, lowercase, must echo something in the poem

NEVER USE:
• Numbers, percentages, measurements
• Technical: voltage, sensor, moisture, lux, data, signal
• Religious: devotion, faith, prayer, divine
• Overused: hum, pulse, verdant, thirst

RECENT TITLES (avoid):
{titles_section}

=== OUTPUT ===
[title - lowercase]

[Visual poem following pattern above]

No footnotes. End with your last poetic line."""
        
        return prompt
    
    def _get_visual_layout_instructions(self, pattern_key):
        """Get specific layout instructions for each visual pattern"""
        
        layouts = {
            # TIER 1 PATTERNS
            "centered_spine": """VISUAL LAYOUT: Centered Spine
- Each line is CENTERED on the page
- Lines stack vertically down the center
- Creates a strong vertical axis
- Like a backbone or trunk
- Symmetrical, stable, grounded
- EACH LINE MUST BE SHORT (max 6-8 words)

Example structure:
         line one here
       line two words
     third line text
       fourth line
         fifth

Use natural line breaks. Keep lines SHORT for visual balance.""",

            "center_stem": """VISUAL LAYOUT: Center Stem
- Similar to Centered Spine but SHORTER (4-6 lines maximum)
- Each line CENTERED
- Compact, condensed
- Like a short vertical stem or pillar
- EACH LINE MUST BE SHORT (max 5-6 words)

Example structure:
         line one
       line two
     third line
       fourth

Brief and concentrated. Keep lines SHORT.""",

            "right_droop": """VISUAL LAYOUT: Right-Leaning Droop
- Lines start at LEFT margin
- Each successive line is INDENTED MORE to the right
- Creates a cascading, drooping effect
- Like wilting or falling
- Gravity pulling downward and rightward
- EACH LINE MUST BE SHORT (max 5-6 words)

Example structure:
short phrase
  another phrase
    three words here
      brief line
        final words

Progressive rightward movement. Keep lines SHORT.""",

            "left_climb": """VISUAL LAYOUT: Left-Grounded Climb
- Lines start DEEPLY INDENTED on the left
- Each line moves BACK toward the left margin
- Creates upward, rising movement
- Rooted but ascending
- EACH LINE MUST BE SHORT (max 5-6 words)

Example structure:
                    short phrase
                another line
            three words
        brief line
    final words

Climbing back to the left, rising upward.""",

            "refrain_stack": """VISUAL LAYOUT: Refrain Stack
- REPEAT a key phrase or word 3-5 times
- Stack vertically
- Can be centered or left-aligned
- Emphasis through repetition
- Creates urgency, intensity
- ALL LINES MUST BE SHORT (max 5-6 words per line)
- The "different line" between refrains should also be brief

Example structure:
the word
the word
the word
brief different phrase here
the word
the word

Repetition creates weight and alarm. Keep ALL lines short - no prose sentences.""",

            # TIER 2 PATTERNS
            "field_constellation": """VISUAL LAYOUT: Field Constellation
- Words/phrases SCATTERED across the page
- Various positions (left, center, right, indented)
- Creates sense of stars in space
- No linear reading path
- Reader navigates the field

Example structure:
word here
              another word
    phrase
                       far word
         middle

Spatial distribution matters.""",

            "diagonal_pairing": """VISUAL LAYOUT: Diagonal Pairing
- Two parallel diagonal paths
- One descending left-to-right
- One ascending left-to-right
- Can represent contrasts or dual states

Example structure:
line          
  line
    line
          line
       line
    line

Two trajectories, two voices.""",

            "distant_islands": """VISUAL LAYOUT: Distant Islands
- 3-5 SHORT phrases or single words
- LARGE VERTICAL GAPS between them
- Isolated, floating
- Emphasizes silence and space

Example structure:
word

[large gap]

another

[large gap]

final

Isolation and distance.""",

            "minimal_drift": """VISUAL LAYOUT: Minimal Drift
- VERY FEW words (3-5 total)
- Sparse placement
- Lots of white space
- Quiet, subtle
- Less is more

Example structure:
             word


    another


                  last

Extreme minimalism.""",

            # TIER 3 PATTERNS (advanced)
            "swarming_refrain": """VISUAL LAYOUT: Swarming Refrain
- CHAOTIC repetition of 2-3 phrases
- Overlapping, stuttering
- Different positions
- Creates visual noise

Example structure:
word word
    word  another
word    another word
  another  word
word another word

Disordered, buzzing.""",

            "echo_cascade": """VISUAL LAYOUT: Echo Cascade
- Start with ONE phrase (4-6 words)
- REDUCE by 1-2 words each line
- Maximum 5-6 lines per cascade
- ONLY ONE cascade section (do NOT repeat the pattern)
- Total poem: 8-10 lines MAXIMUM

Example structure:
the morning finds me here
  the morning finds me
    the morning finds
      the morning
        the

CRITICAL: Keep it SHORT. One cascade only.""",

            "forked_path": """VISUAL LAYOUT: Forked Path
- Start centered or left
- Lines SPLIT into two branches
- Diverging paths
- Choice or transformation point

Example structure:
      start
    
  left path          right path
left continues       right continues

Bifurcation.""",

            "dense_field": """VISUAL LAYOUT: Dense Field
- Short phrases packed tightly LEFT-ALIGNED
- Each phrase on its own line, but NO extra spacing
- Keep it SHORT: 6-8 lines maximum
- Lines should be brief (3-5 words each)
- Creates visual density through compact arrangement

Example structure:
the wet arrives
roots drinking
cells opening
green expanding
warmth rising
no pause
just becoming

Compression through brevity, not run-on sentences.""",

            "central_thread": """VISUAL LAYOUT: Central Thread with Walls
- Central vertical column of words
- Flanked by text "walls" on both sides
- Creates corridor or channel
- Text compressed

Example structure:
xxxxx  word  xxxxx
xxxxx  word  xxxxx
xxxxx  word  xxxxx

Corridor of meaning.""",

            "morph_ladder": """VISUAL LAYOUT: Morph Ladder
- Word transforms letter by letter
- Each line shows one letter change
- Vertical progression
- Linguistic metamorphosis

Example structure:
word
ward
hard
hart
part

Gradual transformation."""
        }
        
        # Add universal line limit reminder to all patterns
        base_instruction = layouts.get(pattern_key, layouts["centered_spine"])
        line_limit_warning = """

*** CRITICAL LINE LIMIT ***
Your ENTIRE poem must fit on a single screen/canvas.
MAXIMUM 10 lines total (including title).
If your pattern involves repetition or cascading, keep it to ONE section only.
SHORTER is BETTER. Do not exceed 10 lines."""
        
        return base_instruction + line_limit_warning
    
    def record_generated_poem(self, poem_text, theme, influence, generation_date=None):
        """Record a generated poem for diversity tracking
        
        Args:
            poem_text: The complete poem text
            theme: Theme key used
            influence: Influence key used
            generation_date: ISO date string (optional)
        """
        if not self.repetition_governor:
            return
        
        # Record in history
        self.repetition_governor.record_poem(
            poem_text=poem_text,
            theme=theme,
            influence=influence,
            generation_date=generation_date
        )
        
        # Check for safe mode
        if REPETITION_PREVENTION_AVAILABLE:
            is_safe_mode, indicators = SafeModeDetector.detect_safe_mode(poem_text)
            if is_safe_mode:
                print(f"[SAFE MODE DETECTED] This poem triggered {len(indicators)} safe mode indicators:")
                for ind in indicators:
                    print(f"  - {ind}")
                print("[RECOMMENDATION] Consider regenerating with different theme/influence combination")
            
            # Check for overused phrases
            is_phrase_safe, overused = self.repetition_governor.check_phrase_safety(poem_text, max_overused=2)
            if not is_phrase_safe:
                print(f"[PHRASE WARNING] Poem contains {len(overused)} overused phrases:")
                for phrase in overused[:5]:  # Show first 5
                    print(f"  - '{phrase}'")
    
    def get_diversity_report(self):
        """Get usage report from repetition governor"""
        if not self.repetition_governor:
            return "Diversity tracking not available"
        
        return self.repetition_governor.get_usage_report()
    
    def _build_footnote(self, date, theme_analysis, influence_key, sensor_summary, human_context, location_context, multi_day_patterns=None):
        """Build formatted footnote with creative prompt and sensor data"""
        
        theme_name = ThemeScorer.THEMES[theme_analysis["primary_theme"]]["name"]
        theme_emotion = ThemeScorer.THEMES[theme_analysis["primary_theme"]]["emotional_translation"]
        influence = INFLUENCES[influence_key]
        influence_name = influence["name"]
        
        # Extract just the author name (before the " - " separator)
        if ' - ' in influence_name:
            author_name = influence_name.split(' - ')[0]
        else:
            author_name = influence_name
        
        # Get time and season context
        if isinstance(sensor_summary, dict) and 'data_24h' in sensor_summary:
            time_period_experienced, _ = TimeContext.get_time_of_day_from_experience(sensor_summary.get('data_24h'))
        else:
            time_period_experienced = "ambient light"
        
        season, seasonal_flavor = TimeContext.get_season(date)
        
        # Build atmospheric paragraph from metaphors
        atmospheric_paragraph = ExperientialMetaphors.build_atmospheric_paragraph(
            sensor_summary, 
            multi_day_patterns
        )
        
        # =====================================================================
        # FOOTNOTE: SENSOR DATA & PATTERNS ONLY
        # (The creative prompt is handled separately for carousel image 2)
        # =====================================================================
        footnote = f"""SENSOR SUMMARY
"""
        
        # =====================================================================
        # PART 2: SENSOR DATA
        # =====================================================================
        
        # Extract sensor values
        if isinstance(sensor_summary, dict):
            # Humidity
            if 'humidity' in sensor_summary and isinstance(sensor_summary['humidity'], dict):
                h_curr = sensor_summary['humidity'].get('current')
                if h_curr is not None:
                    footnote += f"\nHumidity: {h_curr:.1f}%"
            
            # Pressure
            if 'pressure' in sensor_summary and isinstance(sensor_summary['pressure'], dict):
                p_curr = sensor_summary['pressure'].get('current')
                p_change = sensor_summary['pressure'].get('change_24h', 0)
                if p_curr is not None:
                    footnote += f"\nPressure: {p_curr:.0f} hPa"
                    if p_change and abs(p_change) > 0.5:
                        footnote += f" ({p_change:+.1f} today)"
            
            # Moisture
            if 'moisture' in sensor_summary and isinstance(sensor_summary['moisture'], dict):
                m_curr = sensor_summary['moisture'].get('current', 0)
                m_change = sensor_summary['moisture'].get('change_24h', 0)
                footnote += f"\nMoisture: {m_curr:.1f}%"
                if m_change:
                    footnote += f" ({m_change:+.1f}% today)"
            
            # Temperature
            if 'temperature' in sensor_summary and isinstance(sensor_summary['temperature'], dict):
                t_curr = sensor_summary['temperature'].get('current', 0)
                t_min = sensor_summary['temperature'].get('min_24h', 0)
                t_max = sensor_summary['temperature'].get('max_24h', 0)
                footnote += f"\nTemp: {t_curr:.1f}C (today: {t_min:.1f}-{t_max:.1f}C)"
            
            # Light
            if 'light' in sensor_summary and isinstance(sensor_summary['light'], dict):
                l_curr = sensor_summary['light'].get('current', 0)
                l_avg = sensor_summary['light'].get('avg_24h', 0)
                if l_curr and not np.isnan(l_curr):
                    footnote += f"\nLight: {l_curr:.0f} lux"
                elif l_avg and not np.isnan(l_avg):
                    footnote += f"\nLight: {l_avg:.0f} lux (24h avg)"
        
        # =====================================================================
        # PART 3: PATTERNS
        # =====================================================================
        if multi_day_patterns:
            footnote += "\n\nPatterns:"
            for pattern in multi_day_patterns:
                footnote += f"\n  {pattern}"
        
        # =====================================================================
        # PART 4: GENERATION INFO
        # =====================================================================
        footnote += f"\n\n---\nGenerated: {date.strftime('%b %d, %Y at %I:%M %p')}"
        footnote += f"\nStyled after: {influence_name}"
        footnote += f"\n(AI prompted in the spirit of this poet's techniques, not replicating their work)"
        
        return footnote
    
    def _build_weekly_sensor_summary(self, data_7days, current_reading, full_df=None):
        """Build sensor summary focusing on weekly patterns and changes.
        
        NOTE: Voltage sensor disabled 2026-01-02 - handles None/NaN gracefully.
        """
        voltage_values = data_7days['plant_V_avg'].dropna().values
        moisture_values = data_7days['soil_pct_avg'].values
        temp_values = data_7days['temp_C_avg'].values
        lux_values = data_7days['lux_lx_avg'].dropna().values if 'lux_lx_avg' in data_7days.columns else []
        
        # Calculate week-over-week changes (handle missing voltage)
        if len(voltage_values) > 0:
            week_start = voltage_values[0]
            week_end = current_reading.get('plant_V_avg') if current_reading.get('plant_V_avg') is not None else voltage_values[-1]
            voltage_summary = {
                "current": current_reading.get('plant_V_avg'),
                "avg_week": np.mean(voltage_values),
                "min_week": np.min(voltage_values),
                "max_week": np.max(voltage_values),
                "change_week": week_end - week_start if week_end is not None else 0,
                "std_week": np.std(voltage_values)
            }
        else:
            # No voltage data - sensor disabled
            voltage_summary = {
                "current": None,
                "avg_week": None,
                "min_week": None,
                "max_week": None,
                "change_week": None,
                "std_week": None
            }
        
        moisture_start = moisture_values[0] if len(moisture_values) > 0 else current_reading['soil_pct_avg']
        moisture_end = current_reading['soil_pct_avg']
        
        summary = {
            "voltage": voltage_summary,
            "moisture": {
                "current": current_reading['soil_pct_avg'],
                "avg_week": np.mean(moisture_values),
                "min_week": np.min(moisture_values),
                "max_week": np.max(moisture_values),
                "change_week": moisture_end - moisture_start
            },
            "temperature": {
                "current": current_reading['temp_C_avg'],
                "avg_week": np.mean(temp_values),
                "min_week": np.min(temp_values),
                "max_week": np.max(temp_values)
            },
            "light": {
                "current": current_reading.get('lux_lx_avg', np.nan),
                "avg_week": np.mean(lux_values) if len(lux_values) > 0 else np.nan,
                "max_week": np.max(lux_values) if len(lux_values) > 0 else np.nan
            },
            "data_7days": data_7days,
            "full_df": full_df
        }
        
        # Add time period based on when the weekly poem is generated
        # (Weekly poems are typically generated Sunday 8am)
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_period = "morning"
        elif 12 <= hour < 17:
            time_period = "afternoon"
        elif 17 <= hour < 21:
            time_period = "evening"
        else:
            time_period = "night"
        
        summary['time_period'] = time_period
        
        return summary
    
    def _generate_weekly_prompt(self, date, theme_analysis, influence_key, sensor_summary, data_7days, human_context, location_context, multi_week_patterns):
        """Generate prompt for weekly reflection poem"""
        influence = INFLUENCES[influence_key]
        
        # Get season context
        season, seasonal_flavor = TimeContext.get_season(date)
        
        # Get theme details
        theme_details = ThemeScorer.THEMES[theme_analysis["primary_theme"]]
        
        prompt = f"""=== WEEKLY REFLECTION POEM ===

You are generating a poem that reflects on an entire week of a plant's life, not just a single day.

DATE: {date.strftime('%A, %B %d, %Y')}
SEASON: {season.capitalize()} - {seasonal_flavor}
REFLECTION PERIOD: Past 7 days

=== THEME ANALYSIS ===
PRIMARY THEME: {theme_details['name']}
Score: {theme_analysis['primary_score']:.2f}
Emotional translation: {theme_details['emotional_translation']}
"""
        
        if theme_analysis.get("secondary_theme"):
            sec_theme = ThemeScorer.THEMES[theme_analysis["secondary_theme"]]
            prompt += f"""
SECONDARY THEME: {sec_theme['name']}
Emotional translation: {sec_theme['emotional_translation']}
"""
        
        prompt += f"""
=== WEEKLY SENSOR DATA (7-day overview) ===

VOLTAGE (bioelectric patterns over the week):
  Current: {sensor_summary['voltage']['current']:.3f}V
  Week average: {sensor_summary['voltage']['avg_week']:.3f}V
  Week range: {sensor_summary['voltage']['min_week']:.3f}V - {sensor_summary['voltage']['max_week']:.3f}V
  Change over week: {sensor_summary['voltage']['change_week']:+.3f}V
  Stability: {sensor_summary['voltage']['std_week']:.3f} (std dev)
  
SOIL MOISTURE (hydration patterns):
  Current: {sensor_summary['moisture']['current']:.1f}%
  Week average: {sensor_summary['moisture']['avg_week']:.1f}%
  Week range: {sensor_summary['moisture']['min_week']:.1f}% - {sensor_summary['moisture']['max_week']:.1f}%
  Change over week: {sensor_summary['moisture']['change_week']:+.1f}%
  
TEMPERATURE (thermal experience):
  Current: {sensor_summary['temperature']['current']:.1f}C
  Week average: {sensor_summary['temperature']['avg_week']:.1f}C
  Week range: {sensor_summary['temperature']['min_week']:.1f}C - {sensor_summary['temperature']['max_week']:.1f}C
  
LIGHT (weekly exposure):
  Current: {sensor_summary['light']['current']:.1f} lux
  Week average: {sensor_summary['light']['avg_week']:.1f} lux
  Peak: {sensor_summary['light']['max_week']:.1f} lux
"""
        
        # Add multi-week patterns if detected
        if multi_week_patterns:
            prompt += f"\n\n=== PATTERNS OVER TIME ===\n"
            for pattern in multi_week_patterns:
                prompt += f"- {pattern}\n"
        
        # NOTE: human_context (marks) no longer influences poem content
        # Marks only trigger burst generation, they don't add to the prompt
        
        # Extract just the author name for weekly poem
        full_influence_name = influence['name']
        if ' - ' in full_influence_name:
            author_name = full_influence_name.split(' - ')[0]
        else:
            author_name = full_influence_name
        
        prompt += f"""

=== STYLISTIC INFLUENCE ===
Write in the style of {author_name}: {influence['description'].lower()}

Style markers: {', '.join(influence['style_markers'][:3])}
Techniques: {influence['techniques']}

=== WEEKLY REFLECTION GUIDANCE ===

This is a WEEKLY poem, not a daily snapshot. Consider:
- How did conditions change over the 7 days?
- Were there cycles (day/night, watering, temperature swings)?
- What was the overall arc of the week?
- Did stability or change dominate?
- How does this week compare to longer patterns?

Your poem should capture the ESSENCE of the week - not just the final moment, but the journey through 7 days of experience.

CRITICAL: Do not mention in the poem:
- Specific numbers in ANY form (percentages like "3%" OR "three percent" OR "seventeen degrees" OR "thirty degrees", voltages, lux measurements) - ALWAYS reinterpret data creatively (e.g., "40%" OR "forty percent" becomes "half-satisfied thirst", "17C then 30C" becomes "from cool to warm", "from thin air to fullness")
- Technical sensor terms: "voltage", "moisture percentage", "lux", "degrees", "sensor"
- The location by name ("office", "garden", "shelf")
- That you are being observed or measured
- References to humans, observers, or being touched/tended
- Religious terms, concepts, or imagery (no prayers, blessings, divine references, sacred language)
- Sexual or steamy content (no sensuality, eroticism, or suggestive language)

Instead: Feel the WEEK's journey. Experience cycles. Notice patterns. Sense changes over time.
Translate measurements into emotional/sensory arcs: voltage fluctuations = energy rhythms over days, moisture patterns = cycles of satisfaction and need, temperature swings = the week's thermal story.

"""
        
        # Get time and season for footnote
        time_period_experienced, _ = TimeContext.get_time_of_day_from_experience(sensor_summary.get('data_7days'))
        
        # Calculate observation duration
        observation_duration = ""
        full_df = sensor_summary.get('full_df')
        if full_df is not None and len(full_df) > 0 and 'datetime' in full_df.columns:
            try:
                first_reading = pd.to_datetime(full_df['datetime'].iloc[0])
                last_reading = pd.to_datetime(full_df['datetime'].iloc[-1])
                total_days = (last_reading - first_reading).days
                if total_days < 30:
                    observation_duration = f"\nObservation period: {total_days} days"
                else:
                    weeks = total_days // 7
                    observation_duration = f"\nObservation period: {weeks} weeks ({total_days} days)"
            except Exception:
                pass
        
        # Build footnote template for Claude to fill in
        # Construct sensor lines with NaN checks
        sensor_lines = []
        
        # Voltage
        v_curr = sensor_summary['voltage']['current']
        v_avg = sensor_summary['voltage'].get('avg_week', np.nan)
        v_min = sensor_summary['voltage'].get('min_week', np.nan)
        v_max = sensor_summary['voltage'].get('max_week', np.nan)
        if pd.notna(v_avg) and pd.notna(v_min) and pd.notna(v_max):
            sensor_lines.append(f"V: {v_curr:.3f}V (week avg: {v_avg:.3f}V, range: {v_min:.3f}-{v_max:.3f}V)")
        else:
            sensor_lines.append(f"V: {v_curr:.3f}V")
        
        # Moisture
        m_curr = sensor_summary['moisture'].get('current', np.nan)
        m_avg = sensor_summary['moisture'].get('avg_week', np.nan)
        m_change = sensor_summary['moisture'].get('change_week', np.nan)
        if pd.notna(m_curr):
            if pd.notna(m_avg) and pd.notna(m_change):
                sensor_lines.append(f"Moisture: {m_curr:.1f}% (week avg: {m_avg:.1f}%, {m_change:+.1f}% change)")
            else:
                sensor_lines.append(f"Moisture: {m_curr:.1f}%")
        
        # Temperature
        t_curr = sensor_summary['temperature'].get('current', np.nan)
        t_avg = sensor_summary['temperature'].get('avg_week', np.nan)
        t_min = sensor_summary['temperature'].get('min_week', np.nan)
        t_max = sensor_summary['temperature'].get('max_week', np.nan)
        if pd.notna(t_curr):
            if pd.notna(t_avg) and pd.notna(t_min) and pd.notna(t_max):
                sensor_lines.append(f"Temp: {t_curr:.1f}C (week avg: {t_avg:.1f}C, range: {t_min:.1f}-{t_max:.1f}C)")
            else:
                sensor_lines.append(f"Temp: {t_curr:.1f}C")
        
        # Light
        l_curr = sensor_summary['light'].get('current', np.nan)
        l_avg = sensor_summary['light'].get('avg_week', np.nan)
        if pd.notna(l_curr):
            if pd.notna(l_avg):
                sensor_lines.append(f"Light: {l_curr:.1f} lux (week avg: {l_avg:.1f} lux)")
            else:
                sensor_lines.append(f"Light: {l_curr:.1f} lux")
        
        footnote_data = f"""
Generated: {date.strftime('%b %d, %Y at %I:%M %p')}{observation_duration}

Light exp: {time_period_experienced.capitalize()} | Season: {season.capitalize()}

Theme: {theme_details['name']} (score: {theme_analysis['primary_score']:.2f})

Title: [POEM TITLE WILL APPEAR HERE]

Visual style: standard

Weekly sensor summary:
"""
        
        # Add sensor lines
        for line in sensor_lines:
            footnote_data += f"{line}\n"
        
        if multi_week_patterns:
            footnote_data += f"\n\nPatterns:\n"
            for pattern in multi_week_patterns:
                footnote_data += f"- {pattern}\n"
            # Remove trailing newline from last pattern
            footnote_data = footnote_data.rstrip('\n')
        
        if human_context and human_context.get("occurred"):
            footnote_data += f"\n\nHuman: {human_context['count']} event(s)"
            if human_context.get('latest_note'):
                footnote_data += f" | \"{human_context['latest_note']}\""
        
        footnote_data += f"\n\nStyled after: {influence['name']}"
        
        # Final instructions
        prompt += f"""=== OUTPUT FORMAT ===

Generate your response in this exact format:

[POEM TITLE - evocative, poetic, 3-7 words]

[The poem itself - 10-14 lines of free verse, weekly reflection]

{footnote_data}

IMPORTANT: In the footnote above, replace "[POEM TITLE WILL APPEAR HERE]" with your actual poem title.

=== POEM REQUIREMENTS ===
- Title: Create an evocative title that captures the essence of the WEEK
- Voice: First-person from plant's perspective, reflecting on 7 days
- Length: 10-14 lines (concise weekly reflection)
- Form: Free verse, but shaped by the stylistic influence
- Scope: This is about a WEEK, not a day - consider cycles, changes, patterns over time
- Tone: Match to the week's overall character (stable vs dynamic, stressful vs peaceful)
- Variation: Apply same creativity and variation guidelines as daily poems

Write the complete output now: title, poem, then the exact footnote shown above.
"""
        
        return prompt
    
    def _build_weekly_footnote(self, date, theme_analysis, influence_key, sensor_summary, human_context, location_context, data_7days):
        """Build formatted footnote for weekly poem - MATCHES DAILY FORMAT"""
        theme_name = ThemeScorer.THEMES[theme_analysis["primary_theme"]]["name"]
        influence_name = INFLUENCES[influence_key]["name"]
        
        time_period_experienced, _ = TimeContext.get_time_of_day_from_experience(data_7days)
        season, _ = TimeContext.get_season(date)
        
        # Calculate observation duration
        observation_duration = "Observation period: 4 weeks (32 days)"
        full_df = sensor_summary.get('full_df')
        if full_df is not None and len(full_df) > 0 and 'datetime' in full_df.columns:
            try:
                first_reading = pd.to_datetime(full_df['datetime'].iloc[0])
                last_reading = pd.to_datetime(full_df['datetime'].iloc[-1])
                total_days = (last_reading - first_reading).days
                
                if total_days < 30:
                    observation_duration = f"Observation period: {total_days} days"
                else:
                    weeks = total_days // 7
                    observation_duration = f"Observation period: {weeks} weeks ({total_days} days)"
            except Exception:
                pass
        
        # Build footnote in EXACT format (matching daily)
        footnote = f"""Generated: {date.strftime('%b %d, %Y at %I:%M %p')}
{observation_duration}

Light exp: {time_period_experienced.capitalize()} | Season: {season.capitalize()}

Theme: {theme_name} (score: {theme_analysis['primary_score']:.2f})

Title: {theme_analysis.get('title', 'untitled')}

Visual style: {theme_analysis.get('visual_pattern', 'standard')}

Weekly sensor summary:"""
        
        # Extract sensor values with NaN handling
        v_current = sensor_summary['voltage'].get('current', np.nan)
        v_avg = sensor_summary['voltage'].get('avg_week', np.nan)
        v_min = sensor_summary['voltage'].get('min_week', np.nan)
        v_max = sensor_summary['voltage'].get('max_week', np.nan)
        
        if pd.notna(v_current):
            if pd.notna(v_avg) and pd.notna(v_min) and pd.notna(v_max):
                footnote += f"\nV: {v_current:.3f}V (week avg: {v_avg:.3f}V, range: {v_min:.3f}-{v_max:.3f}V)"
            else:
                footnote += f"\nV: {v_current:.3f}V"
        
        m_current = sensor_summary['moisture'].get('current', np.nan)
        m_avg = sensor_summary['moisture'].get('avg_week', np.nan)
        m_change = sensor_summary['moisture'].get('change_week', np.nan)
        
        if pd.notna(m_current):
            if pd.notna(m_avg) and pd.notna(m_change):
                footnote += f"\nMoisture: {m_current:.1f}% (week avg: {m_avg:.1f}%, {m_change:+.1f}% change)"
            else:
                footnote += f"\nMoisture: {m_current:.1f}%"
        
        t_current = sensor_summary['temperature'].get('current', np.nan)
        t_avg = sensor_summary['temperature'].get('avg_week', np.nan)
        t_min = sensor_summary['temperature'].get('min_week', np.nan)
        t_max = sensor_summary['temperature'].get('max_week', np.nan)
        
        if pd.notna(t_current):
            if pd.notna(t_avg) and pd.notna(t_min) and pd.notna(t_max):
                footnote += f"\nTemp: {t_current:.1f}C (week avg: {t_avg:.1f}C, range: {t_min:.1f}-{t_max:.1f}C)"
            else:
                footnote += f"\nTemp: {t_current:.1f}C"
        
        l_current = sensor_summary['light'].get('current', np.nan)
        l_avg = sensor_summary['light'].get('avg_week', np.nan)
        
        if pd.notna(l_current):
            if pd.notna(l_avg):
                footnote += f"\nLight: {l_current:.1f} lux (week avg: {l_avg:.1f} lux)"
            else:
                footnote += f"\nLight: {l_current:.1f} lux"
        
        # Multi-week patterns - NO blank line after "Patterns:"
        multi_week_patterns = sensor_summary.get('multi_week_patterns', [])
        if multi_week_patterns:
            footnote += "\n\nPatterns:"
            for pattern in multi_week_patterns:
                footnote += f"\n- {pattern}"
        
        # Influence - blank line before
        footnote += f"\n\nInfluence: {influence_name}"
        
        return footnote


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Example CLI for testing"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python poetry_engine.py <path_to_csv>")
        print("\nExample: python poetry_engine.py plant_soil_log.csv")
        return
    
    csv_path = sys.argv[1]
    
    print("===================================================")
    print("  BIOPOEM - Daily Poetry Generation System")
    print("===================================================\n")
    
    try:
        # Initialize generator
        generator = DailyPoetryGenerator(csv_path)
        
        # Generate today's poem prompt
        result = generator.generate_daily_poem_prompt()
        
        print(" THEME ANALYSIS")
        print("-----------------")
        for theme, score in result["theme_analysis"]["ranked"][:3]:
            theme_name = ThemeScorer.THEMES[theme]["name"]
            print(f"  {theme_name}: {score:.2f}")
        
        print(f"\n SELECTED INFLUENCE")
        print("---------------------")
        print(f"  {result['metadata']['influence_name']}")
        
        print(f"\n SENSOR SUMMARY")
        print("-----------------")
        for sensor, value in result['metadata']['sensor_readings'].items():
            print(f"  {sensor.capitalize()}: {value}")
        
        print(f"\n" + "="*60)
        print("GENERATED PROMPT FOR LLM:")
        print("="*60)
        print(result["prompt"])
        
        print("\n" + "="*60)
        print("POEM FOOTNOTE:")
        print("="*60)
        print(result["footnote"])
        
        # Save prompt to file for testing
        output_file = f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result["prompt"])
            f.write("\n\n")
            f.write(result["footnote"])
        
        print(f"\n Prompt saved to: {output_file}")
        
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

