"""Current company profile, bounded source verification and existing Skill publication."""
from typing import ClassVar
from adapters.base import Adapter

try:
    from .orchestration_v0_1_48 import invoke_v0_1_48
except ImportError:
    from orchestration_v0_1_48 import invoke_v0_1_48

AGENT_ORCHESTRATION_OWNER = 'python_adapter'


class NusaibahPharmaCompanyIntelligenceLabV048Adapter(Adapter):
    key: ClassVar[str] = 'nusaibah.pharma_company_intelligence_lab'
    version: ClassVar[str] = '0.1.48'

    def invoke(self, inputs, context):
        del context
        from devtools.skill_changes import SkillChangeSet
        if not callable(getattr(SkillChangeSet, 'rename_title', None)):
            raise RuntimeError('pharma_runtime_skill_title_capability_required')
        return invoke_v0_1_48(inputs, asset_identity=f'{self.key}:{self.version}')
