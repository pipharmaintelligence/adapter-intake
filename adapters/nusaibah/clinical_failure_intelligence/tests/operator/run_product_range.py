"""Official SDK product-range runner. Default is a local no-network command plan."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from clinical_failure_intelligence.contracts_v0_1_12 import ContractError, require
from clinical_failure_intelligence.product_range_v0_1_12 import bounds
from clinical_failure_intelligence.range_workflow_v0_1_12 import ProductRangeWorkflow
from clinical_failure_intelligence.source_workflow_v0_1_12 import SourceReadUnavailable
import run_clinical_workflow as sdk


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--variables-file',required=True)
    parser.add_argument('--product-index-range',required=True)
    parser.add_argument('--checkpoint-directory',required=True)
    parser.add_argument('--env-file')
    parser.add_argument('--live',action='store_true',help='Submit model-free governed selection and case preflights.')
    parser.add_argument('--analyze',action='store_true',help='Authorize bounded source and Agent calls for selected cases.')
    parser.add_argument('--prepare-sources-only',action='store_true',help='Qualify governed source reads without scientific Agent execution.')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(argv)
    bounds(args.product_index_range)
    require(not args.analyze or args.live,'clinical_analysis_requires_live')
    require(not args.prepare_sources_only or args.live,'clinical_source_preparation_requires_live')
    require(not (args.analyze and args.prepare_sources_only),'clinical_range_execution_mode_conflict')
    variables=sdk.read(args.variables_file)
    variables['product_index_range']=args.product_index_range
    if not args.live:
        print(json.dumps({'status':'plan_only','asset':'nusaibah.clinical_failure_intelligence:0.1.12',
            'product_index_range':args.product_index_range,'index_base':0,'end_inclusive':True,
            'workflow_concurrency':2,'provider_calls':0,'workflows_submitted':0}))
        return 0
    require(bool(args.env_file),'clinical_env_file_required')
    config=sdk.read(args.config)
    if config.get('substrate','local_worker')=='local_worker':
        import re
        from clinical_failure_intelligence.retained_sources_v0_1_12 import SOURCE_ROLES
        required={'nusaibah.clinical_failure_intelligence'} | {row[0] for row in SOURCE_ROLES.values()}
        for key in required:
            queue=config.get('assets',{}).get(key,{}).get('queue_name')
            require(isinstance(queue,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',queue) is not None,
                    'clinical_execution_queue_required')
    directory=Path(args.checkpoint_directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    with sdk.checkpoint_lock(directory/'range.lock'):
        def factory(key,selected):
            checkpoint=directory/(key+'.json')
            # Per-case state prevents concurrent SDK operations sharing a writer.
            host=sdk.SdkWorkflowHost(config,selected,args.env_file,checkpoint,
                resume=args.resume and checkpoint.exists())
            def execute(*positional,**named):
                try:return host.execute(*positional,**named)
                except sdk.SourceReadUnavailable as error:raise SourceReadUnavailable(error.code,detail=getattr(error,'detail',None)) from None
            return execute
        result=ProductRangeWorkflow(factory).run(variables,analyze=args.analyze,prepare_sources=args.prepare_sources_only)
        sdk.save(directory/'range-result.safe.json',result)
        print(json.dumps(result))
        return 0 if result['status'] in {'completed','preflight_completed','source_prepared'} else 2


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ContractError,sdk.ContractError) as error:
        print(json.dumps({'status':'blocked','reason_code':error.code,'resume_requires_same_checkpoint':True}))
        raise SystemExit(2)
    except FileExistsError:
        print(json.dumps({'status':'blocked','reason_code':'clinical_checkpoint_locked_inspect_owner'}))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({'status':'blocked','reason_code':'clinical_sdk_operation_unconfirmed_inspect_checkpoint',
            'resume_requires_same_checkpoint':True}))
        raise SystemExit(2)
