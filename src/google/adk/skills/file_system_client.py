"""FileSystemClient implementation."""

import pathlib
from typing import Any, Dict, Optional

from typing_extensions import override

from . import base_client
from . import file_loader
from . import models


_SKILL_MD = "SKILL.md"


class FileSystemClient(base_client.BaseClient):
  """Loads skills from a local directory."""

  def __init__(self, skills_base_path: str):
    self._skills_base_path = pathlib.Path(skills_base_path)

  @property
  @override
  def workspace(self) -> str:
    return str(self._skills_base_path)

  @override
  def list(self, source: Optional[str] = None) -> Dict[str, models.Frontmatter]:
    if not self._skills_base_path.is_dir():
      # Return empty list if directory doesn't exist.
      return {}

    skills = {}
    # Find all manifest files in immediate subdirectories.
    for manifest_path in sorted(self._skills_base_path.glob(f"*/{_SKILL_MD}")):
      content = file_loader.read_file(manifest_path)
      if content is None:
        continue
      frontmatter, _ = file_loader.parse_skill_md(content)
      if frontmatter:
        skills[manifest_path.parent.name] = frontmatter
    return skills

  @override
  def create(self, skill: models.Skill) -> models.Skill:
    raise NotImplementedError

  @override
  def delete(self, skill_id: str, version: Optional[str] = None) -> None:
    raise NotImplementedError

  @override
  def disable(self, skill_id: str) -> None:
    raise NotImplementedError

  @override
  def enable(self, skill_id: str) -> None:
    raise NotImplementedError

  @override
  def retrieve(self, skill_id: str) -> models.Skill:
    skill_path = self._skills_base_path / skill_id
    return file_loader.load_skill(skill_path)

  @override
  def location(self, skill_id: str) -> Optional[str]:
    """Find the SKILL.md file in a skill directory.

    Prefers SKILL.md (uppercase) but accepts skill.md (lowercase).

    Args:
      skill_id: The ID of the skill.
    """
    skill_dir = self._skills_base_path / skill_id
    path = file_loader.find_skill_md(skill_dir)
    return str(path) if path else None



