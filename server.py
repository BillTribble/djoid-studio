#!/usr/bin/env python3
"""DJOID Studio — Standalone AI DJ Set & Rekordbox XML Studio HTTP Server (:18919)."""

import argparse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import urllib.parse

from engine import (
    SAMPLE_REKORDBOX_XML,
    analyze_audio_payload,
    build_harmonic_graph,
    export_m3u8,
    export_rekordbox_xml,
    find_bridge_path,
    parse_rekordbox_xml,
    solve_set,
)
from library_data import ENERGY_PRESETS, build_initial_library

APP_BUILD = "2026.10.15-r1"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "debug.log")

STATE_LOCK = threading.Lock()
TRACK_LIBRARY = build_initial_library()
CURRENT_CURVE = list(ENERGY_PRESETS["warmup_to_peak"]["curve"])
CURRENT_WEIGHTS = {
    "harmonic_strictness": 82.0,
    "bpm_tolerance": 3.5,
    "energy_adherence": 85.0,
}


def append_debug_log(event: str, detail: str = ""):
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [build={APP_BUILD}] {event} {detail}\n"
    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


class DjoidRequestHandler(SimpleHTTPRequestHandler):
    """Serves static UI and JSON/XML/M3U8 API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, payload: dict, status: int = 200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(self, text: str, content_type: str, filename: str = None, status: int = 200):
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/state":
            with STATE_LOCK:
                tracks = list(TRACK_LIBRARY)
                curve = list(CURRENT_CURVE)
                weights = dict(CURRENT_WEIGHTS)
            solved = solve_set(
                tracks,
                curve,
                harmonic_strictness=weights["harmonic_strictness"],
                bpm_tolerance=weights["bpm_tolerance"],
                energy_adherence=weights["energy_adherence"],
            )
            set_tracks = [s["track"] for s in solved["slots"]]
            xml_preview = export_rekordbox_xml(set_tracks, playlist_name="DJOID Studio AI Set")
            bridge_default = find_bridge_path(tracks, tracks[2]["id"], tracks[18]["id"], weights["bpm_tolerance"])
            self._send_json({
                "app_build": APP_BUILD,
                "tracks": tracks,
                "edges": build_harmonic_graph(tracks),
                "presets": ENERGY_PRESETS,
                "curve": curve,
                "weights": weights,
                "solved_set": solved,
                "default_bridge": bridge_default,
                "xml_preview": xml_preview,
                "sample_rekordbox_xml": SAMPLE_REKORDBOX_XML,
            })
            return

        if path == "/api/export/rekordbox.xml":
            playlist_name = qs.get("name", ["DJOID Studio AI Set"])[0]
            track_ids = qs.get("ids", [""])[0].split(",") if qs.get("ids") else []
            with STATE_LOCK:
                by_id = {t["id"]: t for t in TRACK_LIBRARY}
                if track_ids and all(tid in by_id for tid in track_ids if tid):
                    selected = [by_id[tid] for tid in track_ids if tid in by_id]
                else:
                    solved = solve_set(
                        TRACK_LIBRARY,
                        CURRENT_CURVE,
                        harmonic_strictness=CURRENT_WEIGHTS["harmonic_strictness"],
                        bpm_tolerance=CURRENT_WEIGHTS["bpm_tolerance"],
                        energy_adherence=CURRENT_WEIGHTS["energy_adherence"],
                    )
                    selected = [s["track"] for s in solved["slots"]]
            xml_doc = export_rekordbox_xml(selected, playlist_name=playlist_name)
            dl = qs.get("download", ["1"])[0] == "1"
            self._send_text(
                xml_doc,
                "application/xml; charset=utf-8",
                filename="rekordbox.xml" if dl else None,
            )
            return

        if path == "/api/export/playlist.m3u8":
            playlist_name = qs.get("name", ["DJOID Studio AI Set"])[0]
            track_ids = qs.get("ids", [""])[0].split(",") if qs.get("ids") else []
            with STATE_LOCK:
                by_id = {t["id"]: t for t in TRACK_LIBRARY}
                if track_ids and all(tid in by_id for tid in track_ids if tid):
                    selected = [by_id[tid] for tid in track_ids if tid in by_id]
                else:
                    solved = solve_set(
                        TRACK_LIBRARY,
                        CURRENT_CURVE,
                        harmonic_strictness=CURRENT_WEIGHTS["harmonic_strictness"],
                        bpm_tolerance=CURRENT_WEIGHTS["bpm_tolerance"],
                        energy_adherence=CURRENT_WEIGHTS["energy_adherence"],
                    )
                    selected = [s["track"] for s in solved["slots"]]
            m3u_doc = export_m3u8(selected, playlist_name=playlist_name)
            self._send_text(
                m3u_doc,
                "audio/x-mpegurl; charset=utf-8",
                filename="djoid_set.m3u8",
            )
            return

        if path == "/data/debug.log":
            if os.path.exists(DEBUG_LOG_PATH):
                with open(DEBUG_LOG_PATH, "r", encoding="utf-8") as f:
                    self._send_text(f.read(), "text/plain; charset=utf-8")
            else:
                self._send_text("", "text/plain; charset=utf-8")
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json_body()
        except Exception as exc:
            self._send_json({"error": f"Invalid JSON body: {exc}"}, status=400)
            return

        if path == "/api/solve-set":
            with STATE_LOCK:
                curve = body.get("curve") or list(CURRENT_CURVE)
                h_strict = float(body.get("harmonic_strictness", CURRENT_WEIGHTS["harmonic_strictness"]))
                bpm_tol = float(body.get("bpm_tolerance", CURRENT_WEIGHTS["bpm_tolerance"]))
                e_adh = float(body.get("energy_adherence", CURRENT_WEIGHTS["energy_adherence"]))
                seed_id = body.get("seed_track_id") or None
                CURRENT_CURVE[:] = [int(round(float(x))) for x in curve]
                CURRENT_WEIGHTS["harmonic_strictness"] = h_strict
                CURRENT_WEIGHTS["bpm_tolerance"] = bpm_tol
                CURRENT_WEIGHTS["energy_adherence"] = e_adh
                tracks = list(TRACK_LIBRARY)

            solved = solve_set(
                tracks,
                CURRENT_CURVE,
                harmonic_strictness=h_strict,
                bpm_tolerance=bpm_tol,
                energy_adherence=e_adh,
                seed_track_id=seed_id,
            )
            set_tracks = [s["track"] for s in solved["slots"]]
            playlist_name = body.get("playlist_name") or "DJOID Studio AI Set"
            xml_preview = export_rekordbox_xml(set_tracks, playlist_name=playlist_name)
            append_debug_log(
                "solve_set",
                f"slots={len(set_tracks)} score={solved['metrics'].get('set_score')}",
            )
            self._send_json({
                "solved_set": solved,
                "xml_preview": xml_preview,
                "curve": CURRENT_CURVE,
                "weights": CURRENT_WEIGHTS,
            })
            return

        if path == "/api/bridge":
            source_id = body.get("source_id")
            target_id = body.get("target_id")
            bpm_tol = float(body.get("bpm_tolerance", CURRENT_WEIGHTS["bpm_tolerance"]))
            with STATE_LOCK:
                tracks = list(TRACK_LIBRARY)
            result = find_bridge_path(tracks, source_id, target_id, bpm_tolerance=bpm_tol)
            append_debug_log("bridge", f"{source_id}->{target_id} avg={result.get('bridge_avg_score')}")
            self._send_json(result)
            return

        if path == "/api/import-xml":
            xml_text = body.get("xml") or SAMPLE_REKORDBOX_XML
            try:
                with STATE_LOCK:
                    imported = parse_rekordbox_xml(xml_text, existing_count=len(TRACK_LIBRARY))
                    TRACK_LIBRARY.extend(imported)
                    tracks = list(TRACK_LIBRARY)
                    curve = list(CURRENT_CURVE)
                    weights = dict(CURRENT_WEIGHTS)
            except Exception as exc:
                self._send_json({"error": f"Failed to parse Rekordbox XML: {exc}"}, status=400)
                return

            solved = solve_set(
                tracks,
                curve,
                harmonic_strictness=weights["harmonic_strictness"],
                bpm_tolerance=weights["bpm_tolerance"],
                energy_adherence=weights["energy_adherence"],
            )
            set_tracks = [s["track"] for s in solved["slots"]]
            append_debug_log("import_xml", f"imported={len(imported)} total={len(tracks)}")
            self._send_json({
                "imported": imported,
                "tracks": tracks,
                "edges": build_harmonic_graph(tracks),
                "solved_set": solved,
                "xml_preview": export_rekordbox_xml(set_tracks),
            })
            return

        if path == "/api/analyze-audio":
            with STATE_LOCK:
                new_track = analyze_audio_payload(body, existing_count=len(TRACK_LIBRARY))
                TRACK_LIBRARY.append(new_track)
                tracks = list(TRACK_LIBRARY)
                curve = list(CURRENT_CURVE)
                weights = dict(CURRENT_WEIGHTS)

            solved = solve_set(
                tracks,
                curve,
                harmonic_strictness=weights["harmonic_strictness"],
                bpm_tolerance=weights["bpm_tolerance"],
                energy_adherence=weights["energy_adherence"],
            )
            set_tracks = [s["track"] for s in solved["slots"]]
            append_debug_log("analyze_audio", f"track={new_track['id']} bpm={new_track['bpm']} key={new_track['camelot']}")
            self._send_json({
                "track": new_track,
                "tracks": tracks,
                "edges": build_harmonic_graph(tracks),
                "solved_set": solved,
                "xml_preview": export_rekordbox_xml(set_tracks),
            })
            return

        if path == "/api/log":
            append_debug_log(str(body.get("event", "client")), str(body.get("detail", "")))
            self._send_json({"ok": True})
            return

        self._send_json({"error": "Not found"}, status=404)


def main():
    parser = argparse.ArgumentParser(description="DJOID Studio Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "18919")))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    append_debug_log("boot", f"starting server on {args.host}:{args.port}")
    server = ThreadingHTTPServer((args.host, args.port), DjoidRequestHandler)
    print(f"DJOID Studio build {APP_BUILD} listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
