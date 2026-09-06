from app.skills.web_research import (
    WebResearchSkill,
)

from app.skills.competitor_research import (
    CompetitorResearchSkill,
)

from app.skills.document_search import (
    DocumentSearchSkill,
)

from app.skills.data_analysis import (
    DataAnalysisSkill,
)

from app.skills.synthesis_analysis import (
    SynthesisAnalysisSkill,
)


SKILL_REGISTRY = {

    "web_research":
        WebResearchSkill(),

    "competitor_research":
        CompetitorResearchSkill(),

    "document_search":
        DocumentSearchSkill(),

    "data_analysis":
        DataAnalysisSkill(),

    "synthesis_analysis":
        SynthesisAnalysisSkill(),
}


def get_skill(
    name: str
):

    skill = SKILL_REGISTRY.get(
        name
    )

    if skill is None:

        raise ValueError(
            f"Unknown skill: {name}"
        )

    return skill


def list_skills() -> list[str]:

    return list(
        SKILL_REGISTRY.keys()
    )
