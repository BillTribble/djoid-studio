# DJOID Studio — AI DJ Set & Rekordbox XML Studio

A standalone, zero-dependency AI DJ set planner, harmonic graph explorer, multi-band waveform cue inspector, and Pioneer DJ / AlphaTheta `rekordbox.xml` (`<DJ_PLAYLISTS Version="1.0.0">`) exporter.

## Features

1. **24-Track Club/Electronic Library + Local Audio DSP & `rekordbox.xml` Importer**
   - Ships with 24 pre-analyzed electronic/club tracks spanning Camelot `1A`–`12B`, `118–134 BPM`, Energy `2–10`, 3-band (`low`/`mid`/`high`) waveform envelopes, beatgrids, and structural Hot Cues `A=Intro`, `B=Buildup`, `C=Drop`, `D=Outro`.
   - Drop or select local `.mp3`/`.wav`/`.flac` files for in-browser WebAudio DSP extraction (BPM, Camelot key, LUFS loudness, and cue segmentation) or import an existing `rekordbox.xml`.
2. **Energy-Curve Set Arc Drawer & Beam-Search Solver**
   - Sketch custom 8-slot energy arcs or choose presets (*Warm-up to peak*, *Sunrise terrace journey*, *Double-peak club set*, *Afterhours hypnotic*).
   - Tune 3 **30×30px 270° SVG Rotary Encoders** (*Harmonic lock*, *BPM tolerance*, *Energy weight*) and solve for the optimal track sequence with actionable per-transition AI mix coaching notes.
3. **Interactive 2D Vibe Map & $A^*$ Bridge Pathfinder**
   - Visualize harmonic compatibility edges across the library and run $A^*$ search between any two tracks to find the highest-scoring 1–2 intermediate bridge tracks.
4. **Dual-Deck Multi-Band Waveform & WebAudio Synth Transition Previewer**
   - Inspect 3-band waveforms and Hot Cues `A`–`D` on Deck A (outgoing) and Deck B (incoming), and audition live synthesized 16-beat crossfades with automatic bass EQ swapping.
5. **1-Click Rekordbox XML (`<DJ_PLAYLISTS Version="1.0.0">`) & `.m3u8` Exporter**
   - Generates spec-compliant Pioneer DJ / AlphaTheta `rekordbox.xml` files with `<COLLECTION>`, `<TRACK>`, `<TEMPO>` beatgrid anchors, color-coded `<POSITION_MARK>` Hot Cues (`Num="0".."3"`) & Memory Cues (`Num="-1"`), and ordered `<PLAYLISTS>`.

## How Rekordbox XML Export Works & How to Load It in Rekordbox

1. Click **Export XML** in DJOID Studio to download `rekordbox.xml`.
2. Open Pioneer DJ **Rekordbox** (v6 or v7) and navigate to **Preferences → Advanced → Database → rekordbox xml**.
3. Click **Browse** under *Imported Library* and select the downloaded `rekordbox.xml` file.
4. In the left vertical sidebar of Rekordbox, click the **rekordbox xml** icon (if hidden, enable **View → Layout → rekordbox xml**).
5. Expand **Playlists → DJOID Studio AI Set**, right-click the playlist, and select **Import To Collection**. All tracks, beatgrids (`<TEMPO>`), Hot Cues `A`–`D` (`Num="0".."3"`), and Memory Cues (`Num="-1"`) will load directly onto your decks and CDJ/XDJ performance pads.

## Quick Start

```bash
python3 server.py --port 18919
```
