"""Versioned offline visual retrieval: model, vector and sampling contracts."""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

from .artifact_locks import artifact_entry
from .errors import AppError, argument_error
from .policy import require_local_reference
from .utils import sha256_bytes

ENGINE = 'transformers-siglip-local-v1'
PROTOCOL = 'agent-semantic-embedding-v1'
INDEX_FORMAT = 'agent-visual-semantic-index-v1'
PREPROCESSING = 'siglip-local-rgb-lowercase-pad64-no-truncation-v1'
MAX_ROWS = 4096
MAX_ASSETS = 512
DIMENSION = 768


def json_object(path: Path, *, max_bytes: int = 64*1024**2) -> dict:
    if path.stat().st_size > max_bytes:
        raise AppError('SEMANTIC_JSON_BUDGET', 'JSON 超出显式预算', exit_code=6, path=str(path))
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(path.read_text('utf-8-sig'), object_pairs_hook=pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        if not isinstance(value, dict):
            raise ValueError('Expected JSON object')
        return value
    except (ValueError, UnicodeError) as exc:
        raise AppError('SEMANTIC_JSON_INVALID', 'JSON 无效或含重复/非有限值', exit_code=6, path=str(path), cause=str(exc)) from exc


def fingerprint(value) -> str:
    return 'sha256:'+sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode('utf-8'))


def local_file(value, *, root: Path | None = None) -> Path:
    require_local_reference(str(value), field='semantic local file')
    raw = Path(value).expanduser()
    if root and not raw.is_absolute():
        raw = root/raw
    if str(raw).startswith('\\\\') or raw.is_symlink() or getattr(raw, 'is_junction', lambda: False)():
        raise argument_error('语义模型/媒体不能使用网络盘或文件链接', str(raw))
    # Check every existing ancestor before resolving so a parent junction cannot
    # disguise a different model tree or introduce unchecked code/resources.
    for ancestor in raw.absolute().parents:
        if ancestor.is_symlink() or getattr(ancestor, 'is_junction', lambda: False)():
            raise argument_error('语义资源路径不能穿越链接目录', str(ancestor))
    if not raw.is_file():
        raise AppError('SEMANTIC_FILE_MISSING', '需要已存在的本地普通文件', exit_code=3, path=str(raw))
    return raw.resolve()


def model_files(model: Path) -> list[Path]:
    try:
        require_local_reference(str(model), field='model_path')
        if not model.is_dir() or model.is_symlink() or getattr(model, 'is_junction', lambda: False)():
            raise ValueError('Model must be a local ordinary directory')
        paths = list(model.rglob('*'))
        if len(paths)>64 or any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in paths):
            raise ValueError('Linked/excessive model files')
        files = sorted(p for p in paths if p.is_file())
        allowed = {'.json', '.txt', '.md', '.safetensors', '.model'}
        if any(p.suffix.lower() not in allowed and p.name != '.gitattributes' for p in files):
            raise ValueError('Model directory contains code, executable or unsupported resources')
        required = {'config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','model.safetensors'}
        if not required.issubset({p.name for p in files if p.parent == model}):
            raise ValueError('Incomplete SigLIP safetensors model/processor')
        if {p.name for p in files if p.suffix=='.safetensors'} != {'model.safetensors'}:
            raise ValueError('Only a single explicitly inventoried safetensors checkpoint is supported')
        config = json_object(model/'config.json',max_bytes=1024**2)
        if config.get('model_type') != 'siglip' or config.get('auto_map') or config.get('custom_pipelines'):
            raise ValueError('Only standard Transformers SiglipModel architecture is supported')
        text, vision = config.get('text_config',{}),config.get('vision_config',{})
        if any(type(value) is not dict for value in (text,vision)):
            raise ValueError('Missing text/vision architecture')
        if (text.get('hidden_size',768) != DIMENSION or text.get('projection_size',768) != DIMENSION
                or vision.get('hidden_size',768) != DIMENSION or text.get('max_position_embeddings',64) != 64
                or vision.get('image_size',224) != 224):
            raise ValueError('This engine requires the explicit 768-dimensional, 224px, 64-token base profile')
        processor=json_object(model/'preprocessor_config.json',max_bytes=1024**2)
        if processor.get('image_processor_type') not in {'SiglipImageProcessor','SiglipImageProcessorFast'}:
            raise ValueError('Unexpected image preprocessor')
        for path in files:
            local_file(path)
            if path.suffix=='.json':
                value=json_object(path)
                if value.get('auto_map') or value.get('custom_pipelines'):
                    raise ValueError('Remote/custom model code is forbidden')
        return files
    except (OSError, ValueError, TypeError) as exc:
        raise AppError('SEMANTIC_MODEL_INVALID','本地图文模型不符合固定架构和资源契约',exit_code=10,cause=str(exc)) from exc


def implementation_files() -> list[Path]:
    return [Path(__file__).with_name(name) for name in ('semantic_contract.py','semantic_worker.py',
            'semantic.py','semantic_cli.py','semantic_sampling.py','artifact_locks.py','whisper_worker.py',
            'utils.py','policy.py','reverse_video_clock.py','community_device.py','media.py',
            'semantic_queries.py','semantic_decision.py','semantic_jobs.py','job_workspaces.py',
            'job_trees.py','native_process_job.py')]


def adapter_fingerprint(record: dict) -> str:
    fields=('adapter_id','engine','protocol','model_path','python_executable','threads','artifacts',
            'preprocessing','dimension','rights_ref','runtime_artifacts','runtime_versions','runtime_modules')
    return fingerprint({key:record.get(key) for key in fields})


def verify_adapter(record: dict) -> dict:
    try:
        if (record.get('engine')!=ENGINE or record.get('protocol')!=PROTOCOL
                or record.get('dimension')!=DIMENSION or record.get('preprocessing')!=PREPROCESSING
                or type(record.get('threads')) is not int or not 1<=record['threads']<=16
                or record.get('sha256')!=adapter_fingerprint(record)):
            raise ValueError('Adapter contract/fingerprint changed')
        expected={(str(p.resolve()),'model') for p in model_files(Path(record['model_path']))}
        expected|={(str(p.resolve()),'implementation') for p in implementation_files()}
        expected.add((str(local_file(record['python_executable'])),'python'))
        runtime=record['runtime_artifacts']
        if not isinstance(runtime,list) or not 1<=len(runtime)<=128 or any(row.get('role')!='runtime' for row in runtime):
            raise ValueError('Missing bounded native runtime inventory')
        expected|={(str(local_file(row['path'])),'runtime') for row in runtime}
        entries=record['artifacts']
        if not isinstance(entries,list) or len(entries)>200:
            raise ValueError('Invalid artifact inventory')
        actual={(row['path'],row['role']) for row in entries}
        if len(actual)!=len(entries) or not expected.issubset(actual) or len(actual-expected)!=1 or next(iter(actual-expected))[1]!='evidence':
            raise ValueError('Artifact closure changed')
        for row in entries:
            observed=artifact_entry(local_file(row['path']),row['role'])
            if observed!=row:
                raise ValueError('Pinned artifact bytes/hash changed: '+row['path'])
        return {'ok':True,'checked_files':len(entries),'network':'disabled'}
    except (AppError,OSError,KeyError,ValueError,TypeError,AttributeError) as exc:
        return {'ok':False,'code':'SEMANTIC_ADAPTER_INTEGRITY_FAILED','message':str(exc)}


def sample_times(duration: float, *, interval: float, per_asset: int) -> list[float]:
    if (type(duration) not in (int,float,Fraction) or type(interval) not in (int,float)
            or not math.isfinite(duration) or duration<=0 or not math.isfinite(interval) or interval<=0
            or type(per_asset) is not int or not 1<=per_asset<=128):
        raise argument_error('视频采样需有限正时长/间隔，单资产预算 1–128','sampling')
    step=Fraction(str(interval))
    count=max(1,math.ceil(Fraction(str(duration))/step))
    if count>per_asset:
        raise AppError('SEMANTIC_SAMPLE_BUDGET_EXCEEDED','完整声明的采样点超出单资产预算；请显式调整间隔或预算',exit_code=2)
    # Fixed start-of-bin source PTS, strictly before EOF, never rounded past it.
    return [float(index*step) for index in range(count)]


def check_vectors(value, rows: int, *, dimension: int=DIMENSION):
    import numpy as np
    if type(rows) is not int or not 1<=rows<=MAX_ROWS or dimension!=DIMENSION:
        raise AppError('SEMANTIC_VECTOR_INVALID','向量数量或维度超出契约',exit_code=6)
    array=np.asarray(value,dtype='<f4')
    if array.shape!=(rows,dimension) or not np.isfinite(array).all():
        raise AppError('SEMANTIC_VECTOR_INVALID','向量形状或有限性无效',exit_code=6)
    norms=np.linalg.norm(array.astype(np.float64),axis=1)
    if not np.all(np.abs(norms-1)<=2e-4):
        raise AppError('SEMANTIC_VECTOR_INVALID','向量必须是非零单位 float32',exit_code=6)
    return array


def rank(vectors, query, records: list[dict], *, limit: int, minimum: float=-1.,
         kind: str|None=None, distinct_assets: bool=True) -> list[dict]:
    import numpy as np
    if type(limit) is not int or not 1<=limit<=100 or type(minimum) not in (int,float) or not math.isfinite(minimum) or not -1<=minimum<=1:
        raise argument_error('limit 须为 1–100，min-score 须为 -1..1','semantic search')
    matrix=check_vectors(vectors,len(records))
    vector=check_vectors(np.asarray(query).reshape(1,-1),1)[0]
    if kind not in {None,'image','video'}:
        raise argument_error('检索类型须为 image/video','kind')
    scores=matrix.astype(np.float64)@vector.astype(np.float64)
    ordered=sorted(range(len(records)),key=lambda i:(-float(scores[i]),str(records[i]['asset_id']),records[i]['sample_seconds'],i))
    results=[];seen=set()
    for index in ordered:
        row=records[index]
        if (kind and row['kind']!=kind) or scores[index]<minimum or (distinct_assets and row['asset_id'] in seen):
            continue
        seen.add(row['asset_id'])
        results.append({**row,'row':index,'score':round(float(scores[index]),8),'score_kind':'cosine_similarity_not_probability',
                        'review_required':True})
        if len(results)==limit:break
    return results
