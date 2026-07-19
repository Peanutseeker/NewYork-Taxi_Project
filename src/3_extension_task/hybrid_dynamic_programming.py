"""Baseline-utility strategy with a conservative three-step value bonus."""

from importlib import import_module

recommend = import_module("3_extension_task.planning_core").recommend_hybrid
