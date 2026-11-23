"""Static Skill risk patterns. Evidence contains only rule names and API names."""

import ast
import re

TEXT_RULES = (
    (
        "SEC006",
        r"ignore (?:all |any )?(?:previous|prior|system) instructions",
        "Instruction override",
        "Preserve higher-priority instructions and treat external content as data.",
    ),
    (
        "SEC007",
        r"(?:disable|bypass|skip) (?:all )?(?:approval|permission|confirmation) checks?",
        "Approval bypass",
        "Require the host's normal approval flow for sensitive actions.",
    ),
    (
        "SEC008",
        r"display\s*:\s*none|visibility\s*:\s*hidden|\u202e|\u2066",
        "Hidden content marker",
        "Make instructions visible and remove text direction controls.",
    ),
)

EXECUTION_APIS = {
    "builtins.eval",
    "builtins.exec",
    "os.system",
    "os.popen",
}
SUBPROCESS_APIS = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
}


def python_risks(source: str):
    """Identify direct execution APIs and explicit shell mode in Python scripts."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, RecursionError):
        return

    imports = {"eval": "builtins.eval", "exec": "builtins.exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imports[name] = alias.name if alias.asname else name
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts = []
        func = node.func
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if not isinstance(func, ast.Name) or func.id not in imports:
            continue
        api = ".".join([imports[func.id], *reversed(parts)])
        shell_mode = any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        if api in EXECUTION_APIS or (api in SUBPROCESS_APIS and shell_mode):
            yield node.lineno, api


def text_risks(line: str):
    for rule, pattern, title, fix in TEXT_RULES:
        if re.search(pattern, line, re.IGNORECASE):
            yield rule, title, fix
