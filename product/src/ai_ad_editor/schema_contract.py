"""Byte-pinned packaged contract and explicitly offline validation executor."""
from __future__ import annotations
from functools import lru_cache
import hashlib
import importlib.metadata
import json
from pathlib import Path
from . import SCHEMA_VERSION
from .errors import AppError
from .rfc3339_dates import RFC3339_REGEX, validate_rfc3339

SCHEMA_SHA256='ce0bd45e94af4a4f75fd412332292d1c8127d5de38035a080ee78b5941e7f78a'
SCHEMA_NAME='agent-project.schema.json'


def schema_path():
    return Path(__file__).with_name(SCHEMA_NAME)


def read_contract():
    path=schema_path()
    try:
        with path.open('rb') as stream:data=stream.read(2*1024**2+1)
    except OSError as exc:
        raise AppError('SCHEMA_RESOURCE_MISSING','随包 Schema 无法读取；请重新离线安装',exit_code=10,path=str(path),cause=str(exc)) from exc
    if hashlib.sha256(data).hexdigest()!=SCHEMA_SHA256:
        raise AppError('SCHEMA_RESOURCE_CHANGED','随包 Schema 摘要不符；不搜索源码目录或降级',exit_code=10,path=str(path))
    try:
        schema=json.loads(data)
        formats=set()
        def inspect(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in {'$ref','$dynamicRef'} and (not isinstance(item,str) or not item.startswith('#')):
                        raise ValueError('external schema references forbidden')
                    if key=='format':formats.add(item)
                    inspect(item)
            elif isinstance(value,list):
                for item in value:inspect(item)
        inspect(schema)
        if formats-{'date-time'}:raise ValueError('unimplemented schema format')
        if schema['properties']['schema_version']['const']!=SCHEMA_VERSION:raise ValueError('contract version mismatch')
    except (ValueError,KeyError,TypeError) as exc:
        raise AppError('SCHEMA_RESOURCE_INVALID','随包 Schema 合同无效',exit_code=10,path=str(path),cause=str(exc)) from exc
    return data,schema,sorted(formats)


def descriptor():
    data,_,formats=read_contract()
    return {'source':'bundled','schema_version':SCHEMA_VERSION,'draft':'2020-12','path':str(schema_path()),
            'bytes':len(data),'sha256':'sha256:'+SCHEMA_SHA256,'formats':formats,'external_reference_retrieval':'disabled',
            'date_time_checker':'rfc3339-validator-0.1.4-python3-adaptation','leap_seconds_supported':False}


def _date_time(value):
    if not isinstance(value,str):return True
    normalized=value.upper()
    return bool(RFC3339_REGEX.fullmatch(normalized)) and validate_rfc3339(normalized)


@lru_cache(maxsize=4)
def _check_meta(data,executor):
    executor.check_schema(json.loads(data))


def make_validator():
    data,schema,_=read_contract()
    try:
        from jsonschema import Draft202012Validator, FormatChecker, SchemaError
        from referencing import Registry
        from referencing.exceptions import NoSuchResource
    except ImportError as exc:
        raise AppError('SCHEMA_EXECUTOR_UNAVAILABLE','缺少声明的本地 jsonschema/referencing 依赖；请离线重装，校验不会降级为成功',
                       exit_code=10,path='schema',cause=str(exc)) from exc
    def denied(uri):
        raise NoSuchResource(ref=uri)
    checker=FormatChecker(formats=[])
    checker.checks('date-time')(_date_time)
    try:
        _check_meta(data,Draft202012Validator)
        return Draft202012Validator(schema,format_checker=checker,registry=Registry(retrieve=denied))
    except (ValueError,TypeError,SchemaError) as exc:
        raise AppError('SCHEMA_EXECUTION_FAILED','机器 Schema 执行器初始化失败',exit_code=10,path='schema',cause=str(exc)) from exc


def probe():
    try:
        result=descriptor();make_validator()
        versions={name:importlib.metadata.version(name) for name in ('jsonschema','attrs','jsonschema-specifications','referencing','rpds-py')}
        return {'ok':True,**result,'executor':'jsonschema','dependencies':versions}
    except (AppError,importlib.metadata.PackageNotFoundError) as exc:
        error=exc.as_dict() if isinstance(exc,AppError) else {'code':'SCHEMA_EXECUTOR_UNAVAILABLE','message':str(exc)}
        return {'ok':False,'executor':'unavailable','error':error}


def export_contract(output,*,dry_run=False):
    data,_,_=read_contract();path=Path(output)
    if path.exists():raise AppError('OUTPUT_EXISTS','Schema 导出不覆盖已有文件',exit_code=2,path=str(path))
    if dry_run:return descriptor()
    created=False
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            created=True;stream.write(data)
    except OSError as exc:
        if created:path.unlink(missing_ok=True)
        raise AppError('OUTPUT_WRITE_FAILED','Schema 无法写入新本地文件',exit_code=2,path=str(path),cause=str(exc)) from exc
    except BaseException:
        if created:path.unlink(missing_ok=True)
        raise
    return descriptor()
