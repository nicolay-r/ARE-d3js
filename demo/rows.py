from arelight.run.utils import iter_content


def iter_rows_from_files(files_iter, csv_sep=",", csv_column="text", content_iter=None):

    def _default_content(filepath):
        return iter_content(filepath=filepath, csv_column=csv_column, csv_delimiter=csv_sep)

    read_content = content_iter if content_iter is not None else _default_content
    for filepath in files_iter or []:
        for index, content in enumerate(read_content(filepath)):
            yield {"id": ":".join([str(filepath), str(index)]), "text": content, "filename": filepath}
