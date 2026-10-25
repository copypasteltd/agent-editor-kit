"""Freeze calibration, independent query evaluation and unchanged old regressions before inference."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/validation/evidence/semantic-decision-20261025-r1/frozen'
ASSETS = ROOT/'docs/assets/semantic-decision-20261025-r1'
DATA = Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/Lib/site-packages/skimage/data')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')


def main():
    OUT.mkdir(parents=True, exist_ok=False); ASSETS.mkdir(parents=True, exist_ok=False)
    old_path = ROOT/'docs/validation/evidence/semantic-20261025-r1/benchmark-frozen/truth.json'
    old = json.loads(old_path.read_bytes())
    entries = [dict(a) for a in old['assets'] if a['kind'] == 'image']
    docs = {n.name: ast.get_docstring(n) for n in ast.parse((DATA/'_fetchers.py').read_text('utf-8')).body
            if isinstance(n, ast.FunctionDef)}
    for ident, name, creator in [('asset_j3', 'brick.png', 'CC0 Textures'),
                                  ('asset_k8', 'horse.png', 'Andreas Preuss (marauder)')]:
        path = ASSETS/name; shutil.copyfile(DATA/name, path)
        entries.append(dict(asset_id=ident, path=path.relative_to(ROOT).as_posix(), kind='image',
            sha256=sha(path), creator=creator, license_spdx='CC0-1.0',
            source_url='https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.'+path.stem,
            local_upstream_docstring=docs[path.stem]))
    # Calibration and holdout wording are distinct. They share a small familiar
    # image library: this is not an unseen-image or natural-action benchmark.
    classes = [
        ('asset_a7', 'black and white photo of a man with a camera', '黑白照片里的男人和相机',
         'a monochrome photographer outdoors', '户外摄影师的黑白影像'),
        ('asset_b4', 'a coffee cup and saucer viewed from above', '俯拍咖啡杯与杯碟',
         'latte art inside a ceramic coffee cup', '陶瓷咖啡杯里的拉花'),
        ('asset_c2', 'the face of a brown tabby cat', '棕色虎斑猫的脸',
         'a furry domestic kitten with striped markings', '带条纹的毛茸茸家猫'),
        ('asset_d9', 'a portrait in an orange astronaut suit', '橙色宇航服的人物肖像',
         'an astronaut posing in front of a flag', '站在旗帜前的航天员'),
        ('asset_e3', 'dense blades of lawn grass', '密集的草坪草叶',
         'a detailed patch of wild grass texture', '野草表面的细节纹理'),
        ('asset_f8', 'a close texture of loose gravel', '松散碎石的近景纹理',
         'rough pebbles covering the ground', '铺满地面的粗糙小石块'),
        ('asset_g5', 'a blurred photograph of an analog clock', '模糊的指针钟表照片',
         'numbers around a round clock dial', '圆形表盘周围的数字'),
        ('asset_h6', 'a telescope view of many distant galaxies', '望远镜中的许多遥远星系',
         'a deep space astronomical photograph', '深空天文摄影'),
        ('asset_j3', 'a close texture of a brick wall', '砖墙表面的近距离纹理',
         'rows of rectangular masonry bricks', '成排的矩形砌筑砖块'),
        ('asset_k8', 'a black and white horse silhouette', '黑白马匹剪影',
         'the side profile of a horse in silhouette', '侧面的马形轮廓'),
    ]
    calibration, heldout = [], []
    relevant = lambda ident: [ident, 'asset_i1'] if ident == 'asset_c2' else [ident]
    for index, (ident, en, zh, test_en, test_zh) in enumerate(classes):
        for language, text, target in [('en', en, calibration), ('zh', zh, calibration),
                                       ('en', test_en, heldout), ('zh', test_zh, heldout)]:
            target.append(dict(id=('c' if target is calibration else 'h')+f'pos{index:02}'+language,
                text=text, expected_asset_ids=relevant(ident), group='positive'))
    absent_calibration = [
        ('a red racing car on a road', '公路上的红色赛车'),
        ('a golden retriever dog', '一只金毛寻回犬'),
        ('ocean waves breaking on a beach', '拍打沙滩的海浪'),
        ('a grand piano in a concert hall', '音乐厅里的三角钢琴'),
        ('a forest beside a clear lake', '清澈湖泊旁边的树林'),
        ('a bowl filled with fresh fruit', '装满新鲜水果的碗'),
        ('a bicycle parked beside a building', '停在建筑旁的自行车'),
        ('an airplane flying in the sky', '天空中飞行的飞机'),
        ('a microphone in a recording studio', '录音棚里的麦克风'),
        ('a surgeon operating in a hospital', '医院里正在手术的外科医生'),
    ]
    absent_holdout = [
        ('an elephant standing in a savanna', '草原上站立的大象'),
        ('penguins walking on ice', '冰面上行走的企鹅'),
        ('a city skyline illuminated at night', '夜间亮灯的城市天际线'),
        ('an octopus swimming underwater', '水下游动的章鱼'),
        ('a sailing boat on the sea', '海面上的帆船'),
        ('a pizza topped with tomatoes and cheese', '番茄芝士披萨'),
        ('snow covered mountain peaks', '白雪覆盖的山峰'),
        ('an empty basketball court', '空旷的篮球场'),
        ('an acoustic guitar leaning on a wall', '靠在墙边的木吉他'),
        ('a waterfall descending into a river', '落入河流的瀑布'),
    ]
    for target, definitions, prefix in [(calibration, absent_calibration, 'c'), (heldout, absent_holdout, 'h')]:
        for index, (en, zh) in enumerate(definitions):
            for language, text in [('en', en), ('zh', zh)]:
                target.append(dict(id=prefix+f'out{index:02}'+language, text=text,
                                   expected_asset_ids=[], group='out_of_library'))
    for index, row in enumerate(classes):
        ident, en, zh, test_en, test_zh = row
        other = classes[(index+3) % len(classes)]
        for language, positive, negative in [('en', test_en, other[1]), ('zh', test_zh, other[2])]:
            text = positive+', not '+negative if language == 'en' else positive+'，不是'+negative
            heldout.append(dict(id=f'hneg{index:02}'+language, text=text,
                expected_asset_ids=relevant(ident), group='negation'))
    raw_calibration = dict(format='agent-semantic-calibration-set-v1',
        scope='Eleven familiar static images, ten visual classes; English/Chinese text, no natural actions, audio or identity.',
        queries=[{k:v for k,v in r.items() if k != 'group'} for r in calibration])
    save(OUT/'calibration.json', raw_calibration)
    save(OUT/'heldout-labels.json', dict(queries=heldout))
    save(OUT/'heldout-queries.json', dict(queries=[dict(id=r['id'], text=r['text']) for r in heldout]))
    regression = []
    for row in old['queries']:
        regression.append(dict(id=row['id'], text=row['text'], expected_asset_ids=row['relevant_image_ids'],
                               group=row['group']))
    save(OUT/'regression-labels.json', dict(queries=regression))
    save(OUT/'regression-queries.json', dict(queries=[dict(id=r['id'], text=r['text']) for r in regression]))
    protocol = dict(format='semantic-decision-frozen-evaluation-v1', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        assets=entries, calibration_sha256=sha(OUT/'calibration.json'), heldout_sha256=sha(OUT/'heldout-labels.json'),
        regression_sha256=sha(OUT/'regression-labels.json'), original_truth_sha256=sha(old_path),
        threshold_algorithm='negative-order-statistic-strict-greater-v1', false_accept_rate=.05,
        minimum_calibration_correct_positive_coverage=.75,
        gates=dict(heldout_positive_correct_coverage=.75, heldout_out_of_library_rejection=.90,
                   heldout_negation_correct_coverage=.80, original_positive_correct_coverage=.75,
                   original_negation_correct=2, original_out_of_library_rejected=2),
        heldout_protocol='Run once after implementation/calibration. Do not tune on heldout. Retain every failure.',
        model_inputs='Only query clauses and image pixels; calibration labels stay in the controller.',
        caveats=['Shared familiar images; independent query wording is not unseen image or training independence.',
                 'Empirical cutoff is index/filter/device specific and is not a semantic probability or universal rejection guarantee.',
                 'Exclusions compare clause scores on sampled frames, not object-presence detectors.',
                 'Whole G26 including actions, audio, identity and recommendation remains open.'],
        generator_sha256=sha(Path(__file__)))
    save(OUT/'protocol.json', protocol)
    save(ASSETS/'SOURCE.json', dict(assets=entries, original_source='../semantic-20261025-r1/SOURCE.json'))
    (OUT/'executed-freezer.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(status='frozen_before_new_model_execution', calibration=len(calibration), heldout=len(heldout),
        regression=len(regression), assets=len(entries), protocol_sha256=sha(OUT/'protocol.json')), ensure_ascii=False))


if __name__ == '__main__':
    main()
