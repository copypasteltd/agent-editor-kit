"""Derive immutable kit mechanics from the previous verified local delivery."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('publish_hdr_metadata_20261028.py','publish_chromatic_20261028.py'),
                      ('verify_hdr_metadata_kit_20261028.py','verify_chromatic_kit_20261028.py')]:
    s=(ROOT/'scripts'/source).read_text('utf8')
    for a,b in [('native-hdr-metadata','native-chromatic'),('0.1.44','0.1.45'),('r45','r46'),('134','136'),('133','135'),('==83','==84'),('skill_files=83','skill_files=84'),
                ('native_hdr10_static_metadata','native_chromatic_adaptation'),('declared-hdr10-static-sei-v1','explicit-white-Bradford-float32-v1'),
                ('native-chromatic-20261028-r2/editable-hdr10.aevpkg.zip','native-chromatic-20261028-r3/editable-chromatic.aevpkg.zip')]:s=s.replace(a,b)
    s=s.replace("assert '-x265-params' in plan['plan']['command'] and plan['plan']['encoder']['hdr10']==load(ROOT/'docs/assets/native-chromatic-20261028-r2/declaration.json')",
        "assert load(project/'project.json')['settings']['pixel_pipeline']['working_signal']==dict(primaries='aces-ap1',transfer='linear',white_xy=[.32168,.33767])\n    assert plan['plan']['command']")
    s=s.replace('portable_hdr10_declaration_validated=True','portable_white_signal_validated=True').replace('installed HDR10 plan','installed chromatic plan')
    (ROOT/'scripts'/target).write_text(s,encoding='utf8',newline='\n')
p=ROOT/'scripts/package_community_skill.py';s=p.read_text('utf8')
assert "'HDR_METADATA.md', 'CHROMATIC_ADAPTATION.md'" not in s
s=s.replace("'HDR_METADATA.md',","'HDR_METADATA.md', 'CHROMATIC_ADAPTATION.md',",1);p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'docs/product/CHROMATIC_ADAPTATION.md';s=p.read_text('utf8').replace('native-chromatic-20261028-r1/','native-chromatic-20261028-r3/')
s=s.replace('Inspect `delivery.pixel_pipeline.source_receipts` and\n`last_output_color_boundary` in the actual render manifest.',
    'Inspect `delivery.pixel_pipeline.source_receipts.<asset_id>.color_boundary`\nfor the actual source-to-working transform. The final declared output signal is\nin `delivery.pixel_pipeline.output_signal`; integer-boundary clipping is counted\nin `delivery.pixel_pipeline.transport.clipped_RGB_components`.')
p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'.gitattributes';s=p.read_text('utf8')
s+='\n# Preserve actual reference-white evidence and media bytes.\ndocs/validation/evidence/native-chromatic-20261028-r1/** -text -whitespace\ndocs/assets/native-chromatic-20261028-*/** -text -whitespace\ndocs/product/chromatic-capabilities-cli-0.1.45.json -text -whitespace\nscripts/*chromatic*20261028.py text eol=lf\ndocs/product/CHROMATIC_ADAPTATION.md text eol=lf\ndocs/releases/CLI_0.1.45_LOCAL.md text eol=lf\ndocs/validation/明确白点色适应实测_2026-10-28.md text eol=lf\n'
p.write_text(s,encoding='utf8',newline='\n')
print('Prepared r46 kit mechanics and exact-byte evidence attributes.')
