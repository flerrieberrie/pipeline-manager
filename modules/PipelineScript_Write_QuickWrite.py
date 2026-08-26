#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_Write_QuickWrite.py
Author: Florian Dheer
Description: Create a new dated document in the Sandbox Write folder and open
it in LibreOffice Writer - capture a quick idea with zero setup.
"""

import os
import sys
import datetime
import subprocess

from shared_logging import get_logger, setup_logging as setup_shared_logging
from rak_settings import get_rak_settings
from workstation_apps import load_apps, resolve_exe_path

logger = get_logger("write_quick_write")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

# Minimal valid empty RTF - LibreOffice Writer opens it directly, no
# ODF/zip machinery needed just to get a blank page on disk.
BLANK_RTF = r"{\rtf1\ansi\deff0}"


def main() -> int:
    setup_shared_logging("write_quick_write")
    settings = get_rak_settings()
    # os.path.join mishandles a bare drive letter ("I:" + "x" -> "I:x", no
    # separator) - build the absolute path with an explicit backslash instead,
    # matching rak_settings.get_work_path()'s own f"{drive}\\{subpath}" pattern.
    write_dir = f"{settings.get_work_drive()}\\_Sandbox\\Write"
    os.makedirs(write_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    file_path = os.path.join(write_dir, f"{timestamp}.rtf")
    with open(file_path, "w", encoding="ascii") as f:
        f.write(BLANK_RTF)
    logger.info(f"Created quick-write file: {file_path}")

    app = next((a for a in load_apps() if a.name == "LibreOffice"), None)
    exe = resolve_exe_path(app) if app else None
    if not exe:
        print(f"Created {file_path} - LibreOffice wasn't found, "
              "opening with the default app instead.", file=sys.stderr)
        os.startfile(file_path)
        return 0

    subprocess.Popen([exe, file_path], creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                      close_fds=True)
    print(f"Opened {file_path} in LibreOffice Writer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
