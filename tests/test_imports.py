"""Test that all modules can be imported successfully.

This test catches import errors early before they cause runtime failures.
"""
import pytest
import importlib
import pkgutil
import sys
from pathlib import Path


def get_all_modules():
    """Get all Python modules in the src directory."""
    src_path = Path(__file__).parent.parent / "src"

    modules = []
    for root, dirs, files in src_path.walk():
        # Skip __pycache__ and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('_') and not d.startswith('.')]

        for file in files:
            if file.endswith('.py') and not file.startswith('_'):
                # Convert file path to module name
                rel_path = (root / file).relative_to(src_path.parent)
                module_name = str(rel_path.with_suffix('')).replace('/', '.')
                modules.append(module_name)

    return sorted(modules)


@pytest.mark.parametrize("module_name", get_all_modules())
def test_module_imports(module_name):
    """Test that each module can be imported without errors."""
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        pytest.fail(f"Failed to import {module_name}: {e}")


def test_all_agent_modules_importable():
    """Test that all agent modules can be imported."""
    # Core modules that should always be importable
    core_modules = [
        'src.agent.config',
        'src.agent.main',
        'src.agent.trading_agent',
        'src.agent.scanner.main_loop',
        'src.agent.scanner.risk_validator',
        'src.agent.paper_trading.portfolio_manager',
        'src.agent.paper_trading.execution_engine',
        'src.agent.tools.technical_analysis',
        'src.agent.tools.signals',
    ]

    for module_name in core_modules:
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import core module {module_name}: {e}")
