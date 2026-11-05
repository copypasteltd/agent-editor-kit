"""Apply the complete delivery66 implementation batch before any tests run."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'product/src/ai_ad_editor'


def write(path, content):
    path.write_text(content, encoding='utf-8', newline='\n')


def main():
    project = SOURCE / 'project.py'
    text = project.read_text(encoding='utf-8')
    assert '_preflight_transaction_recovery' not in text
    candidate = (ROOT / 'docs/validation/recovery66_preflight_candidate.py').read_text(encoding='utf-8')
    replacements = '\n\n'.join(ast.get_source_segment(candidate, node)
        for node in ast.parse(candidate).body if isinstance(node, ast.FunctionDef))
    tree = ast.parse(text)
    old = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'recover_pending_transaction')
    lines = text.splitlines(keepends=True)
    text = ''.join(lines[:old.lineno - 1]) + replacements + '\n\n' + ''.join(lines[old.end_lineno:])
    begin = text.index('        for source in _transaction_metadata_files(root):')
    end = text.index('        journal = {', begin)
    text = text[:begin] + '''        # Bound the number of in-flight copies. All files are flushed before
        # the prepared journal is published; no durability barrier is removed.
        from concurrent.futures import ThreadPoolExecutor
        sources = _transaction_metadata_files(root)
        entries = []
        for index, source in enumerate(sources):
            relative, checked = _recovery_entry_path(root, source.relative_to(root).as_posix())
            entries.append((index, relative, checked))

        def backup_one(entry):
            index, relative, source = entry
            destination = backup_root / f'{index:04d}.bin'
            digest, size = hashlib.sha256(), 0
            with source.open('rb') as reader, destination.open('xb') as writer:
                while chunk := reader.read(1024 * 1024):
                    writer.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            return dict(path=relative,
                backup=f'operations/project-transaction-backups/{transaction_id}/{index:04d}.bin',
                size=size, sha256=digest.hexdigest())

        with ThreadPoolExecutor(max_workers=min(4, max(1, len(entries))),
                                thread_name_prefix='project-backup') as executor:
            files = list(executor.map(backup_one, entries))
''' + text[end:]
    write(project, text)
    pipeline = SOURCE / 'music_generation_pipeline.py'
    text = pipeline.read_text(encoding='utf-8')
    before = "info = json.loads((work / 'progress.json').read_bytes())"
    assert text.count(before) == 1
    text = text.replace(before, 'info = diagnostic.read_progress()')
    write(pipeline, text)
    for path in (ROOT / 'product/pyproject.toml', SOURCE / '__init__.py'):
        text = path.read_text(encoding='utf-8')
        assert text.count('0.1.65') == 1
        write(path, text.replace('0.1.65', '0.1.66'))


if __name__ == '__main__':
    main()
