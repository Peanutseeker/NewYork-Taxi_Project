"""Four-step beam-search strategy."""

from importlib import import_module

recommend = import_module("3_extension_task.planning_core").recommend_beam
