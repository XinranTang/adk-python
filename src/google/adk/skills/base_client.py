"""Base class for skill clients."""

import abc
from typing import Dict, Optional

from google.genai import types
from . import models
from . import scripts


class BaseClient(abc.ABC):
  """Abstract base class for skill clients."""

  ##############################################################################
  # Commonly used public APIs
  ##############################################################################

  @abc.abstractmethod
  def list(self, source: Optional[str] = None) -> Dict[str, models.Frontmatter]:
    """Lists available skills.

    Retrieves all Skills available to the workspace, including both pre-built
    and custom Skills. Supports filtering by source.

    Args:
      source: The source to filter by (e.g., 'custom').

    Returns:
      A dictionary mapping skill path or ID to the skill's frontmatter.
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
  # File System Compatibility
  #
  # These methods adapt various clients to be compatible with a file system
  # abstraction, reducing divergence from how skills operate in open source.
  ##############################################################################

  @property
  @abc.abstractmethod
  def workspace(self) -> str:
    """Returns the workspace path of the skills."""
    raise NotImplementedError

  @abc.abstractmethod
  def location(self, skill_id: str) -> Optional[str]:
    """Returns the location of the skill definition file (SKILL.md).

    Args:
      skill_id: The unique path (name or id) of the skill.
    """
    raise NotImplementedError

  ##############################################################################
  # Optional utilities methods for a more versatile skill client.
  ##############################################################################
  def execute(
      self,
      skill_id: str,
      function_call: types.FunctionCall,
  ) -> types.FunctionResponse:
    """Executes a script defined in a skill.

    Note: This implementation only supports `models.FunctionScript` which wraps
    a python callable. It does not support executing arbitrary source code
    (e.g. `models.Script` with raw string content) for security reasons.
    Users are strongly recommended to override this method to support more
    complex execution environments (e.g., sandboxed execution of arbitrary code)
    or to integrate with specific runtime requirements.

    Args:
      skill_id: The unique name or id of the skill.
      function_call: The function call to execute.

    Returns:
      The response from the function execution.
    """
    skill = self.retrieve(skill_id)
    script_id = function_call.name
    script = skill.resources.get_script(script_id)

    if script is None:
      raise ValueError(
          f"Script '{script_id}' for function '{function_call.name}' not"
          f" found in skill '{skill_id}'"
      )

    if not isinstance(script, scripts.FunctionScript):
      raise ValueError(
          f"Script '{script_id}' is of type '{type(script).__name__}', which"
          f" is not supported by {self.__class__.__name__}. Only"
          " 'FunctionScript' is supported."
      )

    result = script.func(**function_call.args)
    return types.FunctionResponse(
        call_id=function_call.id,
        name=function_call.name,
        content={"result": result},
    )


