from pathlib import Path
from PySide6.QtCore import QStandardPaths


def default_path():
    documents=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if not documents: raise OSError('Windows не предоставила путь к папке «Документы».')
    return Path(documents)/'LisaMacroMagic'/'settings.json'
