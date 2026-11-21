import json
import os
import sqlite3
import sys
import tempfile
import unittest
from os.path import dirname, join, realpath

WEB_ROOT = dirname(dirname(realpath(__file__)))
sys.path.insert(0, WEB_ROOT)

from dotenv import load_dotenv

load_dotenv(join(WEB_ROOT, "demo", ".env"))

import server
from arelight_preset import UI_INFER_PRESETS


class TestStreamPipeline(unittest.TestCase):
    """ The inference pipeline `/stream-with-post` runs through `run_inference`. """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        root = self._tmpdir.name
        self._status = join(root, "data_status.json")
        with open(self._status, "w") as handle:
            json.dump({"server": {"port": 8000}, "data": {}}, handle)

        output = join(root, "output")
        self._saved = {
            "data_status_file": server.data_status_file,
            "settings": {
                "path_to_raw_data": server.SETTINGS["path_to_raw_data"],
                "path_to_force_data": server.SETTINGS["path_to_force_data"],
                "path_to_radial_data": server.SETTINGS["path_to_radial_data"],
                "output_template": server.SETTINGS["arelight_const_args"]["output_template"],
            },
        }
        server.data_status_file = self._status
        server.SETTINGS["path_to_raw_data"] = join(root, "raw")
        server.SETTINGS["path_to_force_data"] = join(output, "force")
        server.SETTINGS["path_to_radial_data"] = join(output, "radial")
        server.SETTINGS["arelight_const_args"]["output_template"] = output
        os.makedirs(server.SETTINGS["path_to_raw_data"], exist_ok=True)
        self._output = output

    def tearDown(self):
        server.data_status_file = self._saved["data_status_file"]
        server.SETTINGS["path_to_raw_data"] = self._saved["settings"]["path_to_raw_data"]
        server.SETTINGS["path_to_force_data"] = self._saved["settings"]["path_to_force_data"]
        server.SETTINGS["path_to_radial_data"] = self._saved["settings"]["path_to_radial_data"]
        server.SETTINGS["arelight_const_args"]["output_template"] = self._saved["settings"]["output_template"]
        self._tmpdir.cleanup()

    def test_run_inference_builds_graphs(self):
        token = os.environ.get("API_TOKEN", "").strip()
        if not token or token in ("None", "null"):
            self.skipTest("API_TOKEN is empty")

        stem = "pipeline-demo"
        filepath = join(server.SETTINGS["path_to_raw_data"], stem + ".txt")
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write("Эммануэль Макрон посетил Берлин.\n")

        options = dict(UI_INFER_PRESETS["russian"])
        options["inference_api"] = ""
        options["docs_limit"] = "1"
        server.__set_data_status__(stem, {"data_status": "processing", "inference_api": ""})

        messages = []
        name = server.run_inference(filepath, options, progress=messages.append)

        self.assertEqual(name, stem)
        self.assertTrue(any(line.startswith("Running ") for line in messages))
        self.assertIn("Graphs saved for {0}".format(stem), messages)
        self.assertEqual(server.__get_data_status__(stem)["data_status"], "completed")

        with open(self._status, encoding="utf-8") as handle:
            status_text = handle.read()
        self.assertFalse(token in status_text, "data_status.json contains API_TOKEN")

        database = join(self._output, stem + "-test.sqlite")
        self.assertTrue(os.path.isfile(database), database)
        connection = sqlite3.connect(database)
        try:
            contents = connection.execute("SELECT COUNT(*) FROM contents").fetchone()[0]
            predicted = connection.execute("SELECT COUNT(*) FROM bulk_chain").fetchone()[0]
        finally:
            connection.close()
        self.assertGreater(contents, 0)
        self.assertGreater(predicted, 0)

        for folder in ("force", "radial"):
            graph_path = join(self._output, folder, stem + ".json")
            self.assertTrue(os.path.isfile(graph_path), graph_path)
            with open(graph_path, encoding="utf-8") as handle:
                graph = json.load(handle)
            self.assertTrue(graph)


if __name__ == "__main__":
    unittest.main()
