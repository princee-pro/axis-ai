"""
Skill Memory.
Library of learned workflows and automation recipes.
"""

class SkillLibrary:
    def __init__(self):
        self.skills = {}

    def add_skill(self, name, steps):
        """
        Learn a new skill from user demonstration or instruction.
        """
        self.skills[name] = steps

    def get_skill(self, name):
        """
        Retrieve a skill by name.
        """
        return self.skills.get(name)
