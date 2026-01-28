"""Tool for discovering, viewing, and executing agent skills.

This module defines the SkillTool class, which provides an interface for
interacting with a collection of agent skills. It allows listing available
skills, viewing their manifests, running scripts, and loading references
and assets associated with each skill.
"""

from typing import Any, Dict, Optional

from google.genai import types

from ..skills import BaseClient
from ..skills import Frontmatter
from .base_tool import BaseTool
from .tool_context import ToolContext


# TODO: can be simplified, a lot of this is about string/object conversion.
# TODO: prompt can be more simplified and structured too.

DEFAULT_SYSTEM_INSTRUCTION = """

You can use specialized 'skills' to help you with complex tasks. You MUST use the `manage_skills` tool to interact with these skills.

Skills are folders of instructions, scripts, and resources that extend your capabilities for specialized tasks. Each skill folder contains:
- **SKILL.md** (required): instructions + metadata
- **references/** (Optional): documentation
- **assets/** (Optional): templates, resources

This is very important:

1. If a skill seems relevant to the current user query, you MUST use the `manage_skills` tool with the `view_manifest` action to read its full instructions before proceeding.

2. Once you have read the instructions, follow them exactly as documented before replying to the user.

"""


def _frontmatter_to_dict(
    frontmatter: Frontmatter,
) -> dict[str, str | dict[str, str]]:
  """Convert to dictionary, excluding None values."""
  result = {"name": frontmatter.name, "description": frontmatter.description}
  if frontmatter.license is not None:
    result["license"] = frontmatter.license
  if frontmatter.compatibility is not None:
    result["compatibility"] = frontmatter.compatibility
  if frontmatter.allowed_tools is not None:
    result["allowed-tools"] = frontmatter.allowed_tools
  if frontmatter.metadata:
    result["metadata"] = frontmatter.metadata
  return result


class SkillTool(BaseTool):
  """A tool for discovering, viewing, and executing agent skills."""

  def __init__(
      self,
      client: BaseClient,
  ):
    super().__init__(
        # TODO: adjust description to promote function calling.
        # This relies on on the assumption there's a sandbox with python.
        # Ajdust it to target function calling   would be more effective.
        name="manage_skills",
        description=(
            """Discovers, views, and executes agent skills. When calling this tool, use the name 'manage_skills'.

            Examples:
            - List skills:
                `print(manage_skills(action="list"))`
            - View manifest:
                `print(manage_skills(action="view_manifest", skill_name="SKILL_NAME"))`
            - Load reference:
                `print(manage_skills(action="load_reference", skill_name="SKILL_NAME", reference_path="REF_PATH"))`
            - Load asset:
                `print(manage_skills(action="load_asset", skill_name="SKILL_NAME", asset_path="ASSET_PATH"))`

            """
        ),
    )
    self._client = client

  def __get_available_skills(self) -> str:
    lines = ["Available Skills:"]
    for skill in self._client.list():
      lines.append(f"- {skill.name}: {skill.description}")
    return "\n".join(lines)

  def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
    return types.FunctionDeclaration(
        name=self.name,
        description=self.description + self.__get_available_skills(),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "action": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The action to perform: list, view_manifest,"
                        # "run_script",  # TODO: Enable safe code execution.
                        " load_reference, load_asset"
                    ),
                    enum=[
                        "list",
                        "view_manifest",
                        # "run_script",  # TODO: Enable safe code execution.
                        "load_reference",
                        "load_asset",
                    ],
                ),
                "skill_name": types.Schema(
                    type=types.Type.STRING,
                    description="The name of the target skill directory.",
                ),
                "script_path": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Relative path to the script within the skill's"
                        " scripts/ directory (for run_script)."
                    ),
                ),
                "args": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description=(
                        "Arguments to pass to the script (for run_script)."
                    ),
                ),
                "reference_path": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Relative path to the document within the skill's"
                        " references/ directory (for load_reference)."
                    ),
                ),
                "asset_path": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Relative path to the file within the skill's"
                        " assets/ directory (for load_asset)."
                    ),
                ),
            },
            required=["action"],
        ),
    )

  async def run_async(
      self, *, args: Dict[str, Any], tool_context: ToolContext
  ) -> Any:
    action = args.get("action")
    valid_actions = [
        "list",
        "view_manifest",
        # "run_script",  # TODO: Enable safe code execution.
        "load_reference",
        "load_asset",
    ]
    if action not in valid_actions:
      return {
          "error": (
              f"Unknown action: {action}. Valid actions are: {valid_actions}"
          )
      }

    if action == "list":
      return [_frontmatter_to_dict(s) for s in self._client.list()]

    skill_name = args.get("skill_name")
    if not skill_name:
      return {"error": f"skill_name is required for action '{action}'"}

    if action == "view_manifest":
      try:
        skill = self._client.retrieve(skill_name)
        return {
            "skill_name": skill_name,
            "manifest_content": skill.instructions,
        }
      except ValueError as e:
        return {"error": str(e)}
    elif action == "run_script":
      raise NotImplementedError("run_script is not implemented yet.")
    elif action == "load_reference":
      reference_path = args.get("reference_path")
      if not reference_path:
        return {"error": "reference_path is required for load_reference"}
      try:
        skill = self._client.retrieve(skill_name)
      except ValueError:
        return {"error": f"Skill '{skill_name}' not found"}
      content = skill.resources.get_reference(reference_path)
      if content is None:
        return {"error": f"Reference not found: {reference_path}"}
      return {
          "skill_name": skill_name,
          "reference_path": reference_path,
          "content": content,
      }
    elif action == "load_asset":
      asset_path = args.get("asset_path")
      if not asset_path:
        return {"error": "asset_path is required for load_asset"}
      try:
        skill = self._client.retrieve(skill_name)
      except ValueError:
        return {"error": f"Skill '{skill_name}' not found"}
      content = skill.resources.get_asset(asset_path)
      if content is None:
        return {"error": f"Asset not found: {asset_path}"}
      return {
          "skill_name": skill_name,
          "asset_path": asset_path,
          "content": content,
      }
    else:
      return {"error": f"Unknown action: {action}"}
