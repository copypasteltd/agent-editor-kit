"""Prepare explicit HLG black schema, honest capability extensions and captures."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'product/src/ai_ad_editor/agent-project.schema.json';d=json.loads(p.read_bytes());signal=d['$defs']['nativeFloatSignal']
assert 'display_black_nits' not in signal['properties']
signal['properties']['display_black_nits']={'type':'number','minimum':0,'maximum':10}
signal['allOf'].append({'if':{'required':['display_black_nits']},'then':{'required':['reference_white_nits','display_peak_nits','system_gamma'],
    'properties':{'transfer':{'const':'hlg-bt2100'}}}})
payload=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8');p.write_bytes(payload);(ROOT/'docs/specs/agent-project.schema.json').write_bytes(payload)
p=ROOT/'product/src/ai_ad_editor/schema_contract.py';s=p.read_text('utf8')
s,n=re.subn(r'cfcb772e180c432515d92045ceab39b21edc541b0cc3e4684ac9bc9de5d72f39',hashlib.sha256(payload).hexdigest(),s);assert n==1;p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'product/src/ai_ad_editor/capabilities.py';s=p.read_text('utf8')
replacements={
    'BT709_relative_delivery_not_HDR_or_ICC':'HDR_whites_ICC_extensions_have_separate_explicit_signal_contracts',
    'not_yet_timeline_render_preview_or_cache_backend':'intermediate_bundle_storage_not_timeline_audio_or_encoded_movie',
    'relative_D65_only_no_absolute_nits_ICC_or_HDR':'HDR_signals_require_complete_JSON_descriptors_and_explicit_nits',
    'no_ICC_dynamic_metadata_or_DolbyVision':'explicit_RGB_ICC_sources_use_native_icc_source_profiles_no_dynamic_metadata_or_DolbyVision',
    'HLG_ideal_zero_black_only_explicit_peak_and_gamma':'HLG_explicit_black_lift_uses_native_hlg_black_level_with_peak_and_gamma',
    'relative_D65_not_HDR_or_ICC':'SDR_review_output_of_explicit_HDR_white_ICC_source_extensions_not_HDR_monitor_acceptance',
    'explicit_D65_relative_colour_signals':'explicit_relative_RGB_CLI_and_API_HDR_nit_white_signals',
}
for old,new in replacements.items():assert old in s;s=s.replace(old,new)
needle="            'native_icc_source_profiles': {";assert needle in s
s=s.replace(needle,"""            'native_hlg_black_level': {
                'status':'implemented_with_limits','protocol':'explicit-HLG-display-black-float32-v1',
                'selection':'HLG source/output signal display_black_nits with reference_white_nits,display_peak_nits,system_gamma',
                'features':['explicit_BT2100_3_HLG_user_black_lift_and_inverse','RGB_coupled_OOTF_not_per_channel_gamma',
                    'declared_0_to_10_nit_black_with_beta_less_than_one','zero_black_legacy_bits_and_metadata_retained',
                    'independent_alpha_and_reference_nit_units','below_black_output_reject_or_explicit_counted_clip',
                    'source_working_output_previews_bundles_and_portable_project_signals',
                    'source_target_beta_and_domain_policy_receipts'],
                'limits':['CPU_tiled_transfer_math_supported_composition_GPU_selected_separately',
                    'explicit_BT2020_D65_HLG_nominal_0_to_1_inputs_not_subblack_PLUGE_input_acceptance',
                    'black_luminance_is_author_declaration_not_measured_display_calibration',
                    'unrepresentable_below_black_components_and_roundoff_require_explicit_clip_if_not_rejected',
                    'surface_HDR_uses_complete_source_working_signal_JSON_descriptors',
                    'no_dynamic_metadata_BT2390_perceptual_gamut_or_natural_HDR_monitor_acceptance'],
            },
"""+needle,1);p.write_text(s,encoding='utf8',newline='\n')
for old,new in [('test_icc_20261028.py','test_hlg_black_20261028.py'),('build_icc_20261028.py','build_hlg_black_20261028.py'),('activate_icc_20261028.py','activate_hlg_black_20261028.py')]:
    s=(ROOT/'scripts'/old).read_text('utf8').replace('native-icc','native-hlg-black').replace('0.1.46','0.1.47').replace('local.44','local.45')
    if old.startswith('test_'):
        s=s.replace("'icc':['test_icc_profiles']","'black':['test_float_hlg_black']").replace("default='icc'","default='black'").replace("'compat':['test_float_chromatic'","'compat':['test_icc_profiles','test_float_chromatic'")
    p=ROOT/'scripts'/new;assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
print('Prepared HLG black schema/capabilities and immutable source/build runners.')
