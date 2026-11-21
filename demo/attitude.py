def class_to_int(text):
    lowered = "" if text is None else str(text).lower()
    if "positive" in lowered:
        return 1
    if "negative" in lowered:
        return -1
    return 0


def attitude_task_kwargs(labels_fmt, classify_func=None):
    """ Prompt and label mapping used by the attitude-classification pipeline. """
    from arekit.common.data.input.providers.text.single import BaseSingleTextProvider

    prompt = (
        f"Given text: {{{BaseSingleTextProvider.TEXT_A}}}"
        "TASK: Classify sentiment attitude of [SUBJECT] to [OBJECT]: "
        "positive, "
        "negative, "
        "neutral."
    )
    return {
        "schema": [{"prompt": prompt, "out": "response"}],
        "classify_func": class_to_int if classify_func is None else classify_func,
        "labels_fmt": labels_fmt,
    }
