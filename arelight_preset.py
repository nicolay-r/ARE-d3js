from os.path import dirname, join, realpath


PROVIDERS_DIR = join(dirname(realpath(__file__)), "demo", "providers")

CONSTANT_INFER_PARAMS = {
    "sampling_framework": "arekit",
    "inference_framework": "bulk_chain",
    "collection_name": None,
    "backend": "d3js_graphs",
    "output_template": "output",
    "labels_fmt": "u:0,p:1,n:2",
    "d3js_label_names": "p:pos,n:neg,u:neu",
}

CONSTANT_INFER_IGNORE_PARAMS = {"from_files", "device_type", "log_file"}

UI_INFER_PRESETS = {
    "russian": {
        "sentence_parser": "nltk:russian",
        "terms_per_context": 50,
        "batch_size": 1,
        "ner_provider": join(PROVIDERS_DIR, "dp_130.py"),
        "ner_model_name": "ner_ontonotes_bert_mult",
        "ner_types": "ORG|PERSON|LOC|GPE",
        "translate_provider": join(PROVIDERS_DIR, "gt_402.py"),
        "translate_text": "auto:ru",
        "inference_filename": join(PROVIDERS_DIR, "replicate_104.py"),
        "inference_model_name": "meta/meta-llama-3-70b-instruct",
        "inference_writer": "sqlite3",
        "csv_sep": ",",
        "csv_column": "text",
    }
}
