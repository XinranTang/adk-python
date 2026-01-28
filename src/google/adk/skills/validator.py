"""Skill validation logic."""

import pathlib
from typing import Dict, List, Optional
import unicodedata

from . import file_loader
from . import models


MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500

# Allowed frontmatter fields per Agent Skills Spec
ALLOWED_FRONTMATTER_FIELDS = frozenset({
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
})


def validate_name(
    name: str, skill_dir: Optional[pathlib.Path] = None
) -> List[str]:
  """Validate skill name format and directory match.

  Skill names support i18n characters (Unicode letters) plus hyphens.
  Names must be lowercase and cannot start/end with hyphens.

  Args:
      name: The skill name to validate
      skill_dir: Optional path to skill directory (for name-directory match
        check)

  Returns:
      List of validation error messages
  """
  errors = []

  if not isinstance(name, str) or not name.strip():
    errors.append("Field 'name' must be a non-empty string")
    return errors

  name = unicodedata.normalize("NFKC", name.strip())

  if len(name) > MAX_SKILL_NAME_LENGTH:
    errors.append(
        f"Skill name '{name}' exceeds {MAX_SKILL_NAME_LENGTH} character"
        f" limit ({len(name)} chars)"
    )

  if name != name.lower():
    errors.append(f"Skill name '{name}' must be lowercase")

  if name.startswith("-") or name.endswith("-"):
    errors.append("Skill name cannot start or end with a hyphen")

  if "--" in name:
    errors.append("Skill name cannot contain consecutive hyphens")

  if not all(c.isalnum() or c == "-" for c in name):
    errors.append(
        f"Skill name '{name}' contains invalid characters. "
        "Only letters, digits, and hyphens are allowed."
    )

  if skill_dir:
    dir_name = unicodedata.normalize("NFKC", skill_dir.name)
    if dir_name != name:
      errors.append(
          f"Directory name '{skill_dir.name}' must match skill name '{name}'"
      )

  return errors


def validate_description(description: str) -> List[str]:
  """Validate description format.

  Args:
      description: The description to validate

  Returns:
      List of validation error messages
  """
  errors = []

  if not isinstance(description, str) or not description.strip():
    errors.append("Field 'description' must be a non-empty string")
    return errors

  if len(description) > MAX_DESCRIPTION_LENGTH:
    errors.append(
        f"Description exceeds {MAX_DESCRIPTION_LENGTH} character limit "
        f"({len(description)} chars)"
    )

  return errors


def validate_compatibility(compatibility: str) -> List[str]:
  """Validate compatibility format.

  Args:
      compatibility: The compatibility string to validate

  Returns:
      List of validation error messages
  """
  errors = []

  if not isinstance(compatibility, str):
    errors.append("Field 'compatibility' must be a string")
    return errors

  if len(compatibility) > MAX_COMPATIBILITY_LENGTH:
    errors.append(
        f"Compatibility exceeds {MAX_COMPATIBILITY_LENGTH} character"
        f" limit ({len(compatibility)} chars)"
    )

  return errors


def validate_metadata_fields(metadata: Dict[str, str]) -> List[str]:
  """Validate that only allowed fields are present.

  Args:
      metadata: The metadata dictionary to validate

  Returns:
      List of validation error messages
  """
  errors = []

  extra_fields = set(metadata.keys()) - ALLOWED_FRONTMATTER_FIELDS
  if extra_fields:
    errors.append(
        "Unexpected fields in frontmatter:"
        f" {', '.join(sorted(extra_fields))}. Only"
        f" {sorted(ALLOWED_FRONTMATTER_FIELDS)} are allowed."
    )

  return errors


def validate_metadata(
    metadata: Dict[str, str], skill_dir: Optional[pathlib.Path] = None
) -> List[str]:
  """Validate parsed skill metadata.

  This is the core validation function that works on already-parsed metadata,
  avoiding duplicate file I/O when called from the parser.

  Args:
      metadata: Parsed YAML frontmatter dictionary
      skill_dir: Optional path to skill directory (for name-directory match
        check)

  Returns:
      List of validation error messages. Empty list means valid.
  """
  errors = []
  errors.extend(validate_metadata_fields(metadata))

  if "name" not in metadata:
    errors.append("Missing required field in frontmatter: name")
  else:
    errors.extend(validate_name(metadata["name"], skill_dir))

  if "description" not in metadata:
    errors.append("Missing required field in frontmatter: description")
  else:
    errors.extend(validate_description(metadata["description"]))

  if "compatibility" in metadata:
    errors.extend(validate_compatibility(metadata["compatibility"]))

  return errors


def validate(skill_dir: pathlib.Path) -> List[str]:
  """Validate a skill directory and its SKILL.md file.

  This is the high-level validation function that reads from the filesystem.

  Args:
      skill_dir: Path to the skill directory

  Returns:
      List of validation error messages. Empty list means valid.
  """
  skill_dir = pathlib.Path(skill_dir)
  errors = []

  # Check if directory exists
  if not skill_dir.exists():
    return [f"Skill directory does not exist: {skill_dir}"]

  if not skill_dir.is_dir():
    return [f"Path is not a directory: {skill_dir}"]

  # Parse and validate frontmatter
  try:
    frontmatter, _ = file_loader.load_skill_md(skill_dir)
    metadata = {
        "name": frontmatter.name,
        "description": frontmatter.description,
    }
    if frontmatter.license is not None:
      metadata["license"] = frontmatter.license
    if frontmatter.compatibility is not None:
      metadata["compatibility"] = frontmatter.compatibility
    if frontmatter.allowed_tools is not None:
      metadata["allowed-tools"] = frontmatter.allowed_tools
    if frontmatter.metadata:
      metadata["metadata"] = frontmatter.metadata

    errors.extend(validate_metadata(metadata, skill_dir))
  except ValueError as e:
    # load_skill_md raises ValueError if SKILL.md is not found or unreadable
    errors.append(str(e))

  return errors


def validate_skill(skill: models.Skill) -> List[str]:
  """Validate a Skill object.

  Args:
      skill: The Skill object to validate

  Returns:
      List of validation error messages. Empty list means valid.
  """
  frontmatter = skill.frontmatter
  metadata = {
      "name": frontmatter.name,
      "description": frontmatter.description,
  }
  if frontmatter.license is not None:
    metadata["license"] = frontmatter.license
  if frontmatter.compatibility is not None:
    metadata["compatibility"] = frontmatter.compatibility
  if frontmatter.allowed_tools is not None:
    metadata["allowed-tools"] = frontmatter.allowed_tools
  if frontmatter.metadata:
    metadata["metadata"] = frontmatter.metadata

  return validate_metadata(metadata, skill_dir=None)
