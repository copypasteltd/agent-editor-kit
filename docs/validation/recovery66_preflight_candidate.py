"""Candidate project.py replacements; not installed or registered product code.

The validation harness compiles these definitions into a separate copy of the
existing project module namespace. No source file or live worker is modified.
"""


def _recovery_transaction_identity(journal, journal_path):
    import re
    if (not isinstance(journal, dict)
            or journal.get('transaction_version') != '0.1.0'
            or journal.get('scope') != 'project-metadata-v1'
            or not isinstance(journal.get('transaction_id'), str)
            or not re.fullmatch(r'txn_[A-Za-z0-9_-]{1,128}', journal['transaction_id'])
            or not isinstance(journal.get('files'), list)
            or not journal['files']
            or journal.get('status') not in {'prepared', 'committed'}):
        raise AppError('PROJECT_TRANSACTION_INVALID', '事务身份、版本、状态或文件清单无效',
                       exit_code=6, path=str(journal_path))
    return journal['transaction_id'], journal['status']


def _recovery_entry_path(root, value, *, backup_prefix=None):
    if not isinstance(value, str) or not value:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务相对路径无效', exit_code=6)
    relative = value.replace('\\', '/')
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or ':' in part or '\0' in part
           or part.endswith(('.', ' ')) for part in parts):
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务路径含别名或无效部分',
                       exit_code=6, path=value)
    if backup_prefix is None:
        fixed = {'project.json', 'rights-ledger.json', 'project.lock.json',
                 'assets/lut-library.json', *MODEL_REGISTRY_FILES}
        allowed = relative in fixed or (len(parts) > 1 and parts[0] in {
            'operations', 'history', 'validation', 'exports'})
        if not allowed or _transaction_excluded(relative):
            raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务不能恢复该项目范围',
                           exit_code=6, path=value)
    elif not relative.startswith(backup_prefix + '/') or '/' in relative[len(backup_prefix) + 1:]:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '备份不属于当前事务',
                       exit_code=6, path=value)
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务恢复拒绝链接路径',
                           exit_code=6, path=str(candidate))
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务路径越出工程',
                       exit_code=6, path=value)
    return relative, resolved


def _preflight_transaction_recovery(root, journal, journal_path):
    import re
    transaction_id = journal['transaction_id']
    prefix = 'operations/project-transaction-backups/' + transaction_id
    seen_paths, seen_backups, prepared = set(), set(), []
    for index, item in enumerate(journal['files']):
        if (not isinstance(item, dict)
                or type(item.get('size')) is not int or item['size'] < 0
                or not isinstance(item.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])):
            raise AppError('PROJECT_TRANSACTION_INVALID', '事务文件大小或摘要无效',
                           exit_code=6, path=str(journal_path))
        relative, destination = _recovery_entry_path(root, item.get('path'))
        backup_relative, backup = _recovery_entry_path(root, item.get('backup'), backup_prefix=prefix)
        if (relative.casefold() in seen_paths or backup_relative.casefold() in seen_backups
                or backup_relative != prefix + f'/{index:04d}.bin'):
            raise AppError('PROJECT_TRANSACTION_INVALID', '事务文件重复或备份顺序无效',
                           exit_code=6, path=str(journal_path))
        seen_paths.add(relative.casefold())
        seen_backups.add(backup_relative.casefold())
        prepared.append((relative, destination, backup, item['size'], item['sha256']))
    try:
        buffer = bytearray(64 * 1024)
        view = memoryview(buffer)
        for relative, destination, backup, expected_size, expected_digest in prepared:
            if not backup.is_file():
                raise AppError('PROJECT_TRANSACTION_BACKUP_MISSING', '事务备份缺失，拒绝部分恢复',
                               exit_code=6, path=str(backup))
            digest, actual_size = hashlib.sha256(), 0
            with backup.open('rb') as handle:
                while count := handle.readinto(buffer):
                    actual_size += count
                    digest.update(view[:count])
            if actual_size != expected_size or digest.hexdigest() != expected_digest:
                raise AppError('PROJECT_TRANSACTION_BACKUP_CHANGED', '事务备份大小或摘要不符，未写回任何文件',
                               exit_code=6, path=str(backup))
    except (OSError, MemoryError) as exc:
        raise AppError('PROJECT_TRANSACTION_BACKUP_UNREADABLE', '无法完整核验所有事务备份，拒绝部分恢复',
                       exit_code=6, path=str(journal_path)) from exc
    try:
        cleanup = []
        baseline = {relative for relative, *_ in prepared}
        for path in _transaction_metadata_files(root):
            relative, candidate = _recovery_entry_path(root, _transaction_relative(path, root))
            if relative not in baseline:
                cleanup.append((relative, candidate))
    except (OSError, ValueError) as exc:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '无法核验待清理的元数据范围',
                       exit_code=6, path=str(journal_path)) from exc
    return prepared, cleanup


def recover_pending_transaction(root_value):
    """Preflight every known backup before any restore or metadata cleanup.

    Recovery remains retryable after an interrupted write. Cooperating callers
    must hold the project write lock; this is not multi-file atomic replacement.
    """
    root = project_root(root_value)
    journal_path = transaction_journal_file(root)
    if not journal_path.exists():
        return {'status': 'clean', 'recovered': False, 'journal': str(journal_path)}
    if journal_path.is_symlink() or getattr(journal_path, 'is_junction', lambda: False)():
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务日志不能是链接',
                       exit_code=6, path=str(journal_path))
    journal = load_json(journal_path)
    transaction_id, status = _recovery_transaction_identity(journal, journal_path)
    prefix = 'operations/project-transaction-backups/' + transaction_id
    # Validate all ancestors even when a committed backup was already removed.
    _recovery_entry_path(root, prefix + '/0000.bin', backup_prefix=prefix)
    if status == 'committed':
        _remove_transaction_tree(root, transaction_id)
        journal_path.unlink(missing_ok=True)
        return {'status': 'committed_cleaned', 'recovered': False,
                'transaction_id': transaction_id, 'journal': str(journal_path)}
    prepared, cleanup = _preflight_transaction_recovery(root, journal, journal_path)
    restored = []
    for relative, destination, backup, expected_size, expected_digest in prepared:
        data = backup.read_bytes()
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_digest:
            raise AppError('PROJECT_TRANSACTION_BACKUP_CHANGED', '备份在预检后发生改变，保留日志以便检查',
                           exit_code=6, path=str(backup))
        _atomic_write_bytes(destination, data)
        restored.append(relative)
    removed = []
    for relative, path in cleanup:
        path.unlink()
        removed.append(relative)
    _remove_transaction_tree(root, transaction_id)
    journal_path.unlink(missing_ok=True)
    return {'status': 'recovered', 'recovered': True, 'transaction_id': transaction_id,
            'command': journal.get('command'), 'restored': restored,
            'removed_metadata': removed, 'side_effect_scope': ['assets', 'renders', 'cache'],
            'journal': str(journal_path)}
