"""Small, offline contract for the self-contained company handoff archive."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    'release_check', Path(__file__).with_name('check_package.py'))
release_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_check)

REQUIRED = (
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
)


class PackageContracts(unittest.TestCase):
    def archive(self, folder, omit=None, extra=None, tamper=False):
        path = Path(folder) / 'fixture.zip'
        members = {name: b'synthetic public fixture' for name in REQUIRED if name != omit}
        members.update(extra or {})
        manifest = ''.join(hashlib.sha256(value).hexdigest() + '  ' + name + '\n'
                           for name, value in members.items())
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in members.items():
                archive.writestr(name, b'changed' if tamper and name == 'README.md' else value)
            archive.writestr('MANIFEST.sha256', manifest)
        return path

    def test_complete_handoff_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            result = release_check.check(self.archive(folder))
            self.assertTrue(result['manifest_valid'])
            self.assertFalse(result['private_files_included'])

    def test_missing_agent_instructions_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                release_check.check(self.archive(folder, omit='CODEX-HANDOFF.md'))

    def test_changed_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Manifest mismatch'):
                release_check.check(self.archive(folder, tamper=True))

    def test_private_state_is_rejected_even_if_manifested(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Private/unexpected'):
                release_check.check(self.archive(folder, extra={'secrets/proxy.env': b'synthetic'}))


if __name__ == '__main__':
    unittest.main()
