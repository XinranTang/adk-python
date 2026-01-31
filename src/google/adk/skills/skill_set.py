"""Module for managing agent skills."""

from typing import Dict, Optional

from typing_extensions import override

from . import base_client
from . import models


class Skills(base_client.BaseClient):
  """An in-memory dictionary mapping skill identifiers to skill objects.

  This class simply stores skill objects, exposing
  convenient methods like create, retrieve, list, and delete. It has no
  access to the file system or bash environments and only operates on
  skills held in memory.

  It also supports converting skills to a
  standard structured string with XML tags to be used in prompts.
  """

  def __init__(self):
    self._skills: Dict[str, models.Skill] = {}

  @property
  @override
  def workspace(self) -> str:
    """Returns the workspace path of the skills."""
    return "/memory"

  @override
  def list(self, source: Optional[str] = None) -> Dict[str, models.Frontmatter]:
    """Lists available skills."""
    return {name: skill.frontmatter for name, skill in self._skills.items()}

  @override
  def create(self, skill: models.Skill) -> models.Skill:
    """Creates a new skill."""
    self._skills[skill.name] = skill
    return skill

  @override
  def delete(self, skill_id: str, version: Optional[str] = None) -> None:
    """Deletes a skill.

    In this in-memory implementation, versioning is not enabled, so the
    `version` parameter is ignored.

    Args:
      skill_id: The ID of the skill to delete.
      version: The version of the skill to delete (ignored in this
        implementation).
    """
    if skill_id in self._skills:
      del self._skills[skill_id]

  @override
  def retrieve(self, skill_id: str) -> models.Skill:
    """Retrieves a specific skill."""
    if skill_id not in self._skills:
      raise ValueError(f"Skill '{skill_id}' not found")
    return self._skills[skill_id]

  @override
  def location(self, skill_id: str) -> Optional[str]:
    """Returns the location of the skill definition file (SKILL.md)."""
    return f"{self.workspace}/{skill_id}/SKILL.md"

  @override
  def enable(self, skill_id: str) -> None:
    """Enables a skill."""
    pass

  @override
  def disable(self, skill_id: str) -> None:
    """Disables a skill."""
    pass
