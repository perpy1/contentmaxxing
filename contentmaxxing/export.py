"""Portable ZIP export; copies inspectable data and intelligence, never env credentials."""
import os
import tempfile
import zipfile
from pathlib import Path

def export_workspace(store, destination):
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('Export destination cannot be a symlink.')
    destination = destination.resolve()
    if destination == store.root or store.root in destination.parents:
        raise ValueError('Export outside the workspace to avoid recursive archives.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Lock covers a consistent reader snapshot versus CLI writers.
    with store.lock():
        files = []
        for folder in [store.data, store.assets]:
            if folder.is_symlink():
                raise ValueError('Export refuses symlink: ' + str(folder.relative_to(store.root)))
            for path in folder.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Export refuses symlink: ' + str(path.relative_to(store.root)))
                if path.is_file():
                    files.append(path)
        for name in ['config.yaml', 'workflows.yaml', 'AGENTS.md', 'START_HERE.md']:
            path = store.root / name
            if path.is_symlink():
                raise ValueError('Export refuses symlink: ' + name)
            if name != 'START_HERE.md' or path.exists():
                files.append(path)
        count = sum(len(store.list(c)) for c in ['ideas', 'content', 'analytics'])
        fd, temporary = tempfile.mkstemp(prefix='.' + destination.name, dir=str(destination.parent))
        os.close(fd)
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive.write(path, str(path.relative_to(store.root)))
                archive.writestr('EXPORT_README.md', '# CONTENTMAXXING portable workspace\n\nInstall the CONTENTMAXXING CLI and point --workspace at this folder. Register your AI commands with contentmaxxing install --agent <codex|claude|cursor|gemini|generic> --path <this-folder>. Host registrations and machine-local runtime hints are not exported. JSON IDs/references are retained. Creator documents and .contentmaxxing skills carry the intelligence. Credentials are not exported from the environment. JSON content is authoritative; Markdown draft sidecars are for reading.\n')
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'archive': str(destination), 'records': count}
