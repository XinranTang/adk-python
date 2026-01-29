from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.skill_tool import SkillTool
from google.adk.tools.skill_tool import DEFAULT_SYSTEM_INSTRUCTION
from google.adk.skills.file_system_client import FileSystemClient

skills_client = FileSystemClient(
      skills_base_path="~/.gemini/jetski/global_skills"
)
skill_manager_tool = SkillTool(client=skills_client)


root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="skill_use_agent",
    description=(
        "A skill use agent."
    ),
    instruction=DEFAULT_SYSTEM_INSTRUCTION,
    tools=[
        skill_manager_tool
    ],
)
