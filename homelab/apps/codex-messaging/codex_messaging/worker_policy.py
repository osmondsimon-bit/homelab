"""Define the worker's dynamic-tool-only surface without native environment authority."""


DISABLED_FEATURES = (
    "apps", "plugins", "remote_plugin", "hooks", "multi_agent", "goals",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use", "image_generation", "shell_tool", "shell_snapshot",
    "skill_search", "workspace_dependencies", "code_mode_host",
)


def feature_configuration() -> str:
    """Use only feature names confirmed by the pinned runtime's feature catalogue."""
    return "[features]\n" + "".join(f"{name} = false\n" for name in DISABLED_FEATURES)


def verify_features(table: str) -> None:
    """Check effective CLI output as well as the root-owned configuration file."""
    effective = {}
    for line in table.splitlines():
        columns = line.split()
        if len(columns) >= 3:
            if columns[0] in effective:
                raise ValueError("worker_features")
            effective[columns[0]] = columns[-1]
    if any(effective.get(name) != "false" for name in DISABLED_FEATURES):
        raise ValueError("worker_features")


def thread_parameters(workspace: str, tools: list[dict]) -> dict:
    """Disable local environment access even if a model invents a native tool call."""
    return {
        "cwd": workspace,
        "permissions": "messaging",
        "approvalPolicy": "never",
        "environments": [],
        "dynamicTools": tools,
    }
