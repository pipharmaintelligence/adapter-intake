"""Inspect exact runtime-staged bytes against Core's hash-bound output DTO."""
import hashlib
import json
from pathlib import Path
from jsonschema.validators import validator_for
if __package__:
    from .contracts_v0_1_11 import ASSET_KEY, VERSION, SCHEMA, ContractError, require
    from .rendering_v0_1_11 import validate_result
else:
    from contracts_v0_1_11 import ASSET_KEY, VERSION, SCHEMA, ContractError, require
    from rendering_v0_1_11 import validate_result


def _no_external_refs(value):
    if isinstance(value,dict):
        for key,child in value.items():
            if key in {'$ref','$dynamicRef','$recursiveRef'}:
                require(isinstance(child,str) and child.startswith('#'),'clinical_output_external_schema_ref_forbidden')
            _no_external_refs(child)
    elif isinstance(value,list):
        for child in value:
            _no_external_refs(child)


def inspect_staged_payload(staged_payload, schema_contract):
    """No transport, credentials, storage writes, provider calls or value-bearing errors."""
    path=Path(staged_payload);checksum=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            checksum.update(chunk)
    pointer=schema_contract.get('pointer',{});document=schema_contract.get('schema',{})
    report={'status':'failed','payload_schema_version':SCHEMA,
        'node_schema_version':pointer.get('schema_version','unknown'),
        'node_schema_sha256':pointer.get('schema_sha256',''),
        'payload_sha256':checksum.hexdigest(),'records_inspected':0,'records_failed':0,
        'error_count':0,'errors':[],'errors_truncated':False}
    def error(code,index=None):
        report['error_count']+=1
        if len(report['errors'])<100:
            report['errors'].append({'field':'record','keyword':code,'expected':'clinical_output_dto',
                **({'record_index':index} if index is not None else {})})
        else:report['errors_truncated']=True
    try:
        encoded=(json.dumps(document,ensure_ascii=False,indent=2,separators=(',',': '))+'\n').encode('utf-8')
        require(hashlib.sha256(encoded).hexdigest()==pointer.get('schema_sha256'),'clinical_output_node_schema_hash_mismatch')
        require(document.get('metadata',{}).get('version')==pointer.get('schema_version'),'clinical_output_node_schema_version_mismatch')
        schema=document['results']['contract'];_no_external_refs(schema)
        validator_class=validator_for(schema);validator_class.check_schema(schema);validator=validator_class(schema)
    except Exception as exc:
        error(exc.code if isinstance(exc,ContractError) else 'clinical_output_node_schema_invalid');return report
    def inspect(record,index):
        report['records_inspected']+=1
        before=report['error_count']
        try:
            require(isinstance(record,dict) and record.get('asset')==ASSET_KEY+'@'+VERSION,'clinical_output_asset_mismatch')
            for issue in validator.iter_errors(record):
                error('json_schema_'+str(issue.validator),index)
            validate_result(record)
        except Exception as exc:
            error(exc.code if isinstance(exc,ContractError) else 'clinical_output_record_invalid',index)
        if report['error_count']>before:report['records_failed']+=1
    try:
        def pairs(entries):
            value={}
            for key,item in entries:
                require(key not in value,'clinical_output_duplicate_json_key');value[key]=item
            return value
        if path.suffix.lower()=='.jsonl':
            with path.open(encoding='utf-8-sig') as stream:
                for index,line in enumerate(stream):
                    if line.strip():inspect(json.loads(line,object_pairs_hook=pairs),index)
        else:
            value=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
            records=value.get('records') if isinstance(value,dict) and 'records' in value else [value]
            require(isinstance(records,list),'clinical_output_records_invalid')
            for index,record in enumerate(records):inspect(record,index)
    except Exception as exc:
        error(exc.code if isinstance(exc,ContractError) else 'clinical_output_json_invalid')
    if not report['records_inspected']:error('clinical_output_records_empty')
    if not report['error_count']:report['status']='passed'
    return report
