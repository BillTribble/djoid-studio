#!/usr/bin/env python3
"""Unit tests for DJOID Studio engine, Rekordbox XML round-trip, A* bridge, and beam solver."""

import unittest
import xml.etree.ElementTree as ET

from engine import (
    SAMPLE_REKORDBOX_XML,
    analyze_audio_payload,
    build_harmonic_graph,
    export_m3u8,
    export_rekordbox_xml,
    find_bridge_path,
    harmonic_compatibility,
    parse_rekordbox_xml,
    solve_set,
)
from library_data import ENERGY_PRESETS, build_initial_library


class DjoidEngineTest(unittest.TestCase):
    def setUp(self):
        self.tracks = build_initial_library()

    def test_initial_library_has_24_tracks_and_cues(self):
        self.assertEqual(len(self.tracks), 24)
        for trk in self.tracks:
            self.assertEqual(len(trk["cues"]), 4)
            self.assertEqual([c["slot"] for c in trk["cues"]], ["A", "B", "C", "D"])
            self.assertEqual(len(trk["waveform"]["low"]), 64)

    def test_camelot_harmonic_rules(self):
        score_same, rel_same, _, _ = harmonic_compatibility("8A", "8A")
        self.assertEqual(score_same, 1.0)
        self.assertEqual(rel_same, "same_key")

        score_fifth, rel_fifth, _, _ = harmonic_compatibility("8A", "9A")
        self.assertGreaterEqual(score_fifth, 0.94)
        self.assertEqual(rel_fifth, "adjacent_fifth")

        score_rel, rel_mode, _, _ = harmonic_compatibility("8A", "8B")
        self.assertGreaterEqual(score_rel, 0.90)
        self.assertEqual(rel_mode, "relative_mode")

    def test_beam_search_set_solver(self):
        curve = ENERGY_PRESETS["warmup_to_peak"]["curve"]
        solved = solve_set(self.tracks, curve, harmonic_strictness=85, bpm_tolerance=3.5, energy_adherence=85)
        self.assertEqual(len(solved["slots"]), 8)
        ids = [s["track"]["id"] for s in solved["slots"]]
        self.assertEqual(len(set(ids)), 8)
        self.assertGreaterEqual(solved["metrics"]["set_score"], 75.0)
        self.assertIn("Hot Cue", solved["slots"][1]["transition_from_prev"]["coaching"])

    def test_astar_bridge_finder(self):
        res = find_bridge_path(self.tracks, "trk-03", "trk-19", bpm_tolerance=3.5)
        self.assertGreaterEqual(len(res["path"]), 2)
        self.assertEqual(res["path"][0]["id"], "trk-03")
        self.assertEqual(res["path"][-1]["id"], "trk-19")
        self.assertGreaterEqual(res["bridge_avg_score"], res["direct_score"])

    def test_rekordbox_xml_export_and_reimport(self):
        xml_str = export_rekordbox_xml(self.tracks[:8], playlist_name="Test Club Set")
        root = ET.fromstring(xml_str)
        self.assertEqual(root.tag, "DJ_PLAYLISTS")
        self.assertEqual(root.attrib.get("Version"), "1.0.0")
        tracks_el = root.findall(".//COLLECTION/TRACK")
        self.assertEqual(len(tracks_el), 8)
        # Verify TEMPO and POSITION_MARK Hot Cues (0..3) + Memory Cues (-1)
        first_trk = tracks_el[0]
        self.assertIsNotNone(first_trk.find("TEMPO"))
        marks = first_trk.findall("POSITION_MARK")
        nums = [m.attrib.get("Num") for m in marks]
        for hot_num in ("0", "1", "2", "3", "-1"):
            self.assertIn(hot_num, nums)

        reimported = parse_rekordbox_xml(xml_str, existing_count=24)
        self.assertEqual(len(reimported), 8)
        self.assertEqual(reimported[0]["title"], self.tracks[0]["title"])

    def test_sample_xml_and_audio_dsp_payload(self):
        imp = parse_rekordbox_xml(SAMPLE_REKORDBOX_XML, existing_count=24)
        self.assertEqual(len(imp), 2)
        analyzed = analyze_audio_payload({"filename": "Bicep - Glue.wav", "bpm": 130.0, "camelot": "8A", "energy": 8}, 26)
        self.assertEqual(analyzed["artist"], "Bicep")
        self.assertEqual(analyzed["title"], "Glue")
        self.assertEqual(len(analyzed["cues"]), 4)
        m3u = export_m3u8(self.tracks[:4], "Club M3U")
        self.assertIn("#EXTM3U", m3u)
        self.assertGreater(len(build_harmonic_graph(self.tracks)), 10)


if __name__ == "__main__":
    unittest.main()
