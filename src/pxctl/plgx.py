"""Reading the metadata a slicer writes into a .plgx task file.

A task file starts with comment lines carrying the slicer's parameters. The
printer identifies a task by the GUID on the ;TID: line -- the upload must be
named after it, or the firmware will not pick the task up.
"""

import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional

# Only the opening comment block is metadata; scanning further would wade
# through megabytes of toolpath. The header runs to ~12 KB on a real file --
# most of it an embedded preview image -- so this leaves generous room.
_HEADER_SCAN_BYTES = 65536

_TID_PATTERN = re.compile(rb"^;TID:\s*([0-9a-fA-F-]{36})\s*$", re.MULTILINE)
_LAYER_COUNT_PATTERN = re.compile(rb"^;LAYER_COUNT:\s*(\d+)\s*$", re.MULTILINE)


@dataclass
class TaskFile:
    """A .plgx file ready to be uploaded."""

    payload: bytes
    task_id: str
    layer_count: Optional[int] = None

    source_name: str = ""
    """Base name of the file it was read from, used as the default task name."""

    @property
    def default_name(self) -> str:
        """Task name to register under when the caller does not supply one."""
        return self.source_name or self.task_id

    @property
    def upload_name(self) -> str:
        """The name the file must be uploaded under."""
        return f"{self.task_id}.plgx"


def read_task_file(path: str, task_id: Optional[str] = None) -> TaskFile:
    """Loads a .plgx file and works out the GUID to upload it under.

    A file sliced by PolygonX already carries a ;TID: line, which is reused so
    re-uploading replaces the same task rather than creating a duplicate. When
    the header has no GUID, `task_id` is used, or a fresh one is generated.
    """
    with open(path, "rb") as handle:
        payload = handle.read()

    header = payload[:_HEADER_SCAN_BYTES]

    if task_id is None:
        match = _TID_PATTERN.search(header)
        task_id = match.group(1).decode("ascii") if match else str(uuid.uuid4())

    layer_match = _LAYER_COUNT_PATTERN.search(header)
    layer_count = int(layer_match.group(1)) if layer_match else None

    return TaskFile(
        payload=payload,
        task_id=task_id,
        layer_count=layer_count,
        source_name=os.path.splitext(os.path.basename(path))[0],
    )
