"""Retain the exact retrieved source snapshot alongside the existing proposals."""
from hashlib import sha256
try:
    from .review_packet_v0_1_21 import build_review_packet_v0_1_21, canonical_bytes, require_output_bound
except ImportError:
    from review_packet_v0_1_21 import build_review_packet_v0_1_21, canonical_bytes, require_output_bound

def build_review_packet_v0_1_26(prepared,**kwargs):
    packet=build_review_packet_v0_1_21(prepared,**kwargs)
    for company,state in zip(packet['companies'],prepared):
        company['retrieved_source_snapshot']=state['result'].get('retrieved_source_snapshot')
        for name,role in (('memory','company_memory'),('methodology','company_methodology')):
            baseline=state.get('review_baselines',{}).get(role,{})
            company[name+'_proposal']['baseline_package_digest']=baseline.get('package_digest')
            company[name+'_proposal']['baseline_snapshot_id']=baseline.get('snapshot_id')
    packet['packet_sha256']='sha256:'+sha256(canonical_bytes({k:v for k,v in packet.items() if k!='packet_sha256'})).hexdigest()
    require_output_bound(packet)
    return packet
