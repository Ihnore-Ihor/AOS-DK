"""Minimal stdio MCP server that bridges Claude to Unreal Engine 5.7 Remote Control HTTP.

Environment variables (optional):
  UE_REMOTE_CONTROL_URL  base URL of the Remote Control HTTP API (default http://127.0.0.1:30010/remote)
  UE_RC_TIMEOUT          request timeout in seconds (default 15)
  UE_DEFAULT_WORLD       world object path used as WorldContextObject for console commands
"""

import json
import os
import subprocess
import tempfile
import threading
import time
import uuid

import requests
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("UE_REMOTE_CONTROL_URL", "http://127.0.0.1:30010/remote").rstrip("/")
TIMEOUT = float(os.environ.get("UE_RC_TIMEOUT", "300"))
DEFAULT_WORLD = os.environ.get(
    "UE_DEFAULT_WORLD", "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson.Lvl_FirstPerson"
)
OFFLINE_MESSAGE = "Unreal Editor offline on port 30010"

UE_EDITOR_EXE = os.environ.get(
    "UE_EDITOR_EXE",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe",
)
UE_PROJECT = os.environ.get(
    "UE_PROJECT",
    r"C:\Users\USER\Documents\Unreal Projects\AOS_DK\AOS_DK.uproject",
)

KISMET_LIB = "/Script/Engine.Default__KismetSystemLibrary"
EDITOR_ACTOR_SUBSYSTEM = "/Script/UnrealEd.Default__EditorActorSubsystem"

mcp = FastMCP("unreal-remote-control")


def _request(method: str, path: str, body: dict | None = None) -> dict:
    """Send one Remote Control request. Never raises; always returns a dict."""
    try:
        resp = requests.request(method, BASE_URL + path, json=body, timeout=TIMEOUT)
    except requests.ConnectionError:
        return {"ok": False, "error": OFFLINE_MESSAGE}
    except requests.Timeout:
        return {"ok": False, "error": f"Unreal Editor did not answer within {TIMEOUT:g}s (port 30010)"}
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Remote Control request failed: {exc}"}

    try:
        data = resp.json() if resp.content else {}
    except ValueError:
        data = {"raw": resp.text}

    if resp.status_code >= 400:
        return {"ok": False, "status": resp.status_code, "error": data}
    return {"ok": True, "status": resp.status_code, "data": data}


def _call_function(object_path: str, function_name: str, parameters: dict | None = None) -> dict:
    body = {
        "objectPath": object_path,
        "functionName": function_name,
        "parameters": parameters or {},
        "generateTransaction": False,
    }
    return _request("PUT", "/object/call", body)


@mcp.tool()
def editor_status() -> dict:
    """Check whether the Unreal Editor Remote Control server is reachable."""
    return _request("GET", "/info")


@mcp.tool()
def launch_editor() -> dict:
    """Start Unreal Editor 5.7 with AOS_DK and the Remote Control web server (non-blocking).

    Returns immediately; poll editor_status until it reports ok, then call get_actors.
    """
    if not os.path.isfile(UE_EDITOR_EXE):
        return {"ok": False, "error": f"Editor not found: {UE_EDITOR_EXE}"}
    if not os.path.isfile(UE_PROJECT):
        return {"ok": False, "error": f"Project not found: {UE_PROJECT}"}

    args = [UE_EDITOR_EXE, UE_PROJECT, '-ExecCmds=WebControl.StartServer']
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        proc = subprocess.Popen(args, creationflags=flags, close_fds=True)
    except OSError as exc:
        return {"ok": False, "error": f"Failed to start editor: {exc}"}
    return {"ok": True, "status": "Unreal Engine 5.7 launching...", "pid": proc.pid}


@mcp.tool()
def close_editor(force: bool = False) -> dict:
    """Close Unreal Editor (graceful by default: WM_CLOSE, so unsaved-changes prompts still appear).

    force=True kills the process without prompts; use only when graceful close hangs.
    """
    cmd = ["taskkill", "/IM", "UnrealEditor.exe"]
    if force:
        cmd.append("/F")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"taskkill failed: {exc}"}
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return {"ok": False, "error": output or f"taskkill exit code {result.returncode}"}
    return {"ok": True, "status": "Unreal Editor closing...", "output": output}


PYTHON_LIBRARY = "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"
PYTHON_RESULT_DIR = os.environ.get("UE_MCP_RESULT_DIR", tempfile.gettempdir())
PYTHON_TIMEOUT = float(os.environ.get("UE_MCP_PYTHON_TIMEOUT", "300"))


def _wrap_python(code: str, result_file: str) -> str:
    """Wrap user code so its `result` variable (JSON-serializable) or traceback is written to result_file."""
    return f"""
import json, traceback
__mcp_out = {{}}
try:
    __mcp_ns = {{}}
    exec(compile({code!r}, '<mcp>', 'exec'), __mcp_ns)
    __mcp_out = {{"ok": True, "result": __mcp_ns.get("result")}}
except Exception:
    __mcp_out = {{"ok": False, "error": traceback.format_exc()}}
with open({result_file!r}, "w", encoding="utf-8") as __mcp_f:
    __mcp_f.write(json.dumps(__mcp_out, default=str))
"""


@mcp.tool()
def execute_python(code: str) -> dict:
    """Run Python inside the Unreal Editor (in-engine `unreal` module). Full editor access.

    The code runs as a script. Assign a JSON-serializable value to `result` to return it.
    Example: 'import unreal\\nactors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()\\nresult = [a.get_name() for a in actors][:5]'
    Errors return the traceback in `error`.
    """
    token = uuid.uuid4().hex
    result_file = os.path.join(PYTHON_RESULT_DIR, f"ue_mcp_{token}.json")
    wrapped = _wrap_python(code, result_file)
    call = _call_function(PYTHON_LIBRARY, "ExecutePythonScript", {"PythonScript": wrapped})
    if not call.get("ok"):
        return call

    deadline = time.monotonic() + PYTHON_TIMEOUT
    while time.monotonic() < deadline:
        if os.path.exists(result_file):
            try:
                with open(result_file, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                pass
            finally:
                try:
                    os.remove(result_file)
                except OSError:
                    pass
        time.sleep(0.2)
    return {"ok": False, "error": f"No result from Unreal Python within {PYTHON_TIMEOUT:g}s"}


@mcp.tool()
def execute_console_command(command: str, world_path: str = DEFAULT_WORLD) -> dict:
    """Run an Unreal console command (for example, open a level or run a stat command).

    world_path is the WorldContextObject used to resolve the world; it defaults to LvL_FirstPerson.
    """
    return _call_function(
        KISMET_LIB,
        "ExecuteConsoleCommand",
        {"WorldContextObject": world_path, "Command": command},
    )


@mcp.tool()
def get_actors() -> dict:
    """List all actors in the currently loaded level (editor world)."""
    return _call_function(EDITOR_ACTOR_SUBSYSTEM, "GetAllLevelActors")


@mcp.tool()
def search_assets(query: str, class_name: str = "") -> dict:
    """Search project assets by name, optionally filtered by class (for example StaticMesh)."""
    body = {
        "Query": query,
        "Filter": {
            "ClassNames": [class_name] if class_name else [],
            "PackagePaths": [],
        },
    }
    return _request("PUT", "/search/assets", body)


@mcp.tool()
def get_property(object_path: str, property_name: str) -> dict:
    """Read a property of an actor or object by its full object path."""
    body = {
        "objectPath": object_path,
        "propertyName": property_name,
        "access": "READ_ACCESS",
    }
    return _request("PUT", "/object/property", body)


@mcp.tool()
def set_property(object_path: str, property_name: str, value: object) -> dict:
    """Write a property of an actor or object by its full object path.

    value must be JSON-compatible and match the property type (for example {"X": 0, "Y": 0, "Z": 100} for a vector).
    """
    body = {
        "objectPath": object_path,
        "propertyName": property_name,
        "access": "WRITE_TRANSACTION_ACCESS",
        "propertyValue": {property_name: value},
    }
    return _request("PUT", "/object/property", body)


# ---------------------------------------------------------------------------
# UBT build control (non-blocking)
# ---------------------------------------------------------------------------
UE_BUILD_BAT = os.environ.get(
    "UE_BUILD_BAT",
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat",
)
_PROJECT_DIR = os.path.dirname(UE_PROJECT)
BUILD_LOG = os.path.join(_PROJECT_DIR, "Saved", "MCP_Build.log")

_build_lock = threading.Lock()
_build: dict = {
    "proc": None,        # subprocess.Popen of the active/last build
    "log_handle": None,  # open log file handle for the active build
    "start": None,       # time.monotonic() at launch
    "end": None,         # time.monotonic() when finish was observed
    "cmd": None,
    "exit_code": None,
    "stopped": False,
}


def _editor_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe", "/NH"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "UnrealEditor.exe" in out


def _tail_log(lines: int = 40) -> str:
    try:
        with open(BUILD_LOG, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _refresh_build_state() -> bool:
    """Update bookkeeping from poll(); return True if a build is currently running."""
    proc = _build["proc"]
    if proc is None:
        return False
    code = proc.poll()
    if code is None:
        return True
    if _build["end"] is None:
        _build["end"] = time.monotonic()
        _build["exit_code"] = code
        handle = _build["log_handle"]
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
            _build["log_handle"] = None
    return False


@mcp.tool()
def start_build(
    target: str = "AOS_DKEditor",
    configuration: str = "Development",
    platform: str = "Win64",
    warnings_as_errors: bool = True,
    close_editor_first: bool = True,
) -> dict:
    """Start an Unreal Build Tool compile asynchronously (non-blocking).

    Closes UnrealEditor.exe first when close_editor_first is True (graceful; reports if it refuses to close).
    Output goes to Saved/MCP_Build.log; poll build_status, cancel with stop_build.
    """
    with _build_lock:
        if _refresh_build_state():
            return {"ok": False, "error": "A build is already running", "pid": _build["proc"].pid,
                    "elapsed_sec": round(time.monotonic() - _build["start"], 1)}
        if not os.path.isfile(UE_BUILD_BAT):
            return {"ok": False, "error": f"Build.bat not found: {UE_BUILD_BAT}"}
        if not os.path.isfile(UE_PROJECT):
            return {"ok": False, "error": f"Project not found: {UE_PROJECT}"}

        editor_was_running = _editor_running()
        if editor_was_running and close_editor_first:
            try:
                subprocess.run(["taskkill", "/IM", "UnrealEditor.exe"],
                               capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {"ok": False, "error": f"Failed to close editor: {exc}"}
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and _editor_running():
                time.sleep(1)
            if _editor_running():
                return {"ok": False, "editor_running": True,
                        "error": "Editor did not close within 60s (likely an unsaved-changes prompt). "
                                 "Save/dismiss it, or call close_editor(force=True), then retry."}
        elif editor_was_running:
            return {"ok": False, "editor_running": True,
                    "error": "UnrealEditor.exe is running; close it or pass close_editor_first=True."}

        cmd = [UE_BUILD_BAT, target, platform, configuration, f"-Project={UE_PROJECT}",
               "-WaitMutex", "-NoHotReload"]
        if warnings_as_errors:
            cmd.append("-WarningsAsErrors")

        env = os.environ.copy()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "core.quotepath"
        env["GIT_CONFIG_VALUE_0"] = "false"

        try:
            os.makedirs(os.path.dirname(BUILD_LOG), exist_ok=True)
            handle = open(BUILD_LOG, "wb")
        except OSError as exc:
            return {"ok": False, "error": f"Cannot open build log {BUILD_LOG}: {exc}"}

        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=env, cwd=_PROJECT_DIR, creationflags=flags)
        except OSError as exc:
            handle.close()
            return {"ok": False, "error": f"Failed to start UBT: {exc}"}

        _build.update(proc=proc, log_handle=handle, start=time.monotonic(), end=None,
                      cmd=cmd, exit_code=None, stopped=False)
        return {"ok": True, "status": "Build started", "pid": proc.pid, "log": BUILD_LOG,
                "editor_was_running": editor_was_running, "command": subprocess.list2cmdline(cmd)}


@mcp.tool()
def build_status() -> dict:
    """Report the active or last UBT build: running, exit_code, elapsed_sec and the last ~40 log lines."""
    with _build_lock:
        if _build["proc"] is None:
            return {"ok": True, "running": False, "exit_code": None, "elapsed_sec": 0,
                    "note": "No build started in this MCP session", "log_tail": _tail_log()}
        running = _refresh_build_state()
        end = time.monotonic() if running else _build["end"]
        return {
            "ok": True,
            "running": running,
            "exit_code": None if running else _build["exit_code"],
            "stopped": _build["stopped"],
            "pid": _build["proc"].pid,
            "elapsed_sec": round(end - _build["start"], 1),
            "log_tail": _tail_log(40),
        }


@mcp.tool()
def stop_build() -> dict:
    """Kill the active UBT build process tree (taskkill /PID <pid> /T /F)."""
    with _build_lock:
        proc = _build["proc"]
        if proc is None or not _refresh_build_state():
            return {"ok": False, "error": "No build is running"}
        pid = proc.pid
        try:
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                    capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": f"taskkill failed: {exc}"}
        _build["stopped"] = True
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        _refresh_build_state()
        return {"ok": result.returncode == 0, "pid": pid,
                "output": (result.stdout + result.stderr).strip()}


if __name__ == "__main__":
    mcp.run()
