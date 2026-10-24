"""Runtime entrypoint for the independent clinical-failure intelligence preview."""
from __future__ import annotations
from typing import Any, ClassVar
from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .orchestration_v0_1_12 import run_analysis
else:
    from orchestration_v0_1_12 import run_analysis


class ClinicalFailureIntelligenceAdapter(Adapter):
    """Interpret governed context through admitted roles; never own execution authority."""
    key: ClassVar[str] = "nusaibah.clinical_failure_intelligence"
    version: ClassVar[str] = "0.1.12"

    def self_inspect(self, staged_payload, schema_contract):
        """Validate the exact staged artifact before governed publication."""
        if __package__:
            from .output_inspection_v0_1_12 import inspect_staged_payload
        else:
            from output_inspection_v0_1_12 import inspect_staged_payload
        return inspect_staged_payload(staged_payload, schema_contract)

    def invoke(self, inputs: Any, context: Any) -> dict[str, Any]:
        """Return a validated preview without publishing or changing product/class memory."""
        del context
        if __package__:
            from .product_range_v0_1_12 import range_selection, scoped_inputs
        else:
            from product_range_v0_1_12 import range_selection, scoped_inputs
        values = inputs.get('variables', {}) if isinstance(inputs, dict) else {}
        if {'previous_assessment','previous_continuation'} & set(inputs):
            if __package__:
                from .continuation_v0_1_12 import continue_analysis
                from .contracts_v0_1_12 import require
            else:
                from continuation_v0_1_12 import continue_analysis
                from contracts_v0_1_12 import require
            require('product_index_range' not in values, 'clinical_continuation_range_conflict')
            return continue_analysis(inputs)
        if 'product_index_range' in values:
            if 'selected_product_index' not in values:
                return range_selection(inputs)
            selected, receipt = scoped_inputs(inputs)
            result = run_analysis(selected)
            result['outputs']['product_selection'] = receipt
            return result
        return run_analysis(inputs)
