"""Utilities for parsing skill-related files."""

import pathlib
from typing import Dict, Optional

import yaml

from . import models


def read_file(path: pathlib.Path) -> Optional[str]:
  """Safely reads a file's content as a string."""
  try:
    if path.is_file():
      return path.read_text(encoding="utf-8")
  except (OSError, UnicodeDecodeError):
    pass
  return None


def load_directory_files(directory: pathlib.Path) -> Dict[str, str]:
  """Load all files from a directory into a dictionary.

  Args:
    directory: Path to the directory

  Returns:
    Dict mapping relative file paths to their content
  """
  files = {}
  if not directory.exists() or not directory.is_dir():
    return files

  for file_path in directory.rglob("*"):
    if file_path.is_file():
      relative_path = file_path.relative_to(directory)
      content = read_file(file_path)
      if content is not None:
        files[str(relative_path)] = content

  return files


def load_skill_md(skill_dir: pathlib.Path) -> tuple[models.Frontmatter, str]:
  """Locates and reads the SKILL.md file, parsing its frontmatter and body.

  This function finds the SKILL.md file within the given directory, reads its
  content, and then separates the YAML frontmatter from the markdown body.
  It performs basic validation on the presence of required fields like 'name'
  and 'description' in the frontmatter.

  Args:
    skill_dir: Path to the skill directory

  Returns:
    A tuple containing:
      -   A `models.Frontmatter` object with the parsed metadata from the YAML.
      -   The markdown body of the SKILL.md file as a string.

  Raises:
    ValueError: If SKILL.md is not found, has invalid YAML in the frontmatter,
      or is missing required fields ('name', 'description').
  """
  skill_dir = pathlib.Path(skill_dir)
  skill_md = None
  for name in ("SKILL.md", "skill.md"):
    path = skill_dir / name
    if path.exists():
      skill_md = path
      break

  if skill_md is None:
    raise ValueError(f"SKILL.md not found in {skill_dir}")

  content = read_file(skill_md)
  if content is None:
    raise ValueError(f"Could not read SKILL.md in {skill_dir}")
  return parse_skill_md(content)


def load_skill(skill_dir: pathlib.Path) -> models.Skill:
  """Load a complete skill including all resources.

  This is the main function for loading a full Skill object with
  frontmatter, instructions, references, assets, and scripts.

  Args:
    skill_dir: Path to the skill directory

  Returns:
    Skill object with all components loaded

  Raises:
    ValueError: If SKILL.md is missing, has invalid YAML, or required fields are
      missing or invalid.
    FileNotFoundError: If the skill directory or SKILL.md is not found.
  """
  skill_dir = pathlib.Path(skill_dir).resolve()

  if not skill_dir.is_dir():
    raise FileNotFoundError(f"Skill directory '{skill_dir}' not found.")
  if (
      not (skill_dir / "SKILL.md").exists()
      and not (skill_dir / "skill.md").exists()
  ):
    raise FileNotFoundError(f"SKILL.md not found in '{skill_dir}'.")

  # Load properties and manifest
  frontmatter, manifest_body = load_skill_md(skill_dir)

  # Load optional directories
  references = load_directory_files(skill_dir / "references")
  assets = load_directory_files(skill_dir / "assets")
  scripts = load_directory_files(skill_dir / "scripts")

  resources = models.Resources(
      references=references,
      assets=assets,
      scripts=scripts,
  )

  skill = models.Skill(
      frontmatter=frontmatter,
      instructions=manifest_body,
      resources=resources,
  )

  return skill


def parse_skill_md(skill_md_str: str) -> tuple[models.Frontmatter, str]:
  """Parses YAML frontmatter from SKILL.md content.

  Args:
    skill_md_str: Raw content of SKILL.md file as a string.

  Returns:
    A tuple containing:
      -   A `models.Frontmatter` object with the parsed metadata from the YAML.
      -   The markdown body of the SKILL.md file as a string.

  Raises:
    ValueError: If frontmatter is missing, has invalid YAML, or required fields
      ('name', 'description') are missing or invalid.
  """
  if not skill_md_str.startswith("---"):
    raise ValueError("SKILL.md must start with YAML frontmatter (---)")

  parts = skill_md_str.split("---", 2)
  if len(parts) < 3:
    raise ValueError("SKILL.md frontmatter not properly closed with ---")

  frontmatter_str = parts[1]
  body = parts[2].strip()

  try:
    parsed = yaml.safe_load(frontmatter_str)
    metadata = parsed
  except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML in frontmatter: {e}") from e

  if not isinstance(metadata, dict):
    raise ValueError("SKILL.md frontmatter must be a YAML mapping")

  if "name" not in metadata:
    raise ValueError("Missing required field in frontmatter: name")
  if "description" not in metadata:
    raise ValueError("Missing required field in frontmatter: description")

  name = metadata["name"]
  description = metadata["description"]

  if not isinstance(name, str) or not name.strip():
    raise ValueError("Field 'name' must be a non-empty string")
  if not isinstance(description, str) or not description.strip():
    raise ValueError("Field 'description' must be a non-empty string")

  kwargs = {}
  if "license" in metadata:
    kwargs["license"] = metadata["license"]
  if "compatibility" in metadata:
    kwargs["compatibility"] = metadata["compatibility"]
  if "allowed-tools" in metadata:
    kwargs["allowed_tools"] = metadata["allowed-tools"]
  if "metadata" in metadata and isinstance(metadata["metadata"], dict):
    kwargs["metadata"] = {
        str(k): str(v) for k, v in metadata["metadata"].items()
    }

  return (
      models.Frontmatter(
          name=name.strip(), description=description.strip(), **kwargs
      ),
      body,
  )
