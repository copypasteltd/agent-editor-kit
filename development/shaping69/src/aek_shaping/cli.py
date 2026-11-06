"""Strict offline inspect/render requests and no-overwrite artifact publication."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .native import Engine, FontSpec, ShapingError, integer, require
from .layout import layout, selection, prefix_plan, Renderer
from .png import encode


def strict_json(raw):
    require(len(raw) <= 1024**2, 'TEXT_REQUEST_BUDGET', 'A text request may not exceed 1 MiB')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'TEXT_JSON_DUPLICATE', 'Duplicate object key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ShapingError('TEXT_JSON_NUMBER', 'Non-finite JSON numbers are not permitted')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShapingError('TEXT_JSON', 'Request is not valid UTF-8 JSON') from exc


def fields(value, allowed, required=()):
    require(isinstance(value, dict) and not set(value).difference(allowed) and set(required).issubset(value),
            'TEXT_REQUEST_FIELDS', 'Missing or unknown request fields')
    return value


def resolved(base, value):
    require(isinstance(value, str) and value and len(value) <= 4096, 'TEXT_REQUEST_PATH', 'An explicit local path is required')
    return (base / value).resolve()


def load_request(path, stack):
    path = Path(path).resolve()
    require(path.is_file() and path.stat().st_size <= 1024**2, 'TEXT_REQUEST_BUDGET', 'Missing or oversized text request')
    request = fields(strict_json(path.read_bytes()), {'format', 'runtime', 'text', 'fonts', 'layout', 'render', 'selection', 'reveal_end'},
                     {'format', 'runtime', 'text', 'fonts'})
    require(request['format'] == 'aek-shaping69-request-v1', 'TEXT_REQUEST_FORMAT', 'Unsupported development request format')
    engine = Engine(resolved(path.parent, request['runtime']))
    require(isinstance(request['fonts'], list) and 1 <= len(request['fonts']) <= 8,
            'TEXT_FONT_STACK', 'One to eight explicit fonts are required')
    fonts, total = [], 0
    for row in request['fonts']:
        fields(row, {'path', 'sha256', 'pixels', 'index', 'variations'}, {'path', 'sha256', 'pixels'})
        font_path = resolved(path.parent, row['path'])
        total += font_path.stat().st_size
        require(total <= 128 * 1024**2, 'TEXT_FONT_STACK_BUDGET', 'Combined font bytes exceed 128 MiB')
        spec = FontSpec(font_path, row['sha256'], row['pixels'], row.get('index', 0), dict(row.get('variations', {})))
        fonts.append(stack.enter_context(engine.font(spec)))
    options = fields(request.get('layout', {}), {'max_width', 'base', 'language', 'features', 'overflow', 'trim_line_end'})
    plan = layout(engine, request['text'], fonts, **options)
    rendering = fields(request.get('render', {}), {'padding', 'align', 'line_spacing', 'foreground', 'active'})
    chosen = fields(request.get('selection', {}), {'ranges', 'partial'})
    display = prefix_plan(plan, request['reveal_end']) if 'reveal_end' in request else plan
    selected = selection(display, chosen.get('ranges', []), partial=chosen.get('partial', 'strict'))
    return request, plan, display, selected, rendering


def publish_file(path, raw):
    path = Path(path).resolve()
    require(path.parent.is_dir() and not path.exists(), 'TEXT_OUTPUT_EXISTS', 'Output exists or its parent is missing')
    fd, name = tempfile.mkstemp(prefix=path.name + '.pending-', dir=path.parent)
    owned = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(owned, path)
        except FileExistsError as exc:
            raise ShapingError('TEXT_OUTPUT_EXISTS', 'Another writer created the output') from exc
    finally:
        owned.unlink(missing_ok=True)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def execute(action, request_path, output):
    output = Path(output).resolve()
    require(output.parent.is_dir() and not output.exists(), 'TEXT_OUTPUT_EXISTS', 'Output exists or its parent is missing')
    with ExitStack() as stack:
        request, plan, display, selected, rendering = load_request(request_path, stack)
        data = display.data()
        data['selection'] = {key: value for key, value in selected.items() if key != 'glyph_windows'}
        data['full_layout'] = dict(widths=[line.width for line in plan.lines], paragraph_bases=[line.base for line in plan.lines])
        if action == 'inspect':
            publish_file(output, json_bytes(data))
            return dict(status='passed', artifact=str(output), glyphs=sum(len(line.glyphs) for line in display.lines), formal_product_integrated=False)
        colors = {key: rendering[key] for key in ('foreground', 'active') if key in rendering}
        renderer = Renderer(plan, **{key: value for key, value in rendering.items() if key not in colors})
        rgba, measured = renderer.render(selected, display_plan=display, **colors)
        png = encode(renderer.width, renderer.height, rgba)
        proof = {key: value for key, value in measured.items() if key not in ('alpha', 'selected_alpha')}
        proof.update(format='aek-shaped-text-render-v1', native_versions=plan.engine.versions,
            source_sha256=hashlib.sha256(plan.source.encode('utf-8')).hexdigest(), png_sha256=hashlib.sha256(png).hexdigest(),
            rgba_sha256=hashlib.sha256(rgba).hexdigest(), revealed_end=display.revealed_end,
            actual_native_raster=True, formal_product_integrated=False)
        temporary = Path(tempfile.mkdtemp(prefix=output.name + '.pending-', dir=output.parent))
        try:
            (temporary / 'actual.png').write_bytes(png)
            (temporary / 'plan.json').write_bytes(json_bytes(data))
            (temporary / 'verification.json').write_bytes(json_bytes(proof))
            try:
                os.rename(temporary, output)  # Native Windows rename refuses an existing destination.
            except FileExistsError as exc:
                raise ShapingError('TEXT_OUTPUT_EXISTS', 'Another writer created the render directory') from exc
        finally:
            if temporary.exists():
                require(temporary.parent == output.parent and temporary.name.startswith(output.name + '.pending-'),
                        'TEXT_OUTPUT_OWNERSHIP', 'Refuse cleanup outside the owned temporary directory')
                shutil.rmtree(temporary)
        return dict(status='passed', artifact=str(output / 'actual.png'), verification=str(output / 'verification.json'),
                    width=renderer.width, height=renderer.height, formal_product_integrated=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'render'])
    parser.add_argument('--request', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        value = execute(args.action, args.request, args.output)
        print(json.dumps(dict(ok=True, **value), ensure_ascii=False))
        return 0
    except (ShapingError, OSError, TypeError, ValueError, KeyError) as exc:
        code = exc.code if isinstance(exc, ShapingError) else 'TEXT_REQUEST_IO' if isinstance(exc, OSError) else 'TEXT_REQUEST_VALUE'
        print(json.dumps(dict(ok=False, code=code, message=str(exc)), ensure_ascii=False))
        return 2
