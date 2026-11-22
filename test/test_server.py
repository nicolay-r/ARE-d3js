import json
import os
import sys
import tempfile
import unittest
from os.path import dirname, join, realpath

WEB_ROOT = dirname(dirname(realpath(__file__)))
sys.path.insert(0, WEB_ROOT)

import server
from fastapi.testclient import TestClient


def _graph(name, source, target, weight=2):
    return {
        "basis": [name],
        "equation": "[" + name + "]",
        "nodes": [{"id": source, "c": 1}, {"id": target, "c": 1}],
        "links": [{"source": source, "target": target, "c": weight, "sent": "pos"}],
    }


class TestFastAPIServer(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        root = self._tmpdir.name
        self._status = join(root, "data_status.json")
        with open(self._status, "w") as handle:
            json.dump({"server": {"port": 8000}, "data": {"kept": {"data_status": "completed"}}}, handle)

        output = join(root, "output")
        self._saved = {
            "data_status_file": server.data_status_file,
            "settings": json.loads(json.dumps({
                "path_to_raw_data": server.SETTINGS["path_to_raw_data"],
                "path_to_force_data": server.SETTINGS["path_to_force_data"],
                "path_to_radial_data": server.SETTINGS["path_to_radial_data"],
                "output_template": server.SETTINGS["arelight_const_args"]["output_template"],
            })),
        }
        self._run_inference = server.run_inference
        server.data_status_file = self._status
        server.SETTINGS["path_to_raw_data"] = join(root, "raw")
        server.SETTINGS["path_to_force_data"] = join(output, "force")
        server.SETTINGS["path_to_radial_data"] = join(output, "radial")
        server.SETTINGS["arelight_const_args"]["output_template"] = output
        os.makedirs(server.SETTINGS["path_to_raw_data"], exist_ok=True)
        self.client = TestClient(server.app)

    def tearDown(self):
        server.run_inference = self._run_inference
        server.data_status_file = self._saved["data_status_file"]
        server.SETTINGS["path_to_raw_data"] = self._saved["settings"]["path_to_raw_data"]
        server.SETTINGS["path_to_force_data"] = self._saved["settings"]["path_to_force_data"]
        server.SETTINGS["path_to_radial_data"] = self._saved["settings"]["path_to_radial_data"]
        server.SETTINGS["arelight_const_args"]["output_template"] = self._saved["settings"]["output_template"]
        self._tmpdir.cleanup()

    def test_provider_paths_come_from_demo(self):
        resolved = server.provider_path("providers/dp_130.py")
        self.assertTrue(resolved.endswith("/demo/providers/dp_130.py"))
        self.assertTrue(os.path.isfile(resolved))
        self.assertTrue(server.provider_path("providers/googletrans_402.py").endswith("/demo/providers/gt_402.py"))
        self.assertTrue(server.provider_path("providers/replicate_104.py").endswith("/demo/providers/replicate_104.py"))

    def test_index_lists_pipeline_fields(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("sentence_parser", response.text)
        self.assertIn("terms_per_context", response.text)
        self.assertIn("Эммануэль Макрон", response.text)
        self.assertIn(">Upload<", response.text)
        self.assertIn("/stream-with-post", response.text)
        self.assertIn('"/get_graph_data?layout=force&file="', response.text)
        self.assertIn('"/get_graph_data?layout=radial&file="', response.text)
        self.assertNotIn("//get_graph_data", response.text)
        self.assertIn("showCompletedDataset(payload.collection)", response.text)
        self.assertIn("import_progress", response.text)
        self.assertIn("text/html", response.headers["content-type"])

    def test_inference_api_reads_env_placeholder(self):
        previous = os.environ.get("API_TOKEN")
        os.environ["API_TOKEN"] = "test-token"
        try:
            self.assertEqual(server.inference_api_key(), "test-token")
        finally:
            if previous is None:
                os.environ.pop("API_TOKEN", None)
            else:
                os.environ["API_TOKEN"] = previous

    def test_available_files(self):
        response = self.client.get("/available_files")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["kept"])

    def _fake_inference(self, seen, messages):
        def fake_run(filepath, options, progress=None):
            seen["filepath"] = filepath
            seen["options"] = options
            for message in messages:
                if progress is not None:
                    progress(message)
            stem = os.path.splitext(os.path.basename(filepath))[0]
            server.__update_data_status__(stem, "completed")
            return stem

        server.run_inference = fake_run

    def test_upload_streams_progress(self):
        seen = {}
        self._fake_inference(seen, ["Reading notes", "Sampling and inference"])
        response = self.client.post(
            "/stream-with-post",
            files={"file": ("notes.txt", b"Obama met Merkel in Berlin.", "text/plain")},
            data={"sentence_parser": "nltk:english", "batch_size": "1", "csv_column": "text"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: progress", response.text)
        self.assertIn("Reading notes", response.text)
        self.assertIn("event: completed", response.text)
        self.assertIn("notes", response.text)
        self.assertTrue(seen["filepath"].endswith("notes.txt"))
        self.assertEqual(seen["options"]["sentence_parser"], "nltk:english")
        self.assertEqual(server.__get_data_status__("notes")["data_status"], "completed")
        self.assertTrue(os.path.exists(seen["filepath"]))

    def test_pasted_text_streams_progress(self):
        seen = {}
        self._fake_inference(seen, ["Running pasted-demo"])
        response = self.client.post(
            "/stream-with-post",
            data={"text": "Франция и Германия обсуждают Евросоюз.", "dataset_name": "pasted-demo",
                  "sentence_parser": "nltk:russian"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: completed", response.text)
        self.assertIn("pasted-demo", response.text)
        self.assertTrue(seen["filepath"].endswith("pasted-demo.txt"))
        self.assertNotIn("text", seen["options"])
        with open(seen["filepath"], encoding="utf-8") as handle:
            self.assertIn("Евросоюз", handle.read())

    def test_graph_operation_uses_pipeline(self):
        force = server.SETTINGS["path_to_force_data"]
        os.makedirs(force, exist_ok=True)
        with open(join(force, "alpha.json"), "w") as handle:
            json.dump(_graph("alpha", "PERSON.Ann", "ORG.UN", 2), handle)
        with open(join(force, "beta.json"), "w") as handle:
            json.dump(_graph("beta", "PERSON.Ann", "LOC.Paris", 3), handle)

        response = self.client.post("/", json={
            "operation": {"A": ["alpha"], "B": ["beta"], "O": "UNION", "D": "alpha_beta"}
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["name"], "alpha_beta")

        graph = self.client.get("/get_graph_data", params={"layout": "force", "file": "alpha_beta"})
        self.assertEqual(graph.status_code, 200, graph.text)
        body = graph.json()
        link_targets = {link["target"] for link in body["links"]}
        self.assertIn("ORG.UN", link_targets)
        self.assertIn("LOC.Paris", link_targets)

        radial = self.client.get("/get_graph_data", params={"layout": "radial", "file": "alpha_beta"})
        self.assertEqual(radial.status_code, 200)
        self.assertIsInstance(radial.json(), list)

        files = self.client.get("/available_files").json()
        self.assertIn("alpha_beta", files)


if __name__ == "__main__":
    unittest.main()
