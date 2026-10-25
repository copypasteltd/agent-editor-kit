"""Verified URI-only relocation of semantic data; external runtimes stay pinned."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .project import asset_map
from .rights import load_ledger, record_for, revise_record
from .semantic_contract import fingerprint
from .utils import sha256_bytes


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _data(root, project):
    from .semantic import read_index_payload, registry
    from .semantic_decision import load_profile

    registered = registry(project)
    indexes, calibrations = registered.get('indexes', []), registered.get('calibrations', [])
    if any(not isinstance(r.get('index_id'), str) for r in indexes):
        raise ValueError('Semantic index ID is missing')
    manifests = {r['index_id']: read_index_payload(root, project, r['index_id'])[0] for r in indexes}
    if len(manifests) != len(indexes):
        raise ValueError('Duplicate semantic index registrations')
    profiles = {}
    for record in calibrations:
        ident = record.get('calibration_id')
        if (not isinstance(ident, str) or ident in profiles or record.get('index_id') not in manifests
                or 'kind' not in record):
            raise ValueError('Missing, duplicate or orphan semantic calibration')
        profiles[ident] = load_profile(root, project, ident, manifests[record['index_id']], kind=record['kind'])
    assets, ledger = asset_map(project), load_ledger(root)
    # Index derivatives have independent active Rights Ledger bindings, just
    # like calibration evidence. This verifies provenance hashes, not a grant.
    for record in indexes:
        for ident in [record['asset_id'], record['vector_asset_id'], *record['frame_asset_ids']]:
            asset = assets[ident]
            rights = record_for(ledger, asset['rights_ref'])
            if not rights or rights.get('sha256') != asset['sha256']:
                raise ValueError('Semantic index rights/hash binding is missing')
    return registered, manifests, profiles


def prepare(root, original, packaged):
    """Check original bindings before deriving any relocated metadata in memory.

    Preserving an owned relative namespace needs no hash changes at all. An
    external source is copied into the package; only URI-bearing index metadata
    and its dependent profile fingerprints then change. Vectors, sampled times,
    dataset bytes, observations, fit, device and adapter pins remain unchanged.
    """
    from .semantic import registry

    registered, manifests, profiles = _data(root, original)
    indexes, calibrations = registered.get('indexes', []), registered.get('calibrations', [])
    summary = dict(indexes=[], calibrations=[], runtime_verification='not_performed',
        external_native_runtimes='not_bundled; original pins retained; search verifies them',
        new_model_forwards=0)
    if not indexes and not calibrations:
        return {}, None, summary
    before_assets, after_assets = asset_map(original), asset_map(packaged)
    after_registry = registry(packaged)
    ledger = copy.deepcopy(load_ledger(root))
    rewrites, ledger_changed, relocated = {}, False, {}

    def publish(asset_id, value):
        nonlocal ledger_changed
        before, after = before_assets[asset_id], after_assets[asset_id]
        content = _json(value)
        digest = 'sha256:' + sha256_bytes(content)
        existing = record_for(ledger, before['rights_ref'])
        if not existing or existing.get('sha256') != before['sha256']:
            raise ValueError('Semantic derived asset rights/hash binding is missing')
        after['sha256'] = digest
        rewrites[after['uri']] = content
        revise_record(ledger, before['rights_ref'], dict(sha256=digest, evidence=after['uri']),
            reason='Verified URI-only project-package relocation; model/vector/data/fit unchanged',
            actor='convert.export')
        ledger_changed = True
        return digest

    for record in after_registry.get('indexes', []):
        old = manifests[record['index_id']]
        manifest = copy.deepcopy(old)
        for source in manifest['sources']:
            source['uri'] = after_assets[source['asset_id']]['uri']
        for row in manifest['rows']:
            row['source_uri'] = after_assets[row['asset_id']]['uri']
            row['preview_uri'] = after_assets[row['preview_asset_id']]['uri']
        manifest['vectors']['uri'] = after_assets[record['vector_asset_id']]['uri']
        changed = manifest != old
        if changed:
            manifest['fingerprint'] = fingerprint({k:v for k,v in manifest.items() if k != 'fingerprint'})
            record['manifest_sha256'] = publish(record['asset_id'], manifest)
            record['sha256'] = fingerprint({k:v for k,v in record.items() if k != 'sha256'})
        relocated[record['index_id']] = manifest
        summary['indexes'].append(dict(index_id=record['index_id'], uri_rewritten=changed,
            old_fingerprint=old['fingerprint'], fingerprint=manifest['fingerprint'],
            vector_sha256_unchanged=old['vectors']['sha256'] == manifest['vectors']['sha256']))
    for record in after_registry.get('calibrations', []):
        old = profiles[record['calibration_id']]
        profile = copy.deepcopy(old)
        profile['index_fingerprint'] = relocated[record['index_id']]['fingerprint']
        changed = profile != old
        if changed:
            profile['fingerprint'] = fingerprint({k:v for k,v in profile.items() if k != 'fingerprint'})
            record['profile_sha256'] = publish(record['asset_id'], profile)
            record['sha256'] = fingerprint({k:v for k,v in record.items() if k != 'sha256'})
        summary['calibrations'].append(dict(calibration_id=record['calibration_id'],
            index_binding_rewritten=changed, cutoff=profile['fit']['cutoff'],
            fit_and_observations_unchanged=profile['fit'] == old['fit'] and profile['observations'] == old['observations'],
            dataset_sha256_unchanged=profile['dataset_sha256'] == old['dataset_sha256']))
    if rewrites:
        packaged.setdefault('provenance', {}).setdefault('change_log', []).append(dict(
            command='convert.export.semantic-uri-relocation', scope='URI bindings only',
            indexes=summary['indexes'], calibrations=summary['calibrations']))
    return rewrites, ledger if ledger_changed else None, summary


def verify(root: Path, project):
    """Verify imported data without loading the optional external model runtime."""
    from .semantic import registry
    from .semantic_contract import local_file
    from .semantic_sampling import owned

    registered = registry(project)
    indexes, calibrations = registered.get('indexes', []), registered.get('calibrations', [])
    if not indexes and not calibrations:
        return dict(indexes=0, calibrations=0, runtime_verified=False, new_model_forwards=0)
    for asset in project.get('assets', []):
        raw = Path(asset['uri'])
        if raw.is_absolute() or raw.drive:
            raise ValueError('Semantic package assets must use package-relative paths')
        owned(root, local_file(raw, root=root))
    _data(root, project)
    return dict(indexes=len(indexes), calibrations=len(calibrations),
        runtime_verified=False, native_runtime='external pins preserved; checked only when used',
        new_model_forwards=0)
