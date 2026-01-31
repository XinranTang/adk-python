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
from ..skills import models
from ..skills import prompts as prompt
from ..skills import scripts
from .base_tool import BaseTool
from .tool_context import ToolContext


# Works with SkillTool.
DEFAULT_SYSTEM_INSTRUCTION = """

You can use specialized 'skills' to help you with complex tasks. You MUST use the `manage_skills` tool to interact with these skills. Each skill has a name and a description listed below.

Skills are folders of instructions, scripts, and resources that extend your capabilities for specialized tasks. Each skill folder contains:
- **SKILL.md** (required): The main instruction file with skill metadata and detailed markdown instructions.
- **references/** (Optional): Additional documentation or examples for skill usage.
- **assets/** (Optional): Templates, scripts or other resources used by the skill.
- **scripts/** (Optional): Helper scripts and utilities that extend your capabilities.

This is very important:

1. If a skill seems relevant to the current user query, you MUST use the `manage_skills` tool with the `view_file` action and `file_path="SKILL.md"` to read its full instructions before proceeding.
2. Once you have read the instructions, follow them exactly as documented before replying to the user. For example, If the instruction lists multiple steps, please make sure you complete all of them in order.
3. Skill scripts MUST be executed using `manage_skills(action="run_script", skill_name="<SKILL_NAME>", file_path="scripts/<SCRIPT_NAME>", kwargs={...})`. You MUST NOT use other tools to execute scripts within a skill's `scripts/` directory.
4. The `view_file` action is ONLY for viewing files within a skill's directory (e.g., `SKILL.md`, `references/*`, `assets/*`, `scripts/*`). Do NOT use `view_file` to access files outside of skill directories.
"""

# Works with SecureBashTool.
DEFAULT_SYSTEM_INSTRUCTION_V2 = """

You can use specialized 'skills' to help you with complex tasks. You MUST use the `secure_bash` tool to interact with these skills. Each skill has a name and a description listed below.

Skills are folders of instructions, scripts, and resources that extend your capabilities for specialized tasks. Each skill folder contains:
- `<SKILL_NAME>/SKILL.md` (required): The main instruction file with skill metadata and detailed markdown instructions.
- `<SKILL_NAME>/references/` (Optional): Additional documentation or examples for skill usage.
- `<SKILL_NAME>/assets/` (Optional): Templates, scripts or other resources used by the skill.
- `<SKILL_NAME>/scripts/` (Optional): Helper scripts and utilities that extend your capabilities.

This is very important:

1. If a skill seems relevant to the current user query, you MUST use `secure_bash(command="cat", path="<SKILL_NAME>/SKILL.md")` to read its full instructions before proceeding.
2. Once you have read the instructions, follow them exactly as documented before replying to the user. For example, If the instruction lists multiple steps, please make sure you complete all of them in order.
3. Skill scripts MUST be executed using `secure_bash(command="sh", path="<SKILL_NAME>/scripts/<SCRIPT_NAME>", args={...})`. You MUST NOT use other tools like python, bash, etc., to execute scripts within a skill's `scripts/` directory.
   For example, if the skill instruction asks you to run a python script, you MUST use `secure_bash(command="sh", path="<SKILL_NAME>/scripts/<SCRIPT_NAME>", args={...})` to execute it, NOT `python <SKILL_NAME>/scripts/<SCRIPT_NAME>`.
4. The `cat` command is ONLY for viewing files within a skill's directory (e.g., `SKILL_NAME/SKILL.md`, `SKILL_NAME/references/*`, `SKILL_NAME/assets/*`, `SKILL_NAME/scripts/*`). Do NOT use `cat` to access files outside of skill directories.
"""


def _execute_skill_script(
    skill: models.Skill,
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
    skill: The skill to execute script from.
    function_call: The function call to execute.

  Returns:
    The response from the function execution.
  """
  script_id = function_call.name
  script = skill.resources.get_script(script_id)

  if script is None:
    raise ValueError(
        f"Script '{script_id}' for function '{function_call.name}' not"
        f" found in skill '{skill.name}'"
    )

  if not isinstance(script, scripts.FunctionScript):
    raise ValueError(
        f"Script '{script_id}' is of type '{type(script).__name__}', which"
        " is not supported by this tool. Only 'FunctionScript' is supported."
    )

  result = script.func(**function_call.args)
  return types.FunctionResponse(
      id=function_call.id,
      name=function_call.name,
      response={"result": result},
  )


class SecureBashTool(BaseTool):
  """A secure bash tool for skill interaction via in-memory functions.

  This allows tying functions to different scripts without front-loading them,
  preventing overwhelming the model. This is not part of any prompt.
  """

  def __init__(
      self,
      skills: list[models.Skill],
  ):
    # TODO: support a skill search command, so model can discover skills.
    super().__init__(
        name="secure_bash",
        description=(
            """A secure bash tool that enables interaction with skills via an in-memory data structure. It offers restricted execution by routing commands (`ls`, `cat`, `sh`) to in-memory functions, providing a sandboxed environment for secure skill testing and execution without filesystem or internet access.

            Examples:
            - View manifest file:
                `secure_bash(command="cat", path="SKILL_NAME/SKILL.md")`
            - View script file:
                `secure_bash(command="cat", path="SKILL_NAME/scripts/SCRIPT_NAME")`
            - Run script:
                `secure_bash(command="sh", path="SKILL_NAME/scripts/SCRIPT_NAME", args={"arg1": "value1"})`
            - List files:
                `secure_bash(command="ls", path="SKILL_NAME/references")`
            """
        ),
    )
    self._skills = {skill.name: skill for skill in skills}

  def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
    return types.FunctionDeclaration(
        name=self.name,
        description=self.description
        + prompt.format_skills_as_xml(
            [s.frontmatter for s in self._skills.values()]
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "command": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The bash-like command to perform: ls, cat, sh."
                    ),
                    enum=["ls", "cat", "sh"],
                ),
                "path": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The path to target, e.g., my_skill/SKILL.md,"
                        " my_skill/scripts/"
                    ),
                ),
                "args": types.Schema(
                    type=types.Type.OBJECT,
                    description="Arguments for sh command.",
                ),
            },
            required=["command", "path"],
        ),
    )

  def _parse_skill_path(self, path: str) -> tuple[str, str] | None:
    if path.startswith("./"):
      path = path[2:]
    parts = path.split("/", 1)
    skill_name = parts[0]
    if skill_name not in self._skills:
      return None
    if len(parts) == 2:
      return skill_name, parts[1]
    else:
      return skill_name, ""

  def _view_file(self, skill_name: str, file_path: str) -> Any:
    """Views a file from a skill."""
    if skill_name not in self._skills:
      return {"error": f"Skill '{skill_name}' not found."}
    skill = self._skills[skill_name]

    if not file_path:
      return {"error": "file_path is required to view file."}

    content = None
    if file_path == "SKILL.md":
      content = skill.instructions
    else:
      found_category = None
      relative_path = file_path
      for category in ["references", "assets", "scripts"]:
        if file_path.startswith(category + "/"):
          found_category = category
          relative_path = file_path[len(category) + 1 :]
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
                f"Invalid file_path: '{file_path}'. For 'cat' command, path"
                " must be 'SKILL.md' or start with 'references/', 'assets/',"
                " or 'scripts/'."
            )
        }

    if content is None:
      return {
          "error": (
              f"File '{file_path}' not found in skill '{skill_name}'. Use 'ls'"
              " on the directory to list available files."
          )
      }
    return {"output": content}

  def _list_files(self, skill_name: str, file_path: str) -> Any:
    """Lists files in a skill."""
    if skill_name not in self._skills:
      return {"error": f"Skill '{skill_name}' not found."}
    skill = self._skills[skill_name]

    if not file_path or file_path == ".":
      return {"output": "SKILL.md\nreferences/\nassets/\nscripts/"}
    clean_path = file_path.rstrip("/")
    if clean_path == "references":
      files = [f"references/{f}" for f in skill.resources.list_references()]
    elif clean_path == "assets":
      files = [f"assets/{f}" for f in skill.resources.list_assets()]
    elif clean_path == "scripts":
      files = [f"scripts/{f}" for f in skill.resources.list_scripts()]
    else:
      return {
          "error": (
              f"Invalid directory for 'ls': '{file_path}'. Must be '.', "
              "'references', 'assets', or 'scripts'."
          )
      }
    return {"output": "\n".join(files)}

  def _run_script(
      self, skill_name: str, file_path: str, script_args: dict[str, Any]
  ) -> Any:
    """Runs a script from a skill."""
    if not file_path:
      return {"error": "file_path is required for 'run_script' action."}

    script_name = file_path
    if file_path.startswith("scripts/"):
      script_name = file_path[len("scripts/") :]

    try:
      response = _execute_skill_script(
          self._skills[skill_name],
          types.FunctionCall(name=script_name, args=script_args),
      )
      return {"output": response.response}
    except Exception as e:  # pylint: disable=broad-except
      return {
          "error": (
              f"Error running script '{script_name}' from skill"
              f" '{skill_name}': {e}. You may want to verify the script name"
              " using ls with path='scripts' or check the script file"
              " using cat for correct usage and arguments."
          )
      }

  async def run_async(
      self, *, args: Dict[str, Any], tool_context: ToolContext
  ) -> Any:
    command = args.get("command")
    path = args.get("path")
    script_args = args.get("args", {})

    if not command:
      return {"error": "command is required."}
    if not path:
      return {"error": "path is required."}

    if command not in ["ls", "cat", "sh"]:
      return {"error": f"Invalid command: {command}. Must be ls, cat, or sh."}

    try:
      skill_path_res = self._parse_skill_path(path)
      if not skill_path_res:
        return {
            "error": (
                f"Skill not found or invalid path: {path}. Path must start with"
                " skill name, e.g. SKILL_NAME/file."
            )
        }
      skill_name, inner_path = skill_path_res

      if command == "cat":
        return self._view_file(skill_name, inner_path)
      elif command == "ls":
        return self._list_files(skill_name, inner_path)
      elif command == "sh":
        if not inner_path.startswith("scripts/"):
          return {
              "error": (
                  "Path for 'sh' command must start with 'scripts/', but got:"
                  f" {inner_path}"
              )
          }
        return self._run_script(skill_name, inner_path, script_args)
      else:
        # Should not be reached due to check above
        return {"error": f"Unknown command: {command}"}
    except Exception as e:  # pylint: disable=broad-except
      return {
          "error": f"Error running bash command: {e}.",
      }


class SkillTool(BaseTool):
  """A tool for discovering, viewing, and executing agent skills."""

  def __init__(
      self,
      skills: list[models.Skill],
  ):
    super().__init__(
        name="manage_skills",
        description=(
            """Discovers, views, and executes agent skills. When calling this tool, use the name 'manage_skills'.

            Examples:
            - View file (manifest):
                `manage_skills(action="view_file", skill_name="SKILL_NAME", file_path="SKILL.md")`
            - View file (script):
                `manage_skills(action="view_file", skill_name="SKILL_NAME", file_path="scripts/SCRIPT_NAME")`
            - Run script:
                `manage_skills(action="run_script", skill_name="SKILL_NAME", file_path="scripts/SCRIPT_NAME", args={"arg1": "value1"})`
            - List files:
                `manage_skills(action="list_files", skill_name="SKILL_NAME", file_path="references")`
            """
        ),
    )
    self._skills = {skill.name: skill for skill in skills}

  def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
    return types.FunctionDeclaration(
        name=self.name,
        description=self.description
        + prompt.format_skills_as_xml(
            [s.frontmatter for s in self._skills.values()]
        ),
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
                "args": types.Schema(
                    type=types.Type.OBJECT,
                    description=(
                        "Arguments to pass to the script (for run_script)."
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
              f"Unknown action: '{action}'. Valid actions are: {valid_actions}"
          )
      }

    skill_name = args.get("skill_name")
    if not skill_name:
      return {"error": f"skill_name is required for action '{action}'."}

    if skill_name not in self._skills:
      return {
          "error": (
              f"Failed to retrieve skill '{skill_name}'. Please check the"
              " tool definition for a list of available skills and verify the"
              " skill name."
          )
      }
    skill = self._skills[skill_name]

    file_path = args.get("file_path")

    if action == "view_file":
      if not file_path:
        return {"error": "file_path is required for 'view_file' action."}

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
                  f"Invalid file_path for view_file: '{file_path}'. Expected"
                  " 'SKILL.md' or a path containing 'references/', 'assets/',"
                  " or 'scripts/'."
              )
          }

      if content is None:
        return {
            "error": (
                f"File '{file_path}' not found in skill '{skill_name}'. Use"
                " action='list_files' with file_path='references', 'assets',"
                " or 'scripts' to see available files in this skill."
            )
        }

      return {
          "skill_name": skill_name,
          "file_path": file_path,
          "content": content,
      }

    elif action == "list_files":
      if not file_path or file_path == ".":
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
                f"Invalid directory for list_files: '{file_path}'. Must be"
                " 'references', 'assets', or 'scripts'."
            )
        }

      return {
          "skill_name": skill_name,
          "directory": target_dir,
          "files": files,
      }

    elif action == "run_script":
      if not file_path:
        return {"error": "file_path is required for 'run_script' action."}

      script_args = args.get("args", {})

      # Determine script name (key in resources.scripts)
      # We allow 'scripts/foo.py' or 'foo.py'.
      script_name = file_path
      if "scripts/" in file_path:
        script_name = file_path.split("scripts/")[-1]

      try:
        response = _execute_skill_script(
            self._skills[skill_name],
            types.FunctionCall(name=script_name, args=script_args),
        )
        return response.content
      except Exception as e:  # pylint: disable=broad-except
        return {
            "error": (
                f"Error running script '{script_name}' from skill"
                f" '{skill_name}': {e}. You may want to verify the script name"
                " using list_files(file_path='scripts') or check SKILL.md or"
                " the script itself for correct usage and arguments."
            )
        }

    return {"error": f"Unexpected action: {action}"}
