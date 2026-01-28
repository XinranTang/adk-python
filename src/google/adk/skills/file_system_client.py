"""FileSystemClient implementation."""

import pathlib
from typing import Any, List, Optional

from typing_extensions import override

from . import base_client
from . import file_loader
from . import models


class FileSystemClient(base_client.BaseClient):
  """Skill client that loads skills from the local file system."""

  def __init__(self, skills_base_path: str):
    """Initializes the FileSystemClient.

    Args:
      skills_base_path: The base path where skills are stored.
    """
    self._base_path = pathlib.Path(skills_base_path).expanduser().resolve()

  @override
  def list(self, source: Optional[str] = None) -> List[models.Frontmatter]:
    """Lists available skills from the file system."""
    skills = []
    if not self._base_path.exists():
      return []

    for item in self._base_path.iterdir():
      if item.is_dir():
        try:
          frontmatter, _ = file_loader.load_skill_md(item)
          skills.append(frontmatter)
        except ValueError:
          # Skip invalid skills or directories not containing SKILL.md
          continue
    return skills

  @override
  def create(self, skill: models.Skill) -> models.Skill:
    """Creates a new skill."""
    raise NotImplementedError("Creating skills is not supported yet.")

  @override
  def delete(self, skill_id: str, version: Optional[str] = None) -> None:
    """Deletes a skill."""
    raise NotImplementedError("Deleting skills is not supported yet.")

  @override
  def retrieve(self, skill_id: str) -> models.Skill:
    """Retrieves a specific skill by its ID (directory name)."""
    # Assuming skill_id matches directory name for now
    skill_dir = self._base_path / skill_id
    if not skill_dir.exists():
      raise ValueError(f"Skill '{skill_id}' not found at {skill_dir}")

    try:
      return file_loader.load_skill(skill_dir)
    except (FileNotFoundError, ValueError) as e:
      raise ValueError(f"Failed to load skill '{skill_id}': {e}") from e

  @override
  def enable(self, skill_id: str) -> None:
    """Enables a skill."""
    pass

  @override
  def disable(self, skill_id: str) -> None:
    """Disables a skill."""
    pass

  @override
  def execute(
      self,
      skill_id: str,
      function_call: Any,
  ) -> Any:
    """Executes a script defined in a skill."""
    raise NotImplementedError("Script execution is not supported yet.")
