from app.tools.search_code import SearchCodeTool
from app.tools.test_runner import TestRunnerTool
from app.tools.patch_applier import PatchApplierTool
from app.tools.git_ops import GitOpsTool

TOOL_REGISTRY = {
    "search_code": SearchCodeTool,
    "run_tests": TestRunnerTool,
    "apply_patch": PatchApplierTool,
    "git_ops": GitOpsTool,
}

__all__ = ["TOOL_REGISTRY", "SearchCodeTool", "TestRunnerTool", "PatchApplierTool", "GitOpsTool"]
