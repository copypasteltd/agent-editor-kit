from __future__ import annotations
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from ai_ad_editor import schema_contract as contract
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project
from ai_ad_editor.validator import _schema_report,validate_project

ROOT=Path(__file__).resolve().parents[2]


def cli(*args):
    out=io.StringIO()
    with contextlib.redirect_stdout(out):code=main(list(map(str,args)))
    return code,json.loads(out.getvalue())


class BundledSchemaTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='schema-contract-');self.addCleanup(temp.cleanup);self.folder=Path(temp.name)
        self.root,self.project=create_project(self.folder/'project')

    def changed(self,edit):
        data,schema,_=contract.read_contract();edit(schema)
        path=self.folder/'changed.json';path.write_text(json.dumps(schema),encoding='utf-8')
        return mock.patch.multiple(contract,schema_path=lambda:path,SCHEMA_SHA256=hashlib.sha256(path.read_bytes()).hexdigest())

    def dated(self,value):
        project=copy.deepcopy(self.project);project['project']['created_at']=value;return project

    def test_contract_packaged_and_documented_bytes_match(self):
        raw,schema,formats=contract.read_contract()
        self.assertEqual(raw,(ROOT/'docs/specs/agent-project.schema.json').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),contract.SCHEMA_SHA256)
        self.assertEqual(formats,['date-time']);self.assertTrue(contract.probe()['ok'])
        self.assertEqual(contract.descriptor()['external_reference_retrieval'],'disabled')

    def test_real_cli_rejects_previously_accepted_invalid_date(self):
        self.project['project']['created_at']='this-is-not-a-date';path=self.root/'project.json'
        path.write_text(json.dumps(self.project),encoding='utf-8');before=path.read_bytes()
        code,report=cli('validate','--project',self.root)
        self.assertEqual(code,2,report);self.assertEqual(path.read_bytes(),before)
        self.assertTrue(any(x['code']=='SCHEMA_VALIDATION_FAILED' and x['path']=='project.created_at' for x in report['errors']))

    def test_calendar_and_offset_valid_dates(self):
        validator=contract.make_validator()
        for value in ('2024-02-29T12:00:00Z','2024-02-29t12:00:00z','2026-10-18T00:27:32.123456+08:00','2026-10-18T00:00:00-23:59'):
            project=self.dated(value)
            self.assertEqual(list(validator.iter_errors(project)),[],value)

    def test_overlay_enum_requires_an_explicit_native_pipeline_in_the_actual_schema(self):
        self.project['sequences'][0]['tracks'][0]['kind']='overlay'
        validator=contract.make_validator();self.assertTrue(list(validator.iter_errors(self.project)))
        self.project['settings']['pixel_pipeline']={'engine':'float32-native-v1',
            'working_signal':{'primaries':'bt709','transfer':'linear'},'output_signal':{'primaries':'bt709','transfer':'linear'},'sources':{}}
        self.assertEqual(list(validator.iter_errors(self.project)),[])

    def test_format_failure_cases_in_actual_validator(self):
        validator=contract.make_validator()
        for value in ('2025-02-29T12:00:00Z','2024-02-30T00:00:00Z','0000-01-01T00:00:00Z','2026-10-18','2026-10-18T24:00:00Z','2026-10-18T00:00:00+24:00','2026-10-18T00:00:00+08:60','2026-10-18T00:00:00Z\n','２０２６-10-18T00:00:00Z','2026-10-18T00:00:60Z'):
            self.assertTrue(list(validator.iter_errors(self.dated(value))),value)
        self.assertFalse(contract.descriptor()['leap_seconds_supported'])

    def test_nonstring_date_is_rejected_by_schema_type(self):
        errors=list(contract.make_validator().iter_errors(self.dated(123)))
        self.assertTrue(any(x.validator=='type' for x in errors))

    def test_missing_executor_is_error_and_preserves_semantic_diagnostics(self):
        self.project['schema_version']='unsupported'
        with mock.patch.dict('sys.modules',{'jsonschema':None}):
            report=validate_project(self.root,self.project)
        self.assertFalse(report['ok']);self.assertEqual(report['schema_engine'],'unavailable')
        self.assertTrue(any(x['code']=='SCHEMA_EXECUTOR_UNAVAILABLE' for x in report['errors']))
        self.assertGreater(len(report['errors']),1)
        self.assertFalse(any(x['code'].startswith('SCHEMA_') for x in report['warnings']))

    def test_missing_resource_never_searches_source_repo(self):
        with mock.patch.object(contract,'schema_path',return_value=self.folder/'missing.json'):
            errors,warnings,engine=_schema_report(self.project)
            self.assertEqual(errors[0]['code'],'SCHEMA_RESOURCE_MISSING');self.assertEqual(engine,'unavailable');self.assertEqual(warnings,[])
            self.assertFalse(contract.probe()['ok'])

    def test_changed_resource_is_rejected_by_real_bytes(self):
        path=self.folder/'tampered.json';path.write_bytes(contract.schema_path().read_bytes()+b' ')
        with mock.patch.object(contract,'schema_path',return_value=path):
            with self.assertRaisesRegex(AppError,'Schema'):contract.read_contract()
            self.assertEqual(contract.probe()['error']['code'],'SCHEMA_RESOURCE_CHANGED')

    def test_external_refs_cannot_retrieve_network_or_external_files(self):
        for key in ('$ref','$dynamicRef'):
            for value in ('https://example.invalid/schema.json','file:///E:/private.json','other.json'):
                with self.changed(lambda schema:schema.update({key:value})),mock.patch('socket.socket',side_effect=AssertionError('no sockets')):
                    self.assertEqual(contract.probe()['error']['code'],'SCHEMA_RESOURCE_INVALID')

    def test_unsupported_format_rejected_instead_of_silently_ignored(self):
        with self.changed(lambda schema:schema['$defs']['project']['properties']['created_at'].update(format='email')):
            self.assertEqual(contract.probe()['error']['code'],'SCHEMA_RESOURCE_INVALID')

    def test_invalid_meta_schema_has_structured_error(self):
        with self.changed(lambda schema:schema['$defs']['project']['properties']['created_at'].update(type='never-a-type')):
            self.assertEqual(contract.probe()['error']['code'],'SCHEMA_EXECUTION_FAILED')

    def test_show_and_validate_are_independent_of_cwd(self):
        previous=Path.cwd()
        try:
            os.chdir(self.folder)
            code,result=cli('schema','show');self.assertEqual(code,0,result)
            self.assertEqual(result['data']['schema'],contract.read_contract()[1])
            self.assertEqual(_schema_report(self.project),([],[],'jsonschema'))
        finally:os.chdir(previous)

    def test_export_dry_run_does_not_create_parent(self):
        path=self.folder/'not-created'/'schema.json'
        code,result=cli('schema','export','--output',path,'--dry-run')
        self.assertEqual(code,0,result);self.assertFalse(path.parent.exists())

    def test_export_exact_bytes_and_existing_target_preserved(self):
        path=self.folder/'contract.json';code,result=cli('schema','export','--output',path)
        self.assertEqual(code,0,result);original=path.read_bytes();self.assertEqual(original,contract.schema_path().read_bytes())
        code,result=cli('schema','export','--output',path);self.assertEqual(code,2,result)
        self.assertEqual(result['errors'][0]['code'],'OUTPUT_EXISTS');self.assertEqual(path.read_bytes(),original)

    def test_export_remote_target_rejected(self):
        code,result=cli('schema','export','--output','https://example.invalid/schema.json')
        self.assertNotEqual(code,0);self.assertFalse(result['ok'])

    def test_doctor_rejects_missing_executor_version_remains_diagnosable(self):
        with mock.patch.dict('sys.modules',{'jsonschema':None}):
            code,result=cli('doctor');self.assertEqual(code,2,result)
            self.assertFalse(result['data']['checks']['schema_validation']['ok'])
            code,result=cli('version');self.assertEqual(code,0,result)
            self.assertFalse(result['data']['schema_validation']['ok'])
