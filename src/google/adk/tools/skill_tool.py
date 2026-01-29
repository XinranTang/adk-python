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

You can use specialized 'skills' to help you with complex tasks. You MUST use the `manage_skills` tool to interact with these skills. Each skill has a name and a description listed below.

Skills are folders of instructions, scripts, and resources that extend your capabilities for specialized tasks. Each skill folder contains:
- **SKILL.md** (required): The main instruction file with skill metadata and detailed markdown instructions.
- **references/** (Optional): Additional documentation or examples for skill usage.
- **assets/** (Optional): Templates, scripts or other resources used by the skill.
- **scripts/** (Optional): Helper scripts and utilities that extend your capabilities.

This is very important:
- If a skill seems relevant to the current user query, you MUST use the `manage_skills` tool with the `view_file` action and `file_path="SKILL.md"` to read its full instructions before proceeding.
- Once you have read the instructions, follow them exactly as documented before replying to the user.
"""


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
            - View file (manifest):
                `manage_skills(action="view_file", skill_name="SKILL_NAME", file_path="SKILL.md")`
            - View file (script):
                `manage_skills(action="view_file", skill_name="SKILL_NAME", file_path="scripts/SCRIPT_NAME")`
            - Run script:
                `manage_skills(action="run_script", skill_name="SKILL_NAME", file_path="scripts/SCRIPT_NAME", kwargs={"arg1": "value1"})`
            - List files:
                `manage_skills(action="list_files", skill_name="SKILL_NAME", file_path="references")`
            """
        ),
    )
    self._client = client

  def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
    return types.FunctionDeclaration(
        name=self.name,
        description=self.description + self._client.format_skills_as_xml(),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "action": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The action to perform: view_file, list_files,"
                        " run_script"
                    ),
                    enum=[
                        "view_file",
                        "list_files",
                        "run_script",
                    ],
                ),
                "skill_name": types.Schema(
                    type=types.Type.STRING,
                    description="The name of the target skill directory.",
                ),
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Relative path to the file or directory within the"
                        " skill. For view_file, examples: 'SKILL.md',"
                        " 'references/doc.md', 'scripts/tool.py'. For"
                        " list_files, examples: 'references', 'assets',"
                        " 'scripts'. For run_script, example:"
                        " 'scripts/tool.py'."
                    ),
                ),
                "kwargs": types.Schema(
                    type=types.Type.OBJECT,
                    description=(
                        "Keyword arguments to pass to the script (for"
                        " run_script)."
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
        "view_file",
        "list_files",
        "run_script",
    ]
    if action not in valid_actions:
      return {
          "error": (
              f"Unknown action: {action}. Valid actions are: {valid_actions}"
          )
      }

    skill_name = args.get("skill_name")
    if not skill_name:
      return {"error": f"skill_name is required for action '{action}'"}

    try:
      skill = self._client.retrieve(skill_name)
    except ValueError as e:
      return {"error": str(e)}

    file_path = args.get("file_path")

    if action == "view_file":
      if not file_path:
        return {"error": "file_path is required for view_file"}

      content = None
      if file_path.endswith("SKILL.md"):
        content = skill.instructions
      else:
        found_category = None
        relative_path = None
        for category in ["references", "assets", "scripts"]:
          token = f"{category}/"
          if token in file_path:
            found_category = category
            relative_path = file_path.split(token)[-1]
            break

        if found_category == "references":
          content = skill.resources.get_reference(relative_path)
        elif found_category == "assets":
          content = skill.resources.get_asset(relative_path)
        elif found_category == "scripts":
          script = skill.resources.get_script(relative_path)
          if script:
            content = script.src
        else:
          return {
              "error": (
                  f"Invalid file_path: {file_path}. Must be 'SKILL.md' or"
                  " contain 'references/', 'assets/', or 'scripts/'"
              )
          }

      if content is None:
        return {"error": f"File not found: {file_path}"}

      return {
          "skill_name": skill_name,
          "file_path": file_path,
          "content": content,
      }

    elif action == "list_files":
      # If file_path is None, we could return top-level.
      # User said "valid path is only references or assets or scripts".
      # So maybe we require file_path? Or default to root.
      # Let's support root (empty/None) and specific dirs.

      if not file_path:
        # Return structure
        return {
            "skill_name": skill_name,
            "files": ["SKILL.md"],
            "directories": ["references", "assets", "scripts"],
        }

      # Strip trailing slash if present
      clean_path = file_path.rstrip("/")

      target_dir = None
      for d in ["references", "assets", "scripts"]:
        if clean_path == d or clean_path.endswith(f"/{d}"):
          target_dir = d
          break

      if target_dir == "references":
        files = skill.resources.list_references()
      elif target_dir == "assets":
        files = skill.resources.list_assets()
      elif target_dir == "scripts":
        files = skill.resources.list_scripts()
      else:
        return {
            "error": (
                f"Invalid directory: {file_path}. Must be 'references',"
                " 'assets', or 'scripts'"
            )
        }

      return {
          "skill_name": skill_name,
          "directory": target_dir,
          "files": files,
      }

    elif action == "run_script":
      if not file_path:
        return {"error": "file_path is required for run_script"}

      script_kwargs = args.get("kwargs", {})

      # Determine script name (key in resources.scripts)
      # We allow 'scripts/foo.py' or 'foo.py'.
      script_name = file_path
      if "scripts/" in file_path:
        script_name = file_path.split("scripts/")[-1]

      try:
        response = self._client.execute(
            skill_name,
            types.FunctionCall(name=script_name, args=script_kwargs),
        )
        return response.response
      except Exception as e:  # pylint: disable=broad-except
        return {"error": str(e)}

    return {"error": f"Unexpected action: {action}"}
