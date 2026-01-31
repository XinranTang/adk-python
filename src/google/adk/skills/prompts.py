"""Module for skill prompt generation."""

import html
from typing import List, Optional, Tuple

from . import models


def format_skills_as_xml(skills: List[models.Frontmatter]) -> str:
  """Formats available skills into a standard XML string.

  Args:
    skills: A list of skill frontmatter objects.

  Returns:
      XML string with <available_skills> block containing each skill's
      name and description.
  """
  return format_skills_as_xml_with_location([(None, skill) for skill in skills])


def format_skills_as_xml_with_location(
    skills: List[Tuple[Optional[str], models.Frontmatter]],
) -> str:
  """Formats available skills into a standard XML string, including location.

  Args:
    skills: A list of tuples, where each tuple contains an optional skill
      location and its corresponding skill frontmatter.

  Returns:
      XML string with <available_skills> block containing each skill's
      name, description, and location.
  """
  if not skills:
    return "<available_skills>\n</available_skills>"

  lines = ["<available_skills>"]

  for location, skill in skills:
    lines.append("<skill>")
    lines.append("<name>")
    lines.append(html.escape(skill.name))
    lines.append("</name>")
    lines.append("<description>")
    lines.append(html.escape(skill.description))
    lines.append("</description>")
    if location:
      lines.append("<location>")
      lines.append(location)
      lines.append("</location>")
    lines.append("</skill>")

  lines.append("</available_skills>")

  return "\n".join(lines)
