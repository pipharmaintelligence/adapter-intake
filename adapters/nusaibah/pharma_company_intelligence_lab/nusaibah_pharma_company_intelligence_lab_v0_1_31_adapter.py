"""Single-pass company enrichment and existing Core Dynamic Skill publication."""
from typing import ClassVar
from adapters.base import Adapter
try:
    from .orchestration_v0_1_31 import invoke_v0_1_31
except ImportError:
    from orchestration_v0_1_31 import invoke_v0_1_31
AGENT_ORCHESTRATION_OWNER='python_adapter'
class NusaibahPharmaCompanyIntelligenceLabV031Adapter(Adapter):
    key:ClassVar[str]='nusaibah.pharma_company_intelligence_lab'
    version:ClassVar[str]='0.1.31'
    def invoke(self,inputs,context):
        del context
        return invoke_v0_1_31(inputs,asset_identity=f'{self.key}:{self.version}')
