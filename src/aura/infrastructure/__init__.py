"""Narrow interfaces for optional runtime infrastructure."""

from .desktop import DesktopActions
from .model_provider import ModelProvider
from .persistence import GraphRepository, JsonGraphRepository
from .project_repository import ProjectRepository, SQLiteProjectRepository
from .tools import ToolExecutor
from .voice import VoiceInteraction

__all__ = ["DesktopActions", "GraphRepository", "JsonGraphRepository", "ModelProvider",
           "ProjectRepository", "SQLiteProjectRepository", "ToolExecutor", "VoiceInteraction"]
