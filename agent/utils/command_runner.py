from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


async def run_command(command: list[str], cwd: Path, timeout: int = 120) -> CommandResult:
    executable = command
    if os.name == "nt" and command[0] in {"npm", "npx"}:
        executable = ["cmd.exe", "/d", "/c", subprocess.list2cmdline(command)]

    process = await asyncio.create_subprocess_exec(
        *executable,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        return CommandResult(command, 124, stdout.decode(errors="replace"), stderr.decode(errors="replace"))

    return CommandResult(
        command,
        process.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )
