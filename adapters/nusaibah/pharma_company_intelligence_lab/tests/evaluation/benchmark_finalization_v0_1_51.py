"""Reproduce provider-free content parity and prompt/call savings, not live latency.

Run with the official SDK source on PYTHONPATH. No providers or mutations outside
in-memory test fixtures are used. Live wall-time qualification remains separate.
"""
from hashlib import sha256
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_durable_batched_v0_1_51 import BatchedInputs,DraftInputs
from orchestration_v0_1_50 import invoke_v0_1_50
from orchestration_v0_1_51 import invoke_v0_1_51


def main():
    rows=[]
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Unexpected network access')):
        for version,fixture,invoke in [('0.1.50',DraftInputs,invoke_v0_1_50),('0.1.51',BatchedInputs,invoke_v0_1_51)]:
            inputs=fixture();started=time.perf_counter()
            result=invoke(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:'+version)
            elapsed=time.perf_counter()-started
            row=result['outputs']['intelligence_dossier']['company_results'][0]
            text=inputs.store[(13,'company_memory')]['text']
            rows.append({'version':version,'fixture_cpu_wall_seconds':round(elapsed,6),
                'agent_calls':result['metrics']['agent_call_count'],
                'canonical_chars':len(text),'canonical_bytes':len(text.encode()),
                'canonical_sha256':sha256(text.encode()).hexdigest(),
                'section_coverage':row['required_section_coverage_count'],
                'accepted_claim_count':row['accepted_claim_count'],
                'readback_verified':row['skill_publication']['memory']['readback_verified'],
                'history_verified':row['skill_publication']['memory']['history_verified'],
                'critic_batching':row.get('critic_review_batching')})
    assert all(rows[0][key]==rows[1][key] for key in ['canonical_chars','canonical_bytes','canonical_sha256','section_coverage','accepted_claim_count'])
    proof=rows[1]['critic_batching']
    print(json.dumps({'schema_version':'pharma_fixture_benchmark.v1','provider_calls':0,
        'canonical_parity':True,'live_wall_time_saving_verified':False,
        'critic_call_reduction_percent':round(100*(1-proof['planned_group_count']/proof['original_packet_count']),2),
        'critic_prompt_bound_reduction_percent':round(100*(1-proof['batched_prompt_bound_chars']/proof['original_prompt_bound_chars']),2),
        'runs':rows},indent=2))


if __name__=='__main__':main()
