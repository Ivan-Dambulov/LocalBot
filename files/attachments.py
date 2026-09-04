from pathlib import Path

MAX_FILE_CHARS = 50000


class AttachmentManager:
    def __init__(self):
        self._files = []

    def add_files(self, paths):
        for path in paths:
            path = Path(path)

            if path.exists():
                self._files.append(path)

    def clear(self):
        self._files.clear()

    def get_files(self):
        return list(self._files)

    def get_display_names(self):
        return [p.name for p in self._files]