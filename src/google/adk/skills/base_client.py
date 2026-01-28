"""Base class for skill clients."""

import abc
from typing import List, Optional

from typing import Any

from . import models


# TODO: the use of skill name or id differs from companies. Harmonize.
class BaseClient(abc.ABC):
  """Abstract base class for skill clients."""

  ##############################################################################
  # Commonly used public APIs
  ##############################################################################

  @abc.abstractmethod
  def list(self, source: Optional[str] = None) -> List[models.Frontmatter]:
    """Lists available skills.

    Retrieves all Skills available to the workspace, including both pre-built
    and custom Skills. Supports filtering by source.

    Args:
      source: The source to filter by (e.g., 'custom').
    """
    raise NotImplementedError

  @abc.abstractmethod
  def create(self, skill: models.Skill) -> models.Skill:
    """Creates a new skill.

    Uploads a custom Skill to make it available in the workspace. Supports
    uploading via directory path, zip file, or file objects. Requires a
    SKILL.md file and common root directory.

    Args:
      skill: The skill to create.
    """
    raise NotImplementedError

  @abc.abstractmethod
  def delete(self, skill_id: str, version: Optional[str] = None) -> None:
    """Deletes a skill.

    Removes a Skill from the workspace. The behavior depends on the `version`
    parameter:

    *   If `version` is `None`:
        *   If no versioning is enabled, the skill is deleted.
        *   If versioning is enabled, all versions must be explicitly deleted
            before the skill can be removed.

    Args:
      skill_id: The unique name or id of the skill to delete.
      version: The version of the skill to delete.
    """
    raise NotImplementedError

  @abc.abstractmethod
  def retrieve(self, skill_id: str) -> models.Skill:
    """Retrieves a specific skill.

    Gets details about a specific Skill by name, including its display title,
    latest version, and creation date.

    Args:
      skill_id: The unique name or id of the skill to retrieve.
    """
    raise NotImplementedError

  # TODO: Implement versions API

  ##############################################################################
  # Gemini CLI compatibility
  ##############################################################################

  @abc.abstractmethod
  def enable(self, skill_id: str) -> None:
    """Enables a skill.

    Re-enables a previously disabled skill, making it available for use.

    Args:
      skill_id: The unique name or id of the skill to enable.
    """
    raise NotImplementedError

  @abc.abstractmethod
  def disable(self, skill_id: str) -> None:
    """Disables a skill.

    Prevents a specific skill from being used without deleting it.

    Args:
      skill_id: The unique name or id of the skill to disable.
    """
    raise NotImplementedError

  ##############################################################################
  # Optional utilities methods for a more versatile skill client.
  ##############################################################################
  @abc.abstractmethod
  def execute(
      self,
      skill_id: str,
      function_call: Any,
  ) -> Any:
    """Executes a script defined in a skill.

    Note: This is not a public API. It is supported for user-defined secure
    script execution, which does not strictly require a sandboxed environment.

    Args:
      skill_id: The unique name or id of the skill.
      function_call: The function call to execute.

    Returns:
      The response from the function execution.
    """
    raise NotImplementedError
