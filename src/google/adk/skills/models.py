"""Data models for Agent Skills."""

import dataclasses
from typing import Dict, List, Optional


# TODO: built-in parser, skill to prompt converter, validators.
@dataclasses.dataclass
class Frontmatter:
  """L1 skill content: metadata parsed from SKILL.md frontmatter for skill discovery.

  Attributes:
      name: Skill name in kebab-case (required).
      description: What the skill does and when the model should use it
        (required).
      license: License for the skill (optional).
      compatibility: Compatibility information for the skill (optional).
      allowed_tools: Tool patterns the skill requires (optional, experimental).
      metadata: Key-value pairs for client-specific properties (defaults to
        empty dict).
  """

  name: str
  description: str
  license: Optional[str] = None
  compatibility: Optional[str] = None
  allowed_tools: Optional[str] = None
  metadata: Dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Resources:
  """L3 skill content: additional instructions, assets, and scripts, loaded as needed.

  Attributes:
      references: Additional markdown files with instructions, workflows, or
        guidance.
      assets: Resource materials like database schemas, API documentation,
        templates, or examples.
      scripts: Executable scripts that can be run via bash.
  """

  references: Dict[str, str] = dataclasses.field(default_factory=dict)
  assets: Dict[str, str] = dataclasses.field(default_factory=dict)
  scripts: Dict[str, str] = dataclasses.field(default_factory=dict)

  def get_reference(self, reference_path: str) -> Optional[str]:
    """Get content of a reference file.

    Args:
        reference_path: Relative path to the reference file

    Returns:
        Reference content as string, or None if not found
    """
    return self.references.get(reference_path)

  def get_asset(self, asset_path: str) -> Optional[str]:
    """Get content of an asset file.

    Args:
        asset_path: Relative path to the asset file

    Returns:
        Asset content as string, or None if not found
    """
    return self.assets.get(asset_path)

  def get_script(self, script_path: str) -> Optional[str]:
    """Get content of a script file.

    Args:
        script_path: Relative path to the script file

    Returns:
        Script content as string, or None if not found
    """
    return self.scripts.get(script_path)

  def list_references(self) -> List[str]:
    """List all available reference paths."""
    return list(self.references.keys())

  def list_assets(self) -> List[str]:
    """List all available asset paths."""
    return list(self.assets.keys())

  def list_scripts(self) -> List[str]:
    """List all available script paths."""
    return list(self.scripts.keys())


@dataclasses.dataclass
class Skill:
  """Complete skill representation including frontmatter, instructions, and resources.

  A skill combines:
  - L1: Frontmatter for discovery (name, description).
  - L2: Instructions from SKILL.md body, loaded when skill is triggered.
  - L3: Resources including additional instructions, assets, and scripts,
  loaded as needed.

  Attributes:
      frontmatter: Parsed skill frontmatter from SKILL.md.
      instructions: L2 skill content: markdown instruction from SKILL.md body.
      resources: L3 skill content: additional instructions, assets, and scripts.
  """

  frontmatter: Frontmatter
  instructions: str
  resources: Resources = dataclasses.field(default_factory=Resources)

  @property
  def name(self) -> str:
    """Convenience property to access skill name."""
    return self.frontmatter.name

  @property
  def description(self) -> str:
    """Convenience property to access skill description."""
    return self.frontmatter.description
