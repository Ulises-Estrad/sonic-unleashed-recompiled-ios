"""Small synthetic fixtures only; never reads or copies a user's game dump."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_arcade_mod import (
    DEFAULT_CATALOG,
    load_catalog,
    stage_append_archives,
    validate_payload,
)
from prepare_arcade_data import catalog_archive_sets, selected_game_files


class BossArchiveDependencyTests(unittest.TestCase):
    def setUp(self):
        self.stage = {
            "label": "Act 5",
            "archive": "ActD_SubAfrica_04",
            "source": "Mazuri Adventure Pack",
            "append": ["BossEggBeetle"],
        }
        self.catalog = {"countries": [{"name": "Mazuri", "stages": [self.stage]}]}

    def test_catalog_retains_parent_without_adding_playable_stage(self):
        catalog = load_catalog(DEFAULT_CATALOG)
        archives, packs = catalog_archive_sets(catalog)
        self.assertIn("BossEggBeetle", archives)
        self.assertIn("BossCommon", archives)
        self.assertIn("ActD_SubAfrica_04", packs["Mazuri Adventure Pack"])
        self.assertNotIn("BossCommon", packs["Mazuri Adventure Pack"])
        self.assertEqual(sum(len(c["stages"]) for c in catalog["countries"]), 48)

    def test_any_boss_append_requires_common_but_ordinary_append_does_not(self):
        self.assertEqual(stage_append_archives(self.stage), {"BossEggBeetle", "BossCommon"})
        self.assertEqual(stage_append_archives({"append": ["BossEggLancer"]}), {"BossEggLancer", "BossCommon"})
        self.assertEqual(stage_append_archives({"append": ["SonicActionCommon"]}), {"SonicActionCommon"})
        self.assertEqual(stage_append_archives({}), set())
        self.assertEqual(self.stage["append"], ["BossEggBeetle"])

    def test_sideloadly_keeps_complete_family_not_other_bosses(self):
        names = {
            "BossCommon.arl", "BossCommon.ar.00", "#BossCommon.arl", "#BossCommon.ar.00",
            "BossEggBeetle.arl", "BossEggBeetle.ar.00", "BossEggBeetle.ar.01",
            "BossEggLancer.arl", "BossEggLancer.ar.00", "ActN_Africa.arl", "Town_Africa.arl",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "game"
            game.mkdir()
            for name in names:
                (game / name).write_bytes(b"fixture")
            selected = {p.name for p in selected_game_files(root, self.catalog, "sideloadly")}
        self.assertEqual(selected, {n for n in names if n.startswith(("BossCommon.", "#BossCommon.", "BossEggBeetle."))})

    def test_payload_validation_rejects_missing_parent_list_or_payload(self):
        required = (
            "game/default.xex", "game/shader.ar", "game/#SonicActionCommon.arl",
            "update/default.xexp", "patched/default.xex", "game/BossEggBeetle.arl",
            "dlc/Mazuri Adventure Pack/#ActD_SubAfrica_04.arl",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, r"BossCommon\.arl"):
                validate_payload(root, self.catalog)
            (root / "game/BossCommon.arl").write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, r"BossCommon\.ar\.00"):
                validate_payload(root, self.catalog)
            (root / "game/BossCommon.ar.00").write_bytes(b"fixture")
            validate_payload(root, self.catalog)


if __name__ == "__main__":
    unittest.main()
