"""Read-only release integrity and public/private boundary check."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile


def check(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(set(names))!=len(names):raise ValueError('Duplicate archive members')
        for name in names:
            parts=PurePosixPath(name).parts
            if name.startswith('/') or '..' in parts or '\\' in name or any(p in ('private','secrets','.venv-portal','data','build') for p in parts) or name.endswith(('.dpapi','.key','.env','.sqlite')):
                raise ValueError('Private/unexpected archive member: '+name)
        manifest={}
        for line in archive.read('MANIFEST.sha256').decode().splitlines():
            digest,name=line.split('  ',1);manifest[name]=digest
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Manifest mismatch: '+name)
        if set(names)!={*manifest,'MANIFEST.sha256'}:raise ValueError('Unmanifested files')
        required = {
            'README.md', 'ACCEPTANCE.md', 'windows/MiniPCConnect.exe',
            'company/setup.py', 'server/app.py', 'portal/index.html',
            '00-START-HERE-FA.md', 'CODEX-HANDOFF.md',
            'handoff/01-ARCHITECTURE.md', 'handoff/02-LINUX-INSTALL.md',
            'handoff/03-WINDOWS-USERS.md', 'handoff/04-OPERATIONS.md',
            'handoff/05-VALIDATION.md', 'handoff/06-SOURCE-MAP.md',
            'handoff/07-DEPENDENCIES-LICENSES.md',
            'handoff/SITE-INPUTS.example.json', 'handoff/DEPLOYMENT-REPORT.template.md',
            'handoff/HOME-ACCEPTANCE.json', 'company/build-package.ps1',
            'company/check_package.py', 'windows/build-helper.ps1',
        }
        if not required.issubset(names):
            raise ValueError('Release is incomplete')
        return {'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'files':len(names),'manifest_valid':True,'private_files_included':False,
                'helper_sha256':hashlib.sha256(archive.read('windows/MiniPCConnect.exe')).hexdigest()}


if __name__=='__main__':print(json.dumps(check(Path(sys.argv[1]))))
