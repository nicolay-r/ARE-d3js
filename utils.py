import os
from os.path import dirname, realpath

from argparse_to_json import convert_parser_to_json


CUR_DIR = dirname(realpath(__file__))


def do_format(entry, is_check=False):
    assert (isinstance(entry, dict))

    list_type = "check" if is_check else "list"

    if "enum" in entry:
        r = {list_type: entry["enum"]}
    elif entry["type"] == "string":
        r = {list_type: [entry["default"]]}
    elif entry["type"] == "integer":
        r = {"field": entry["default"]}
    else:
        r = None
    return r


def extract(parser, args=None):
    values = vars(parser.parse_args([] if args is None else args))
    json_data = convert_parser_to_json(parser)
    for k, v in values.items():
        json_data["schema"][k]["default"] = v
    return json_data


def setup_preset(predefined_args, preset, ignored_params):
    """ Assigning predefined settings.
    """
    for p, v in preset.items():
        if p in ignored_params or p not in predefined_args:
            continue
        target = predefined_args[p]
        if "list" in target:
            options = target["list"]
            if v in options:
                options.remove(v)
            options.insert(0, v)
        if "field" in target:
            target["field"] = v


def iter_last_n_lines(filepath, n):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", errors="replace") as handle:
        lines = handle.readlines()
    for line in lines[-n:]:
        yield line.rstrip("\n")
