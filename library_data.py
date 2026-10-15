"""Pre-loaded 24-track electronic/club library and set arc presets for DJOID Studio."""

import math

CAMELOT_TO_MUSICAL = {
    "1A": "Abm", "1B": "B",
    "2A": "Ebm", "2B": "F#",
    "3A": "Bbm", "3B": "Db",
    "4A": "Fm",  "4B": "Ab",
    "5A": "Cm",  "5B": "Eb",
    "6A": "Gm",  "6B": "Bb",
    "7A": "Dm",  "7B": "F",
    "8A": "Am",  "8B": "C",
    "9A": "Em",  "9B": "G",
    "10A": "Bm", "10B": "D",
    "11A": "F#m", "11B": "A",
    "12A": "C#m", "12B": "E",
}

MUSICAL_TO_CAMELOT = {v.lower(): k for k, v in CAMELOT_TO_MUSICAL.items()}
MUSICAL_TO_CAMELOT.update({k.lower(): k for k in CAMELOT_TO_MUSICAL})

ENERGY_PRESETS = {
    "warmup_to_peak": {
        "id": "warmup_to_peak",
        "name": "Warm-up to peak",
        "description": "Gradual opening build into peak-hour club intensity",
        "curve": [3, 4, 5, 6, 7, 8, 9, 9],
    },
    "sunrise_journey": {
        "id": "sunrise_journey",
        "name": "Sunrise terrace journey",
        "description": "Hypnotic mid-set crest tapering into melodic sunrise closure",
        "curve": [6, 7, 8, 7, 6, 7, 5, 3],
    },
    "double_peak": {
        "id": "double_peak",
        "name": "Double-peak club set",
        "description": "Two high-impact techno peaks separated by a tension breakdown",
        "curve": [4, 6, 9, 6, 5, 8, 10, 7],
    },
    "afterhours_hypnotic": {
        "id": "afterhours_hypnotic",
        "name": "Afterhours hypnotic",
        "description": "Locked-groove deep and hypnotic techno roller arc",
        "curve": [5, 6, 6, 7, 7, 8, 7, 6],
    },
}


def build_waveform_bands(seed: int, energy: int, duration: int, cue_ratios: tuple):
    """Generates deterministic 64-bin 3-band (low/mid/high) waveform envelopes."""
    bins = 64
    r_intro, r_build, r_drop, r_outro = cue_ratios
    low, mid, high = [], [], []
    base_amp = 0.32 + (energy / 10.0) * 0.58
    for i in range(bins):
        pos = i / float(bins - 1)
        if pos < r_intro:
            env = 0.38 + 0.25 * (pos / max(0.01, r_intro))
        elif pos < r_build:
            env = 0.55 + 0.20 * math.sin((pos - r_intro) * 18.0)
        elif pos < r_outro:
            # Main drop section with a brief mid-track breakdown around 58%
            if 0.52 <= pos <= 0.63:
                env = 0.44 + 0.12 * math.cos(pos * 25.0)
            else:
                env = 0.88 + 0.12 * math.sin(i * 1.7 + seed)
        else:
            tail = (pos - r_outro) / max(0.01, 1.0 - r_outro)
            env = max(0.22, 0.72 * (1.0 - 0.65 * tail))

        ripple_l = 0.08 * math.sin(i * 1.31 + seed * 0.7)
        ripple_m = 0.10 * math.cos(i * 2.17 + seed * 1.1)
        ripple_h = 0.11 * math.sin(i * 3.43 + seed * 1.9)

        # Breakdown strips sub-bass so DJs see where to blend
        bass_gate = 0.35 if (0.53 <= pos <= 0.62) else 1.0
        l_val = round(min(1.0, max(0.08, env * base_amp * bass_gate + ripple_l)), 3)
        m_val = round(min(1.0, max(0.10, env * (0.45 + 0.45 * base_amp) + ripple_m)), 3)
        h_val = round(min(1.0, max(0.06, env * (0.35 + 0.50 * base_amp) + ripple_h)), 3)
        low.append(l_val)
        mid.append(m_val)
        high.append(h_val)
    return {"low": low, "mid": mid, "high": high}


def make_cues(duration: int, bpm: float, ratios=(0.08, 0.24, 0.34, 0.82)):
    """Creates quantised 16-bar structural Hot Cues A-D and Memory Cues."""
    bar_sec = (60.0 / bpm) * 4.0
    r_a, r_b, r_c, r_d = ratios

    def snap_bar(sec):
        bars = max(1, round(sec / bar_sec))
        return round(bars * bar_sec, 2), int(bars)

    sec_a, bar_a = snap_bar(duration * r_a)
    sec_b, bar_b = snap_bar(duration * r_b)
    sec_c, bar_c = snap_bar(duration * r_c)
    sec_d, bar_d = snap_bar(duration * r_d)

    return [
        {
            "slot": "A",
            "num": 0,
            "name": f"A: Intro ({bar_a}b)",
            "section": "Intro",
            "start": sec_a,
            "bar": bar_a,
            "color": {"r": 40, "g": 226, "b": 20},
            "tone": "green",
        },
        {
            "slot": "B",
            "num": 1,
            "name": f"B: Buildup ({bar_b}b)",
            "section": "Buildup",
            "start": sec_b,
            "bar": bar_b,
            "color": {"r": 245, "g": 158, "b": 11},
            "tone": "yellow",
        },
        {
            "slot": "C",
            "num": 2,
            "name": f"C: Drop ({bar_c}b)",
            "section": "Drop",
            "start": sec_c,
            "bar": bar_c,
            "color": {"r": 239, "g": 68, "b": 68},
            "tone": "red",
        },
        {
            "slot": "D",
            "num": 3,
            "name": f"D: Mix Out ({bar_d}b)",
            "section": "Outro",
            "start": sec_d,
            "bar": bar_d,
            "color": {"r": 59, "g": 130, "b": 246},
            "tone": "blue",
        },
    ]


RAW_TRACKS = [
    ("trk-01", "Subaquatic Horizon", "Kiasmos & Rival Consoles", "Ambient / Deep Intro", 118.0, "1A", 2, 342, 0.18, 0.24, -13.4),
    ("trk-02", "Velvet Mist (Sunrise Dub)", "Pachanga Boys", "Organic House", 119.5, "1B", 3, 388, 0.24, 0.31, -12.1),
    ("trk-03", "Nocturne in Glass", "Christian Löffler", "Deep House", 120.0, "2A", 4, 356, 0.30, 0.28, -11.5),
    ("trk-04", "Solstice Drift", "Sébastien Léger", "Organic House", 121.0, "2B", 4, 394, 0.35, 0.42, -10.8),
    ("trk-05", "Mirage Protocol", "Ben Böhmer", "Melodic House", 122.0, "3A", 5, 368, 0.42, 0.48, -10.2),
    ("trk-06", "Amber Resonance", "Marsh", "Melodic House", 122.5, "3B", 5, 350, 0.47, 0.56, -9.8),
    ("trk-07", "Parallel Warehouse", "Overmono", "Breakbeat", 123.5, "4A", 6, 332, 0.53, 0.38, -9.4),
    ("trk-08", "Parallax Echoes", "Yotto", "Progressive House", 124.0, "4B", 6, 376, 0.56, 0.52, -9.1),
    ("trk-09", "Obsidian Pulse", "Stephan Bodzin", "Melodic Techno", 125.0, "5A", 7, 404, 0.62, 0.44, -8.5),
    ("trk-10", "Electric Arcade", "Maceo Plex", "Indie Dance", 125.5, "5B", 7, 364, 0.66, 0.64, -8.3),
    ("trk-11", "Shadow Telemetry", "Mind Against", "Melodic Techno", 126.0, "6A", 7, 382, 0.68, 0.35, -8.1),
    ("trk-12", "Solaris Vector", "CamelPhat", "Progressive House", 126.0, "6B", 8, 372, 0.72, 0.68, -7.8),
    ("trk-13", "Cobalt Substructure", "Tale Of Us", "Melodic Techno", 127.0, "7A", 8, 390, 0.75, 0.40, -7.6),
    ("trk-14", "Hyperion Gate", "ARTBAT", "Melodic Techno", 127.5, "7B", 8, 360, 0.79, 0.72, -7.4),
    ("trk-15", "Kinetic Monolith", "Bicep", "Breakbeat", 128.0, "8A", 8, 346, 0.74, 0.58, -7.5),
    ("trk-16", "Aether Circuit", "Four Tet", "Melodic House", 128.0, "8B", 7, 354, 0.64, 0.78, -8.2),
    ("trk-17", "ferrofluid 09", "Rødhåd", "Hypnotic Techno", 129.0, "9A", 8, 412, 0.81, 0.22, -7.2),
    ("trk-18", "Chrominance", "Avalon Emerson", "Indie Dance", 129.5, "9B", 8, 348, 0.77, 0.82, -7.6),
    ("trk-19", "Turbine Hall", "Enrico Sangiuliano", "Peak-Time Techno", 130.5, "10A", 9, 398, 0.86, 0.30, -6.7),
    ("trk-20", "Laser Grid 303", "Charlotte de Witte", "Acid Techno", 131.5, "10B", 9, 366, 0.90, 0.46, -6.4),
    ("trk-21", "Event Horizon (berghain mix)", "Ben Klock", "Peak-Time Techno", 132.5, "11A", 10, 418, 0.94, 0.19, -6.1),
    ("trk-22", "Supernova Strobe", "Amelie Lens", "Peak-Time Techno", 133.5, "11B", 10, 374, 0.96, 0.54, -5.9),
    ("trk-23", "Acid Rain Protocol", "999999999", "Acid Techno", 134.0, "12A", 10, 358, 0.92, 0.26, -5.8),
    ("trk-24", "Dawn Afterglow (Closing Mix)", "Jon Hopkins", "Closing Break", 121.5, "12B", 4, 424, 0.36, 0.86, -10.9),
]


def build_initial_library():
    """Returns the 24-track club library with beatgrids, cues, and 3-band waveforms."""
    tracks = []
    for idx, row in enumerate(RAW_TRACKS, start=1):
        tid, title, artist, genre, bpm, camelot, energy, duration, vx, vy, lufs = row
        ratios = (0.07, 0.23, 0.33, 0.81) if energy >= 7 else (0.09, 0.26, 0.38, 0.83)
        cues = make_cues(duration, bpm, ratios)
        waveform = build_waveform_bands(idx, energy, duration, ratios)
        slug = title.lower().replace(" ", "_").replace("(", "").replace(")", "")
        tracks.append({
            "id": tid,
            "track_number": idx,
            "title": title,
            "artist": artist,
            "genre": genre,
            "bpm": bpm,
            "camelot": camelot,
            "musical_key": CAMELOT_TO_MUSICAL.get(camelot, "Am"),
            "energy": energy,
            "duration": duration,
            "vibe_x": vx,  # Dancefloor drive / tempo intensity
            "vibe_y": vy,  # Euphoria / harmonic brightness
            "lufs": lufs,
            "first_beat_sec": 0.125,
            "location": f"file://localhost/Users/dj/Music/DJOID/{idx:02d}_{slug}.wav",
            "cues": cues,
            "waveform": waveform,
            "source": "library",
        })
    return tracks
