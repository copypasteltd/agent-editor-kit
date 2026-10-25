"""Project-bound CLI for offline semantic visual retrieval."""
from __future__ import annotations

from .artifact_locks import verification_scope, verification_summary
from .project import load_project
from .execution_control import operation_budget
from . import semantic
from .semantic_contract import verify_adapter

ACTIONS=('adapter-register','adapter-list','adapter-inspect','index','index-list','verify','calibrate','calibration-list','search')
READ_ONLY_ACTIONS=('adapter-list','adapter-inspect','index-list','verify','calibration-list','search')


def execution(parser):
    parser.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    parser.add_argument('--device-index',type=int,default=0)
    parser.add_argument('--batch-size',type=int,default=8)
    parser.add_argument('--timeout-seconds',type=float,default=600)
    parser.add_argument('--cancel-file')


def add_parser(subs,leaf):
    parser=subs.add_parser('semantic',help='已有本地图文模型的视觉向量索引和中英自然语言/参考图查询')
    actions=parser.add_subparsers(dest='action',required=True)
    for action in ACTIONS:
        p=leaf(actions.add_parser(action))
        p.add_argument('--project',required=True)
        if action in ('adapter-register','adapter-inspect','index'):p.add_argument('--adapter-id',required=True)
        if action in ('index','verify','calibrate','search'):p.add_argument('--index-id',required=True)
        if action=='adapter-register':
            p.add_argument('--python-executable',required=True)
            p.add_argument('--model-path',required=True)
            p.add_argument('--evidence',required=True)
            p.add_argument('--creator',required=True)
            p.add_argument('--license-spdx',required=True)
            p.add_argument('--verification-status',choices=('unverified','verified','restricted'),default='unverified')
            p.add_argument('--permitted-use',action='append')
            p.add_argument('--threads',type=int,default=4)
            p.add_argument('--timeout-seconds',type=float,default=600)
            p.add_argument('--cancel-file')
        if action=='index':
            group=p.add_mutually_exclusive_group(required=True)
            group.add_argument('--asset-id',action='append')
            group.add_argument('--all-visual-assets',action='store_true')
            p.add_argument('--sample-interval-seconds',type=float,default=2.)
            p.add_argument('--max-samples-per-asset',type=int,default=128)
            execution(p)
        if action in ('adapter-list','adapter-inspect','verify'):
            p.add_argument('--timeout-seconds',type=float,default=600)
            p.add_argument('--cancel-file')
        if action=='search':
            group=p.add_mutually_exclusive_group(required=True)
            group.add_argument('--query')
            group.add_argument('--queries-file')
            group.add_argument('--image')
            p.add_argument('--limit',type=int,default=5)
            p.add_argument('--min-score',type=float,default=-1.)
            p.add_argument('--kind',choices=('image','video'))
            p.add_argument('--all-samples',action='store_true',help='返回各采样点；默认每资产只保留最高相似度候选')
            p.add_argument('--query-mode',choices=('clauses','raw'),default='clauses',help='默认解析有界否定；raw 仅用于原始整句排名/历史复现')
            p.add_argument('--calibration-id',help='使用当前索引/类型/设备绑定的经验拒识档案')
            execution(p)
        if action=='calibrate':
            p.add_argument('--calibration-id',required=True)
            p.add_argument('--input',required=True)
            p.add_argument('--kind',choices=('image','video'))
            p.add_argument('--false-accept-rate',type=float,default=.05)
            p.add_argument('--minimum-coverage',type=float,default=.75)
            execution(p)


def command(args,envelope):
    with verification_scope():
        root,project=load_project(args.project)
        action=args.action
        if action=='adapter-register':
            data=semantic.register(root,project,adapter_id=args.adapter_id,python_executable=args.python_executable,
                model_path=args.model_path,evidence=args.evidence,creator=args.creator,license_spdx=args.license_spdx,
                verification_status=args.verification_status,permitted_uses=args.permitted_use,threads=args.threads,
                timeout=args.timeout_seconds,cancel_file=args.cancel_file,dry_run=args.dry_run)
        elif action in ('adapter-list','adapter-inspect'):
            adapters=semantic.registry(project).get('adapters',[]) if action=='adapter-list' else [semantic.item(project,'adapters',args.adapter_id)]
            with operation_budget(args.timeout_seconds,args.cancel_file,root=root):
                data=dict(adapters=[dict(adapter=r,verification=verify_adapter(r)) for r in adapters],network='disabled')
        elif action=='index':
            data=semantic.build_index(root,project,index_id=args.index_id,adapter_id=args.adapter_id,asset_ids=args.asset_id,
                all_visual=args.all_visual_assets,interval=args.sample_interval_seconds,max_per_asset=args.max_samples_per_asset,
                device=args.device,device_index=args.device_index,batch_size=args.batch_size,timeout=args.timeout_seconds,
                cancel_file=args.cancel_file,dry_run=args.dry_run)
        elif action=='index-list':
            data=dict(indexes=semantic.registry(project).get('indexes',[]),verification='use semantic verify for current bytes',network='disabled')
        elif action=='calibration-list':
            data=dict(calibrations=semantic.registry(project).get('calibrations',[]),
                      verification='search --dry-run verifies the selected profile/index/source/model binding',network='disabled')
        elif action=='calibrate':
            from .semantic_decision import calibrate
            data=calibrate(root,project,index_id=args.index_id,calibration_id=args.calibration_id,input_path=args.input,
                kind=args.kind,false_accept_rate=args.false_accept_rate,minimum_coverage=args.minimum_coverage,
                device=args.device,device_index=args.device_index,batch_size=args.batch_size,
                timeout=args.timeout_seconds,cancel_file=args.cancel_file,dry_run=args.dry_run)
        elif action=='verify':
            with operation_budget(args.timeout_seconds,args.cancel_file,root=root):
                manifest,vectors,adapter=semantic.read_index(root,project,args.index_id)
            data=dict(index_id=args.index_id,verified=True,rows=len(vectors),source_assets=len(manifest['sources']),
                      adapter_sha256=adapter['sha256'],network='disabled')
        else:
            data=semantic.search(root,project,index_id=args.index_id,query=args.query,queries_file=args.queries_file,
                image=args.image,limit=args.limit,minimum=args.min_score,kind=args.kind,
                distinct_assets=not args.all_samples,device=args.device,device_index=args.device_index,batch_size=args.batch_size,
                timeout=args.timeout_seconds,cancel_file=args.cancel_file,dry_run=args.dry_run,
                calibration_id=args.calibration_id,query_mode=args.query_mode)
        data['verification_scope']=verification_summary()
        return envelope('semantic.'+action,args,data=data,status='planned' if args.dry_run else 'succeeded',
                        operation_id=data.get('operation_id'),warnings=data.get('warnings',[]))
