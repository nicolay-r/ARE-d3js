import asyncio
import json
import logging
import os
from os.path import basename, join
from threading import Lock

from arekit.common.pipeline.base import BasePipelineLauncher
from bulk_chain.core.utils import dynamic_init
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from arelight.api import create_inference_pipeline
from arelight.arekit.sample_service import AREkitSamplesService
from arelight.backend.d3js.relations_graph_operations import OP_DIFFERENCE, OP_INTERSECTION, OP_UNION
from arelight.backend.d3js.utils_graph import load_graph
from arelight.pipelines.demo.labels.formatter import CustomLabelsFormatter
from demo.d3js_graphs import D3jsGraphsBackendPipelineItem
from demo.d3js_operations import D3jsGraphOperationsBackendPipelineItem
from arelight.pipelines.result import PipelineResult
from arelight.run.infer import create_infer_parser
from arelight.run.utils import merge_dictionaries

from demo.rows import iter_rows_from_files
from arelight.run.utils_logger import TqdmToLogger

from arelight_preset import CONSTANT_INFER_IGNORE_PARAMS, CONSTANT_INFER_PARAMS, PROVIDERS_DIR, UI_INFER_PRESETS
from utils import CUR_DIR, do_format, extract, setup_preset


DEMO_DIR = join(CUR_DIR, "demo")
load_dotenv(join(DEMO_DIR, ".env"))

PREDICT_TABLE = "bulk_chain"
_status_lock = Lock()
_OUTPUT_DIR = join(CUR_DIR, CONSTANT_INFER_PARAMS["output_template"])
data_status_file = join(_OUTPUT_DIR, "data_status.json")

SETTINGS = {
    "path_to_raw_data": join(CUR_DIR, "raw_data"),
    "path_to_force_data": join(_OUTPUT_DIR, "force"),
    "path_to_radial_data": join(_OUTPUT_DIR, "radial"),
    "arelight_const_args": {**CONSTANT_INFER_PARAMS, "output_template": _OUTPUT_DIR},
    "arelight_args": {
        k: do_format(v, is_check=False)
        for k, v in extract(create_infer_parser(), args=[])["schema"].items()
        if k not in CONSTANT_INFER_PARAMS and k not in CONSTANT_INFER_IGNORE_PARAMS
    },
    "port": None,
}


def _ensure_data_status():
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    if os.path.isfile(data_status_file):
        return
    with open(data_status_file, "w") as handle:
        json.dump({"server": {"port": 8000}, "data": {}}, handle, indent=4)


_ensure_data_status()
with open(data_status_file, "r") as handle:
    SETTINGS["port"] = json.load(handle)["server"]["port"]

setup_preset(predefined_args=SETTINGS["arelight_args"], preset=UI_INFER_PRESETS["russian"],
             ignored_params=CONSTANT_INFER_IGNORE_PARAMS)

app = FastAPI(title="ARElight")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(SETTINGS["path_to_raw_data"], exist_ok=True)


def _output_dir():
    return SETTINGS["arelight_const_args"]["output_template"]


def _opt(options, key, default=None):
    if key not in options:
        return default
    value = options[key]
    if value is None:
        return default
    if isinstance(value, str) and value.strip() in ("", "None", "null"):
        return default
    return value


def _opt_int(options, key, default=None):
    value = _opt(options, key, None)
    if value is None:
        return default
    return int(value)


with open(join(DEMO_DIR, "attitude.json"), encoding="utf-8") as handle:
    _ATTITUDE = json.load(handle)


def _classify_attitude(row):
    lowered = "" if row is None else str(row).lower()
    for item in _ATTITUDE["classes"]:
        if item["contains"] in lowered:
            return item["value"]
    return _ATTITUDE["default"]


_API_PLACEHOLDERS = {"API_TOKEN", "${API_TOKEN}"}


def inference_api_key(options):
    """ Form value wins. An empty field or the placeholder reads API_TOKEN from .env. """
    value = _opt(options, "inference_api")
    if isinstance(value, str) and value.strip() in _API_PLACEHOLDERS:
        value = None
    if value:
        return value
    token = os.environ.get("API_TOKEN")
    if token is None or token.strip() in ("", "None", "null"):
        return None
    return token.strip()


_PROVIDER_ALIASES = {"googletrans_402.py": "gt_402.py"}


def provider_path(value):
    """ Resolve a provider script from this project's demo/providers directory. """
    if value is None:
        return None
    text = str(value)
    name = _PROVIDER_ALIASES.get(basename(text), basename(text))
    candidate = join(PROVIDERS_DIR, name)
    if os.path.isfile(candidate):
        return candidate
    if os.path.isfile(text):
        return text
    return text


def stored_upload_name(filename):
    base = basename(filename).replace(" ", "")
    lower = base.lower()
    for ext in (".txt", ".csv", ".zip"):
        if lower.endswith(ext):
            return base[:-len(ext)], base
    return base, base


def generate_ARELIGHT_PARAMETERS():
    html_code = ""
    for parameter_name, parameter_info in SETTINGS["arelight_args"].items():
        if parameter_name == "inference_api":
            html_code += """
            <small class="form-text text-muted">inference_api:</small>
            <input class="form-control" type="text" name="inference_api" value="" placeholder="API_TOKEN" autocomplete="off">"""
            continue
        if "const" in parameter_info:
            html_code += f"""
            <small class="form-text text-muted">{parameter_name}:</small>
            <input type="text" class="form-control" disabled="disabled" name="{parameter_name}" value="{parameter_info['const']}">"""
        elif "list" in parameter_info:
            html_code += f"""
            <small class="form-text text-muted">{parameter_name}:</small>
            <select class="form-control" name="{parameter_name}">"""
            for option in parameter_info["list"]:
                html_code += f"""<option value="{option}">{option}</option>"""
            html_code += """</select>"""
        elif "check" in parameter_info:
            html_code += f"""
            <small class="form-text text-muted">{parameter_name}:</small>"""
            for option in parameter_info["check"]:
                html_code += f"""
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="{parameter_name}" value="{option}" id="{option}" checked>
                    <label class="form-check-label" for="{option}"><span class="grey-text">{option}</span></label>
                </div>
                """
        elif "field" in parameter_info:
            html_code += f"""
            <small class="form-text text-muted">{parameter_name}:</small>
            <input class="form-control" type="number" name="{parameter_name}" value="{parameter_info['field']}">"""
    return html_code


def __read_template(name):
    with open(join(DEMO_DIR, name), "r") as handle:
        return handle.read()


def __get_html_template__():
    return (__read_template("template.html")
            .replace("<!--ARELIGHT ARGUMENTS-->", generate_ARELIGHT_PARAMETERS())
            .replace("<---SERVER-PORT--->", str(SETTINGS["port"])))


def __set_data_status__(filename, data):
    filename = basename(filename)
    with _status_lock:
        with open(data_status_file, "r") as handle:
            data_status = json.load(handle)
        data_status["data"][filename] = data
        with open(data_status_file, "w") as handle:
            json.dump(data_status, handle, indent=4)


def __get_data_status__(filename):
    filename = basename(filename)
    with _status_lock:
        with open(data_status_file, "r") as handle:
            return json.load(handle)["data"][filename]


def __update_data_status__(filename, status):
    filename = basename(filename)
    data = __get_data_status__(filename)
    data["data_status"] = status
    __set_data_status__(filename, data)


def get_all_data_status():
    with _status_lock:
        with open(data_status_file, "r") as handle:
            return json.load(handle)["data"]


def _graph_path(name):
    filename = basename(name)
    if not filename.endswith(".json"):
        filename += ".json"
    return join(SETTINGS["path_to_force_data"], filename)


def run_operation(path_a, path_b, operation, collection_name, description):
    label_names = SETTINGS["arelight_const_args"]["d3js_label_names"]
    label_fmt = {a: v for a, v in map(lambda item: item.split(":"), label_names.split(","))}
    BasePipelineLauncher.run(
        pipeline=[D3jsGraphOperationsBackendPipelineItem()],
        pipeline_ctx=PipelineResult({
            "labels_formatter": CustomLabelsFormatter(**label_fmt),
            "d3js_graph_output_dir": _output_dir(),
            "d3js_collection_description": description,
            "d3js_graph_a": load_graph(path_a),
            "d3js_graph_b": load_graph(path_b),
            "d3js_graph_operations": operation,
            "d3js_collection_name": collection_name,
        }),
        has_input=False)


def _combine_graphs(names, label):
    paths = [_graph_path(name) for name in names]
    if len(paths) == 1:
        return paths[0]
    current = paths[0]
    for index, nxt in enumerate(paths[1:], start=1):
        run_operation(current, nxt, OP_UNION, label, label)
        current = _graph_path(label)
    return current


class _ProgressLogHandler(logging.Handler):

    def __init__(self, callback):
        super(_ProgressLogHandler, self).__init__()
        self._callback = callback

    def emit(self, record):
        message = record.getMessage().strip()
        if message:
            self._callback(message)


def _sse(event, payload):
    return "event: {event}\ndata: {data}\n\n".format(
        event=event, data=json.dumps(payload, ensure_ascii=False))


def run_inference(filepath, options, progress=None):
    """ Run sampling, attitude inference and the D3.js graph backend on one file. """
    def report(message):
        if progress is not None:
            progress(message)

    try:
        consts = SETTINGS["arelight_const_args"]
        collection_name = basename(filepath)
        for ext in (".txt", ".csv", ".zip"):
            if collection_name.lower().endswith(ext):
                collection_name = collection_name[:-len(ext)]
                break
        output_dir = _output_dir()
        os.makedirs(output_dir, exist_ok=True)

        logger = logging.getLogger("arelight")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if progress is not None:
            logger.addHandler(_ProgressLogHandler(progress))
        report("Running {0}".format(collection_name))

        ner_types = _opt(options, "ner_types")
        ner_type_set = None if ner_types is None else set(str(ner_types).split("|"))
        ner_model = dynamic_init(class_filepath=provider_path(_opt(options, "ner_provider")))

        translate_provider = provider_path(_opt(options, "translate_provider"))
        translate_text = _opt(options, "translate_text")
        translator_args = None
        if translate_provider and translate_text and ":" in str(translate_text):
            src, dest = str(translate_text).split(":", 1)
            translator_args = {
                "model": dynamic_init(class_filepath=translate_provider)(),
                "src": src,
                "dest": dest,
            }

        collection_target_func = lambda data_type: join(
            output_dir, "-".join([collection_name, data_type.name.lower()]))

        def named_rows():
            for index, row in enumerate(iter_rows_from_files(
                    files_iter=[filepath],
                    csv_sep=_opt(options, "csv_sep", ","),
                    csv_column=_opt(options, "csv_column", "text"))):
                row["id"] = ":".join([collection_name, str(index)])
                yield row

        pipeline, settings = create_inference_pipeline(
            rows_iter=named_rows(),
            sampling_args={
                "sentence_parser": _opt(options, "sentence_parser", "nltk:english"),
                "terms_per_context": _opt_int(options, "terms_per_context", 50),
                "docs_limit": _opt_int(options, "docs_limit", None),
                "synonyms_filepath": _opt(options, "synonyms_filepath"),
            },
            predict_table_name=PREDICT_TABLE,
            collection_target_func=collection_target_func,
            translator_args=translator_args,
            ner_args={
                "model": ner_model(model=_opt(options, "ner_model_name")),
                "obj_filter": None if ner_type_set is None else (
                    lambda s_obj, accepted=ner_type_set: s_obj.ObjectType in accepted),
                "chunk_limit": 128,
            },
            inference_args={
                "model": _opt(options, "inference_model_name"),
                "class_name": provider_path(_opt(options, "inference_filename")),
                "api_key": inference_api_key(options),
                "writer": _opt(options, "inference_writer", "sqlite3"),
                "task_kwargs": {
                    "schema": _ATTITUDE["schema"],
                    "classify_func": _classify_attitude,
                    "labels_fmt": _ATTITUDE["labels_fmt"],
                },
            },
            tqdm_log_out=TqdmToLogger(logger),
            batch_size=_opt_int(options, "batch_size", 1),
        )
        pipeline += [
            D3jsGraphsBackendPipelineItem(graph_min_links=1, weights=True),
            D3jsGraphOperationsBackendPipelineItem(),
        ]

        label_names = consts["d3js_label_names"]
        label_fmt = {a: v for a, v in map(lambda item: item.split(":"), label_names.split(","))}
        settings.append({
            "labels_formatter": CustomLabelsFormatter(**label_fmt),
            "d3js_collection_name": collection_name,
            "d3js_collection_description": collection_name,
            "d3js_graph_output_dir": output_dir,
        })

        report("Sampling and inference")
        BasePipelineLauncher.run(
            pipeline=pipeline,
            pipeline_ctx=PipelineResult(merge_dictionaries(settings)),
            has_input=False)
        report("Graphs saved for {0}".format(collection_name))
        __update_data_status__(collection_name, "completed")
        return collection_name
    except Exception as exc:
        stem, _ = stored_upload_name(filepath)
        try:
            __update_data_status__(stem, f"error: {exc}")
        except Exception:
            logging.getLogger("arelight").exception("Failed to record inference error")
        raise


def _load_graph_response(folder, file_name):
    if not file_name:
        return None
    path = join(folder, basename(file_name) + ".json")
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    with open(path, "r") as handle:
        return json.load(handle)


@app.api_route("/file_status", methods=["GET", "POST"])
async def get_file_status(request: Request, file: str = None):
    file = file or request.query_params.get("file")
    if not file:
        return JSONResponse({"error": "Key is missing"}, status_code=400)
    try:
        return {"data": __get_data_status__(file)}
    except KeyError:
        return JSONResponse({"error": "File not found"}, status_code=404)


@app.api_route("/available_files", methods=["GET", "POST"])
async def get_all_file_names():
    return list(map(basename, get_all_data_status().keys()))


_GRAPH_LAYOUTS = {
    "force": "path_to_force_data",
    "radial": "path_to_radial_data",
}

_GRAPH_MISSING = {
    "force": {"graph": {"nodes": [{"id": "DATASET NOT EXIST", "c": 1}], "links": []}},
    "radial": [{"w": 0.5, "imports": [], "name": "DATASET NOT EXIST"}],
}


@app.api_route("/get_graph_data", methods=["GET", "POST"])
async def get_graph_data(request: Request, file: str = None, layout: str = None):
    file_name = file or request.query_params.get("file")
    layout = layout or request.query_params.get("layout")
    if request.method == "POST":
        payload = await request.json()
        file_name = payload.get("file", file_name)
        layout = payload.get("layout", layout)
    folder_key = _GRAPH_LAYOUTS.get(layout)
    if folder_key is None:
        return JSONResponse({"error": "Unknown layout"}, status_code=400)
    loaded = _load_graph_response(SETTINGS[folder_key], file_name)
    if isinstance(loaded, JSONResponse):
        return loaded
    if loaded is None:
        return _GRAPH_MISSING[layout]
    if request.method == "POST":
        return {"graph": loaded}
    return loaded


@app.post("/details")
async def get_details(request: Request):
    data = await request.json()
    links = data.get("links") or []
    basis = data.get("basis") or []
    results = []
    for filename in basis:
        conditions = []
        for link in links:
            conditions.append({
                "s_type": link["source"]["id"].split(".")[0],
                "s_val": link["source"]["id"].split(".")[1],
                "t_type": link["target"]["id"].split(".")[0],
                "t_val": link["target"]["id"].split(".")[1],
                "label": link["sent"],
                "filename": filename,
            })

        sqlite_path = join(_output_dir(), filename + "-test.sqlite")
        if not os.path.exists(sqlite_path):
            continue

        def filter_records(record, expected=conditions):
            for condition in expected:
                matched = True
                for key, value in condition.items():
                    actual = record[key]
                    if key == "filename":
                        actual = basename(actual)
                    if value != actual:
                        matched = False
                        break
                if matched:
                    return True
            return False

        data_it = AREkitSamplesService.iter_samples_and_predict_sqlite3(
            sqlite_filepath=join(_output_dir(), filename + "-test"),
            samples_table_name="contents",
            predict_table_name=PREDICT_TABLE,
            filter_record_func=filter_records)
        results.extend(list(data_it))
    return {"results": results}


def _run_posted_operation(payload):
    operation = payload["operation"]
    op_name = operation["O"]
    if op_name not in (OP_UNION, OP_INTERSECTION, OP_DIFFERENCE):
        return JSONResponse({"error": "Unknown operation"}, status_code=400)
    if not operation.get("A") or not operation.get("B"):
        return JSONResponse({"error": "Select datasets A and B"}, status_code=400)

    a_names = [basename(name) for name in operation["A"]]
    b_names = [basename(name) for name in operation["B"]]
    requested = (operation.get("D") or "").replace(" ", "").replace("[OPERATION]", "").replace(".json", "")
    if requested:
        new_name = requested
    else:
        new_name = "__".join(["+".join(a_names), op_name, "+".join(b_names)])

    path_a = _combine_graphs(a_names, "temporary_A")
    path_b = _combine_graphs(b_names, "temporary_B")
    description = "___".join(["+".join(a_names), op_name, "+".join(b_names)])
    run_operation(path_a, path_b, op_name, new_name, description)
    __set_data_status__(new_name, {"data_status": "completed", "operation": op_name})
    return {"status": "completed", "name": new_name}


async def _read_import(form):
    upload = form.get("file")
    pasted = form.get("text")
    pasted = pasted.strip() if isinstance(pasted, str) else ""
    options = {
        key: form.get(key)
        for key in form.keys()
        if key not in ("file", "text", "dataset_name")
    }
    has_file = upload is not None and getattr(upload, "filename", None)
    if has_file:
        stem, stored = stored_upload_name(upload.filename)
        file_path = join(SETTINGS["path_to_raw_data"], stored)
        payload = await upload.read()
        with open(file_path, "wb") as handle:
            handle.write(payload)
        return file_path, stem, options
    if pasted:
        raw_name = form.get("dataset_name") or "example"
        stem = "".join(ch for ch in str(raw_name) if ch.isalnum() or ch in "-_[]") or "example"
        file_path = join(SETTINGS["path_to_raw_data"], stem + ".txt")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(pasted)
        return file_path, stem, options
    return None


@app.post("/stream-with-post")
async def stream_with_post(request: Request):
    """ Stream progress while `run_inference` handles the import form. """
    form = await request.form()
    prepared = await _read_import(form)
    if prepared is None:
        return StreamingResponse(
            iter([_sse("error", {"status": "error", "error": "Write text or attach a file."})]),
            media_type="text/event-stream")

    file_path, stem, options = prepared
    stored = dict(options)
    if "inference_api" in stored:
        stored["inference_api"] = "API_TOKEN" if inference_api_key(options) else ""
    __set_data_status__(stem, {**stored, "data_status": "processing"})

    async def events():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def progress(message):
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", {"message": message}))

        async def work():
            try:
                name = await asyncio.to_thread(run_inference, file_path, options, progress)
                collection = name if isinstance(name, str) and name else stem
                await queue.put(("completed", {"status": "completed", "collection": collection}))
            except Exception as exc:
                await queue.put(("error", {"status": "error", "error": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(work())
        while True:
            item = await queue.get()
            if item is None:
                break
            kind, payload = item
            yield _sse(kind, payload)
        await task

    return StreamingResponse(events(), media_type="text/event-stream")


@app.api_route("/", methods=["GET", "POST"])
async def upload_file(request: Request):
    if request.method == "POST" and "application/json" in request.headers.get("content-type", ""):
        try:
            return _run_posted_operation(await request.json())
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    return HTMLResponse(__get_html_template__())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(SETTINGS["port"]))
