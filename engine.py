"""Harmonic graph, Beam-Search Set Solver, A* Bridge Finder, DSP analyzer, and Rekordbox XML engine."""

import heapq
import math
import urllib.parse
import xml.etree.ElementTree as ET
from xml.dom import minidom

from library_data import (
    CAMELOT_TO_MUSICAL,
    MUSICAL_TO_CAMELOT,
    build_waveform_bands,
    make_cues,
)


def parse_camelot(code: str):
    """Parses a Camelot key like '8A' or '11B' into (number 1..12, letter 'A'|'B')."""
    if not code:
        return (8, "A")
    clean = str(code).strip().upper()
    if clean.lower() in MUSICAL_TO_CAMELOT:
        clean = MUSICAL_TO_CAMELOT[clean.lower()]
    letter = clean[-1] if clean[-1] in ("A", "B") else "A"
    num_part = clean[:-1] if clean[:-1].isdigit() else "8"
    num = max(1, min(12, int(num_part)))
    return (num, letter)


def wheel_distance(n1: int, n2: int) -> int:
    """Shortest distance around the 12-hour Camelot circle (0..6)."""
    diff = abs(n1 - n2) % 12
    return min(diff, 12 - diff)


def harmonic_compatibility(cam_a: str, cam_b: str):
    """Returns (score 0..1, relation_type, badge_tone, short_label)."""
    n1, l1 = parse_camelot(cam_a)
    n2, l2 = parse_camelot(cam_b)
    dist = wheel_distance(n1, n2)
    step = (n2 - n1) % 12

    if n1 == n2 and l1 == l2:
        return (1.00, "same_key", "green", "Unison key (0)")
    if dist == 1 and l1 == l2:
        direction = "+1 fifth" if step == 1 else "-1 fifth"
        return (0.95, "adjacent_fifth", "green", f"Harmonic {direction}")
    if n1 == n2 and l1 != l2:
        return (0.92, "relative_mode", "teal", f"Relative {l1}→{l2}")
    if step in (2, 7) and l1 == l2:
        return (0.82, "energy_boost", "blue", f"Energy boost (+{step})")
    if dist == 1 and l1 != l2:
        return (0.78, "diagonal_mod", "purple", "Diagonal modulation")
    if dist == 2 and l1 == l2:
        return (0.72, "whole_step", "yellow", "Whole-tone step (-2)")
    return (max(0.22, 0.65 - 0.08 * dist), "key_clash", "orange", "Percussive / EQ swap")


def format_mmss(seconds: float) -> str:
    sec = max(0, int(round(seconds)))
    return f"{sec // 60}:{sec % 60:02d}"


def generate_coaching_note(track_a: dict, track_b: dict, harm_info: tuple, bpm_diff: float) -> str:
    """Produces a concrete DJ transition coaching note referencing exact Hot Cues & bars."""
    _, rel_type, _, _ = harm_info
    cues_a = {c["slot"]: c for c in track_a.get("cues", [])}
    cues_b = {c["slot"]: c for c in track_b.get("cues", [])}
    out_a = cues_a.get("D", {"start": track_a["duration"] * 0.82, "bar": 96})
    in_b = cues_b.get("A", {"start": 15.0, "bar": 8})
    build_b = cues_b.get("B", {"start": 45.0, "bar": 24})

    pitch_pct = ((track_a["bpm"] - track_b["bpm"]) / max(1.0, track_b["bpm"])) * 100.0
    if abs(pitch_pct) < 0.08:
        pitch_str = "tempo-locked (0.0% pitch)"
    else:
        sign = "+" if pitch_pct > 0 else ""
        pitch_str = f"{sign}{pitch_pct:.1f}% pitch on Deck B"

    if rel_type in ("same_key", "adjacent_fifth", "relative_mode"):
        return (
            f"Trigger Deck B at Hot Cue A ({format_mmss(in_b['start'])}, {pitch_str}) over "
            f"Deck A Hot Cue D ({format_mmss(out_a['start'])}). Blend melodic mids across 16 bars "
            f"and swap sub-bass EQ at Deck B Cue B ({format_mmss(build_b['start'])})."
        )
    if rel_type in ("energy_boost", "diagonal_mod"):
        return (
            f"Energy lift ({track_a['camelot']}→{track_b['camelot']}, {pitch_str}): loop 8 bars at "
            f"Deck B Cue A ({format_mmss(in_b['start'])}), high-pass Deck A bass at Cue D "
            f"({format_mmss(out_a['start'])}), and drop full low-end on Deck B Cue B ({format_mmss(build_b['start'])})."
        )
    return (
        f"Percussive transition ({track_a['camelot']}→{track_b['camelot']}, {pitch_str}): isolate "
        f"drum stem at Deck A Cue D ({format_mmss(out_a['start'])}), apply 1/4 echo tail on mids, "
        f"and hard-swap bass into Deck B Cue B ({format_mmss(build_b['start'])})."
    )


def score_transition(
    track_a: dict,
    track_b: dict,
    target_energy_b=None,
    harmonic_strictness: float = 80.0,
    bpm_tolerance: float = 4.0,
    energy_adherence: float = 85.0,
):
    """Computes weighted compatibility between track_a and track_b."""
    harm_score, rel_type, badge_tone, harm_label = harmonic_compatibility(
        track_a["camelot"], track_b["camelot"]
    )
    bpm_diff = abs(float(track_a["bpm"]) - float(track_b["bpm"]))
    tol = max(0.5, float(bpm_tolerance))
    bpm_score = math.exp(-((bpm_diff / tol) ** 1.6) * 0.65)
    bpm_score = max(0.10, min(1.0, bpm_score))

    if target_energy_b is not None:
        e_diff = abs(float(track_b["energy"]) - float(target_energy_b))
        energy_score = max(0.10, 1.0 - (e_diff / 7.5))
    else:
        e_step = abs(float(track_b["energy"]) - float(track_a["energy"]))
        energy_score = max(0.20, 1.0 - max(0.0, e_step - 1.5) / 6.0)

    # 2D Vibe space proximity bonus
    vibe_dist = math.hypot(
        float(track_a.get("vibe_x", 0.5)) - float(track_b.get("vibe_x", 0.5)),
        float(track_a.get("vibe_y", 0.5)) - float(track_b.get("vibe_y", 0.5)),
    )
    vibe_score = max(0.25, 1.0 - 0.55 * vibe_dist)

    w_h = max(0.05, harmonic_strictness / 100.0)
    w_b = max(0.15, (13.0 - min(12.0, tol)) / 10.0)
    w_e = max(0.05, energy_adherence / 100.0)
    w_v = 0.25
    total_w = w_h + w_b + w_e + w_v

    combined = (w_h * harm_score + w_b * bpm_score + w_e * energy_score + w_v * vibe_score) / total_w
    coaching = generate_coaching_note(
        track_a, track_b, (harm_score, rel_type, badge_tone, harm_label), bpm_diff
    )

    return {
        "overall": round(combined * 100.0, 1),
        "harmonic_score": round(harm_score * 100.0, 1),
        "bpm_score": round(bpm_score * 100.0, 1),
        "energy_score": round(energy_score * 100.0, 1),
        "bpm_delta": round(float(track_b["bpm"]) - float(track_a["bpm"]), 1),
        "relation_type": rel_type,
        "badge_tone": badge_tone,
        "harmonic_label": harm_label,
        "coaching": coaching,
    }


def build_harmonic_graph(tracks: list):
    """Builds harmonic + tempo compatibility edges for the 2D Vibe Map."""
    edges = []
    n = len(tracks)
    for i in range(n):
        for j in range(i + 1, n):
            ta, tb = tracks[i], tracks[j]
            h_score, rel_type, tone, label = harmonic_compatibility(ta["camelot"], tb["camelot"])
            bpm_diff = abs(float(ta["bpm"]) - float(tb["bpm"]))
            if h_score >= 0.88 and bpm_diff <= 4.5:
                weight = round(0.6 * h_score + 0.4 * max(0.0, 1.0 - bpm_diff / 6.0), 3)
                edges.append({
                    "source": ta["id"],
                    "target": tb["id"],
                    "relation": rel_type,
                    "label": label,
                    "tone": tone,
                    "bpm_diff": round(bpm_diff, 1),
                    "weight": weight,
                })
    return edges


def find_bridge_path(tracks: list, source_id: str, target_id: str, bpm_tolerance: float = 4.0):
    """Runs A* search over the track library to find the smoothest harmonic/BPM bridge path."""
    by_id = {t["id"]: t for t in tracks}
    if source_id not in by_id or target_id not in by_id:
        return {"path": [], "transitions": [], "summary": "Select valid start and target tracks."}
    if source_id == target_id:
        t = by_id[source_id]
        return {"path": [t], "transitions": [], "summary": "Start and target are the same track."}

    target = by_id[target_id]

    def heuristic(tid: str) -> float:
        cur = by_id[tid]
        h_score, _, _, _ = harmonic_compatibility(cur["camelot"], target["camelot"])
        bpm_gap = abs(float(cur["bpm"]) - float(target["bpm"]))
        return (1.0 - h_score) * 0.6 + (bpm_gap / 30.0) * 0.4

    # Find best 2-to-4 track path (including at least 1 intermediate bridge track if direct isn't optimal)
    direct_eval = score_transition(by_id[source_id], target, bpm_tolerance=bpm_tolerance)
    force_bridge = direct_eval["overall"] < 88.0

    pq = [(heuristic(source_id), 0.0, [source_id])]
    best_cost = {}

    best_path = None
    while pq:
        _, g_cost, path = heapq.heappop(pq)
        curr_id = path[-1]
        hops = len(path) - 1

        if curr_id == target_id and (hops >= 2 or not force_bridge):
            best_path = path
            break

        if hops >= 3:
            continue

        state_key = (curr_id, hops)
        if state_key in best_cost and best_cost[state_key] <= g_cost:
            continue
        best_cost[state_key] = g_cost

        curr_trk = by_id[curr_id]
        for cand in tracks:
            cid = cand["id"]
            if cid in path:
                continue
            if cid == target_id and force_bridge and hops == 0:
                continue
            trans = score_transition(
                curr_trk,
                cand,
                harmonic_strictness=90.0,
                bpm_tolerance=bpm_tolerance,
                energy_adherence=75.0,
            )
            step_cost = max(0.02, 1.05 - (trans["overall"] / 100.0))
            next_g = g_cost + step_cost
            heapq.heappush(pq, (next_g + heuristic(cid) * 0.35, next_g, path + [cid]))

    if not best_path:
        best_path = [source_id, target_id]

    path_tracks = [by_id[tid] for tid in best_path]
    transitions = []
    for i in range(len(path_tracks) - 1):
        tr = score_transition(
            path_tracks[i],
            path_tracks[i + 1],
            harmonic_strictness=90.0,
            bpm_tolerance=bpm_tolerance,
            energy_adherence=75.0,
        )
        transitions.append({
            "from_id": path_tracks[i]["id"],
            "to_id": path_tracks[i + 1]["id"],
            **tr,
        })

    avg_score = (
        round(sum(t["overall"] for t in transitions) / len(transitions), 1)
        if transitions
        else 100.0
    )
    bridge_names = [t["title"] for t in path_tracks[1:-1]]
    if bridge_names:
        summary = (
            f"A* bridge via {', '.join(bridge_names)} raises harmonic/BPM compatibility "
            f"from {direct_eval['overall']}% (direct) to {avg_score}% average across {len(transitions)} transitions."
        )
    else:
        summary = f"Direct harmonic lock ({avg_score}% compatibility) between {path_tracks[0]['title']} and {path_tracks[-1]['title']}."

    return {
        "path": path_tracks,
        "transitions": transitions,
        "direct_score": direct_eval["overall"],
        "bridge_avg_score": avg_score,
        "summary": summary,
    }


def solve_set(
    tracks: list,
    target_curve: list,
    harmonic_strictness: float = 80.0,
    bpm_tolerance: float = 4.0,
    energy_adherence: float = 85.0,
    seed_track_id: str = None,
    beam_width: int = 24,
):
    """Beam-search solver that optimizes track sequence over the user's target energy curve."""
    if not tracks or not target_curve:
        return {"slots": [], "metrics": {}}

    n_slots = min(len(target_curve), len(tracks))
    curve = [float(x) for x in target_curve[:n_slots]]
    w_energy = max(0.1, float(energy_adherence) / 100.0)

    def slot_energy_fit(trk: dict, target_e: float) -> float:
        diff = abs(float(trk["energy"]) - target_e)
        return max(0.05, 1.0 - (diff / 8.0))

    # Slot 0 initialization
    beam = []
    for trk in tracks:
        if seed_track_id and trk["id"] != seed_track_id:
            continue
        fit0 = slot_energy_fit(trk, curve[0])
        beam.append((fit0 * (0.6 + 0.4 * w_energy), [trk], []))

    if not beam:
        for trk in tracks:
            fit0 = slot_energy_fit(trk, curve[0])
            beam.append((fit0, [trk], []))

    beam.sort(key=lambda x: x[0], reverse=True)
    beam = beam[:beam_width]

    for slot_idx in range(1, n_slots):
        target_e = curve[slot_idx]
        next_candidates = []
        for cum_score, seq, trans_list in beam:
            prev_trk = seq[-1]
            used_ids = {t["id"] for t in seq}
            for cand in tracks:
                if cand["id"] in used_ids:
                    continue
                tr = score_transition(
                    prev_trk,
                    cand,
                    target_energy_b=target_e,
                    harmonic_strictness=harmonic_strictness,
                    bpm_tolerance=bpm_tolerance,
                    energy_adherence=energy_adherence,
                )
                e_fit = slot_energy_fit(cand, target_e)
                step_score = (tr["overall"] / 100.0) * (1.0 - 0.35 * w_energy) + e_fit * (0.35 * w_energy)
                next_candidates.append((
                    cum_score + step_score,
                    seq + [cand],
                    trans_list + [tr],
                ))
        next_candidates.sort(key=lambda x: x[0], reverse=True)
        beam = next_candidates[:beam_width]

    _, best_seq, best_trans = beam[0]
    slots = []
    total_duration = 0
    for idx, trk in enumerate(best_seq):
        total_duration += int(trk.get("duration", 360))
        slots.append({
            "slot": idx + 1,
            "target_energy": curve[idx],
            "actual_energy": trk["energy"],
            "track": trk,
            "transition_from_prev": best_trans[idx - 1] if idx > 0 else None,
        })

    avg_overall = (
        round(sum(t["overall"] for t in best_trans) / len(best_trans), 1)
        if best_trans
        else 100.0
    )
    avg_harmonic = (
        round(sum(t["harmonic_score"] for t in best_trans) / len(best_trans), 1)
        if best_trans
        else 100.0
    )
    max_bpm_jump = (
        round(max(abs(t["bpm_delta"]) for t in best_trans), 1)
        if best_trans
        else 0.0
    )
    energy_mae = round(
        sum(abs(s["actual_energy"] - s["target_energy"]) for s in slots) / max(1, len(slots)),
        2,
    )

    return {
        "slots": slots,
        "metrics": {
            "set_score": avg_overall,
            "harmonic_flow": avg_harmonic,
            "max_bpm_jump": max_bpm_jump,
            "energy_mae": energy_mae,
            "track_count": len(slots),
            "total_duration_sec": total_duration,
            "total_duration_formatted": f"{total_duration // 60}m {total_duration % 60:02d}s",
        },
    }


def export_rekordbox_xml(set_tracks: list, playlist_name: str = "DJOID Studio AI Set") -> str:
    """Generates a spec-compliant Rekordbox XML (<DJ_PLAYLISTS Version='1.0.0'>) document."""
    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    ET.SubElement(
        root,
        "PRODUCT",
        {"Name": "rekordbox", "Version": "6.8.5", "Company": "AlphaTheta"},
    )
    collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(set_tracks))})

    track_keys = []
    for idx, trk in enumerate(set_tracks, start=1):
        tid_num = str(idx)
        track_keys.append(tid_num)
        location = trk.get("location") or f"file://localhost/Users/dj/Music/DJOID/{idx:02d}.wav"
        if not location.startswith("file://localhost/"):
            raw_path = location.replace("file://", "").lstrip("/")
            location = "file://localhost/" + urllib.parse.quote(raw_path, safe="/:._-")

        track_el = ET.SubElement(
            collection,
            "TRACK",
            {
                "TrackID": tid_num,
                "Name": str(trk.get("title", f"Track {idx}")),
                "Artist": str(trk.get("artist", "Unknown Artist")),
                "Album": "DJOID Studio Curated Set",
                "Genre": str(trk.get("genre", "Electronic")),
                "TotalTime": str(int(round(float(trk.get("duration", 360))))),
                "AverageBpm": f"{float(trk.get('bpm', 124.0)):.2f}",
                "Tonality": str(trk.get("camelot", "8A")),
                "Comments": (
                    f"Energy {trk.get('energy', 6)}/10 • Key {trk.get('camelot', '8A')} "
                    f"({trk.get('musical_key', 'Am')}) • Loudness {trk.get('lufs', -8.5)} LUFS"
                ),
                "Location": location,
            },
        )
        # Beatgrid anchor (<TEMPO>)
        ET.SubElement(
            track_el,
            "TEMPO",
            {
                "Inizio": f"{float(trk.get('first_beat_sec', 0.125)):.3f}",
                "Bpm": f"{float(trk.get('bpm', 124.0)):.2f}",
                "Metro": "4/4",
                "Battito": "1",
            },
        )
        # Hot Cues A-D (Num="0".."3") + Memory Cues (Num="-1")
        for cue in trk.get("cues", []):
            rgb = cue.get("color", {"r": 40, "g": 226, "b": 20})
            ET.SubElement(
                track_el,
                "POSITION_MARK",
                {
                    "Name": str(cue.get("name", "Cue")),
                    "Type": "0",
                    "Start": f"{float(cue.get('start', 0.0)):.3f}",
                    "Num": str(cue.get("num", 0)),
                    "Red": str(rgb.get("r", 40)),
                    "Green": str(rgb.get("g", 226)),
                    "Blue": str(rgb.get("b", 20)),
                },
            )
            # Also add Rekordbox Memory Cue (Num="-1") on Intro (A) and Mix Out (D)
            if cue.get("slot") in ("A", "D"):
                ET.SubElement(
                    track_el,
                    "POSITION_MARK",
                    {
                        "Name": f"Memory: {cue.get('section', 'Marker')}",
                        "Type": "0",
                        "Start": f"{float(cue.get('start', 0.0)):.3f}",
                        "Num": "-1",
                    },
                )

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(
        playlists, "NODE", {"Type": "0", "Name": "ROOT", "Count": "1"}
    )
    pl_node = ET.SubElement(
        root_node,
        "NODE",
        {
            "Name": playlist_name,
            "Type": "1",
            "KeyType": "0",
            "Entries": str(len(track_keys)),
        },
    )
    for k in track_keys:
        ET.SubElement(pl_node, "TRACK", {"Key": k})

    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


def export_m3u8(set_tracks: list, playlist_name: str = "DJOID Studio AI Set") -> str:
    """Generates an extended .m3u8 playlist with BPM, Camelot key, and energy metadata."""
    lines = ["#EXTM3U", f"#PLAYLIST:{playlist_name}"]
    for idx, trk in enumerate(set_tracks, start=1):
        dur = int(round(float(trk.get("duration", 360))))
        artist = trk.get("artist", "Unknown")
        title = trk.get("title", f"Track {idx}")
        cam = trk.get("camelot", "8A")
        bpm = float(trk.get("bpm", 124.0))
        energy = trk.get("energy", 6)
        loc = trk.get("location", f"file://localhost/Users/dj/Music/DJOID/{idx:02d}.wav")
        path = urllib.parse.unquote(loc.replace("file://localhost", ""))
        lines.append(f"#EXTINF:{dur},{artist} - {title} [{cam} • {bpm:.1f} BPM • E{energy}]")
        lines.append(path)
    return "\n".join(lines) + "\n"


def parse_rekordbox_xml(xml_text: str, existing_count: int = 24) -> list:
    """Parses a Rekordbox XML file (<DJ_PLAYLISTS>) and extracts tracks, beatgrids, and cues."""
    root = ET.fromstring(xml_text.strip())
    imported = []
    for idx, trk_el in enumerate(root.findall(".//COLLECTION/TRACK"), start=existing_count + 1):
        name = trk_el.attrib.get("Name") or f"Imported Track {idx}"
        artist = trk_el.attrib.get("Artist") or "Imported Artist"
        genre = trk_el.attrib.get("Genre") or "Electronic / Club"
        bpm = float(trk_el.attrib.get("AverageBpm") or 126.0)
        duration = int(float(trk_el.attrib.get("TotalTime") or 360))
        tonality = (trk_el.attrib.get("Tonality") or "8A").strip()
        cam_num, cam_let = parse_camelot(tonality)
        camelot = f"{cam_num}{cam_let}"

        tempo_el = trk_el.find("TEMPO")
        first_beat = float(tempo_el.attrib.get("Inizio", 0.125)) if tempo_el is not None else 0.125

        # Parse POSITION_MARK Hot Cues if present
        pos_marks = trk_el.findall("POSITION_MARK")
        parsed_cues = []
        slot_names = ["A", "B", "C", "D"]
        slot_tones = ["green", "yellow", "red", "blue"]
        slot_sections = ["Intro", "Buildup", "Drop", "Outro"]
        bar_sec = (60.0 / max(60.0, bpm)) * 4.0

        for pm in pos_marks:
            num = int(pm.attrib.get("Num", "-1"))
            if 0 <= num <= 3:
                start_sec = float(pm.attrib.get("Start", 0.0))
                bar_num = max(1, int(round(start_sec / bar_sec)))
                parsed_cues.append({
                    "slot": slot_names[num],
                    "num": num,
                    "name": pm.attrib.get("Name") or f"{slot_names[num]}: {slot_sections[num]} ({bar_num}b)",
                    "section": slot_sections[num],
                    "start": round(start_sec, 2),
                    "bar": bar_num,
                    "color": {
                        "r": int(pm.attrib.get("Red", 40)),
                        "g": int(pm.attrib.get("Green", 226)),
                        "b": int(pm.attrib.get("Blue", 20)),
                    },
                    "tone": slot_tones[num],
                })

        if len(parsed_cues) < 4:
            parsed_cues = make_cues(duration, bpm)

        energy = max(2, min(10, int(round((bpm - 115.0) / 2.1))))
        vx = round(min(0.96, max(0.12, (bpm - 116.0) / 20.0)), 2)
        vy = round(0.20 + ((cam_num * 7 + (3 if cam_let == "B" else 0)) % 11) * 0.065, 2)
        ratios = (0.08, 0.24, 0.34, 0.82)

        imported.append({
            "id": f"trk-{idx:02d}",
            "track_number": idx,
            "title": name,
            "artist": artist,
            "genre": genre,
            "bpm": round(bpm, 1),
            "camelot": camelot,
            "musical_key": CAMELOT_TO_MUSICAL.get(camelot, "Am"),
            "energy": energy,
            "duration": duration,
            "vibe_x": vx,
            "vibe_y": vy,
            "lufs": round(-14.0 + energy * 0.75, 1),
            "first_beat_sec": first_beat,
            "location": trk_el.attrib.get("Location") or f"file://localhost/Users/dj/Music/{name}.wav",
            "cues": sorted(parsed_cues, key=lambda c: c["num"]),
            "waveform": build_waveform_bands(idx, energy, duration, ratios),
            "source": "rekordbox_xml",
        })
    return imported


def analyze_audio_payload(payload: dict, existing_count: int = 24) -> dict:
    """Processes browser WebAudio DSP extraction (or raw metadata) into a full DJOID track."""
    idx = existing_count + 1
    filename = str(payload.get("filename") or f"Custom_Track_{idx}.wav")
    clean_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " - ")
    if " - " in clean_name:
        artist, title = [p.strip() for p in clean_name.split(" - ", 1)]
    else:
        artist = payload.get("artist") or "Local Audio Upload"
        title = payload.get("title") or clean_name

    bpm = float(payload.get("bpm") or 126.0)
    bpm = max(90.0, min(160.0, round(bpm * 2.0) / 2.0))
    duration = max(60, int(round(float(payload.get("duration") or 348))))
    camelot = str(payload.get("camelot") or "8A").upper()
    cam_num, cam_let = parse_camelot(camelot)
    camelot = f"{cam_num}{cam_let}"
    energy = max(1, min(10, int(round(float(payload.get("energy") or 7)))))
    lufs = round(float(payload.get("lufs") or (-13.5 + energy * 0.72)), 1)

    ratios = payload.get("cue_ratios") or [0.08, 0.24, 0.35, 0.82]
    if len(ratios) != 4:
        ratios = [0.08, 0.24, 0.35, 0.82]
    cues = make_cues(duration, bpm, tuple(ratios))

    wf = payload.get("waveform")
    if not isinstance(wf, dict) or "low" not in wf:
        wf = build_waveform_bands(idx, energy, duration, tuple(ratios))

    vx = round(min(0.96, max(0.12, (bpm - 116.0) / 20.0)), 2)
    vy = round(min(0.92, max(0.14, 0.18 + (energy / 12.0) * 0.55 + (0.15 if cam_let == "B" else 0.0))), 2)

    return {
        "id": f"trk-{idx:02d}",
        "track_number": idx,
        "title": title,
        "artist": artist,
        "genre": payload.get("genre") or "Analyzed Audio",
        "bpm": bpm,
        "camelot": camelot,
        "musical_key": CAMELOT_TO_MUSICAL.get(camelot, "Am"),
        "energy": energy,
        "duration": duration,
        "vibe_x": vx,
        "vibe_y": vy,
        "lufs": lufs,
        "first_beat_sec": float(payload.get("first_beat_sec") or 0.120),
        "location": f"file://localhost/Users/dj/Music/Uploads/{urllib.parse.quote(filename)}",
        "cues": cues,
        "waveform": wf,
        "source": "audio_dsp",
    }


SAMPLE_REKORDBOX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
  <COLLECTION Entries="2">
    <TRACK TrackID="901" Name="Lunar Phase (Club Dub)" Artist="Dixon &amp; Âme" Genre="Melodic Techno" TotalTime="384" AverageBpm="125.00" Tonality="6A" Location="file://localhost/Users/dj/Music/Lunar_Phase.wav">
      <TEMPO Inizio="0.120" Bpm="125.00" Metro="4/4" Battito="1"/>
      <POSITION_MARK Name="A: Intro (16b)" Type="0" Start="30.720" Num="0" Red="40" Green="226" Blue="20"/>
      <POSITION_MARK Name="B: Arpeggio Swell" Type="0" Start="92.160" Num="1" Red="245" Green="158" Blue="11"/>
      <POSITION_MARK Name="C: Main Drop" Type="0" Start="138.240" Num="2" Red="239" Green="68" Blue="68"/>
      <POSITION_MARK Name="D: Mix Out (16b)" Type="0" Start="307.200" Num="3" Red="59" Green="130" Blue="246"/>
    </TRACK>
    <TRACK TrackID="902" Name="Klockworks 34" Artist="DVS1" Genre="Hypnotic Techno" TotalTime="362" AverageBpm="131.00" Tonality="10A" Location="file://localhost/Users/dj/Music/Klockworks_34.wav">
      <TEMPO Inizio="0.095" Bpm="131.00" Metro="4/4" Battito="1"/>
      <POSITION_MARK Name="A: Polyrhythm In" Type="0" Start="29.310" Num="0" Red="40" Green="226" Blue="20"/>
      <POSITION_MARK Name="B: Filter Tension" Type="0" Start="87.940" Num="1" Red="245" Green="158" Blue="11"/>
      <POSITION_MARK Name="C: Sub Drop" Type="0" Start="131.910" Num="2" Red="239" Green="68" Blue="68"/>
      <POSITION_MARK Name="D: Outro Loop" Type="0" Start="293.130" Num="3" Red="59" Green="130" Blue="246"/>
    </TRACK>
  </COLLECTION>
</DJ_PLAYLISTS>
"""
