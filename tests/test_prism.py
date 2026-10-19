import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PrismTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='prism-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home with spaces'
        self.home.mkdir()
        self.config = self.home / 'custom config'
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                        XDG_STATE_HOME=str(self.home / 'state'), PATH='')
        self.env.pop('ZDOTDIR', None)

    def install(self, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), *args],
                                env=self.env, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def engine(self):
        shutil.copytree(ROOT / 'payload/config', self.config)
        spec = importlib.util.spec_from_file_location('prism', self.config / 'prism/prism.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = self.config
        return module

    def test_dry_run_is_zero_write(self):
        before = list(self.home.rglob('*'))
        self.install('--dry-run')
        self.assertEqual(before, list(self.home.rglob('*')))

    def test_install_and_restore_preserve_existing_files(self):
        (self.home / '.bashrc').write_text('original bash config\n')
        self.config.mkdir()
        (self.config / 'unrelated').write_text('keep me')
        self.install('--theme', 'catppuccin')
        self.assertEqual((self.config / 'prism/current').read_text().strip(), 'catppuccin')
        self.assertTrue(os.access(self.home / '.local/bin/prism', os.X_OK))
        for path in (self.config / 'starship').glob('*.toml'):
            self.assertEqual(tomllib.loads(path.read_text())['palette'], 'prism')
        self.assertTrue((self.config / 'fish/conf.d/15-prism-theme.fish').is_file())
        self.assertFalse((self.config / 'nushell/history.txt').exists())
        backup = next((self.home / 'state/prism/install-backups').iterdir())
        # Restoration must work after the downloaded installer source is removed.
        result = subprocess.run([sys.executable, str(backup / 'restore.py'), '--restore', str(backup)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / '.bashrc').read_text(), 'original bash config\n')
        self.assertEqual((self.config / 'unrelated').read_text(), 'keep me')
        self.assertFalse((self.home / '.local/bin/prism').exists())

    def test_symlink_escape_rejected(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        self.config.symlink_to(outside)
        self.assertNotEqual(self.install(success=False).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_palettes_and_previous_theme(self):
        engine = self.engine()
        with patch.object(engine.shutil, 'which', return_value=None), patch.object(engine, 'reload_kitty') as reload:
            for name in engine.PALETTES:
                engine.switch(name, reload=False)
                self.assertEqual(engine.current_theme(), name)
                json.loads((self.config / 'fastfetch/config.jsonc').read_text())
                for path in (self.config / 'starship').glob('*.toml'):
                    self.assertEqual(tomllib.loads(path.read_text())['palettes']['prism']['base'], engine.PALETTES[name]['base'])
            reload.assert_not_called()
        self.assertEqual((self.config / 'prism/previous').read_text().strip(), 'catppuccin')

    def test_failed_theme_switch_restores_written_files(self):
        engine = self.engine()
        before = {p: p.read_bytes() for p in self.config.rglob('*') if p.is_file()}
        real_write = engine.write_atomic
        calls = 0
        def fail_once(path, content):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('injected write failure')
            return real_write(path, content)
        with patch.object(engine.shutil, 'which', return_value=None), patch.object(engine, 'write_atomic', side_effect=fail_once):
            with self.assertRaises(OSError):
                engine.switch('arch-blue', reload=False)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_payload_is_portable(self):
        for path in (ROOT / 'payload').rglob('*'):
            self.assertFalse(path.is_symlink(), str(path))
            if path.is_file() and '__pycache__' not in path.parts:
                text = path.read_text()
                self.assertNotIn('/home/zei', text, str(path))
                self.assertNotIn('/mnt/storage', text, str(path))
        for path in (ROOT / 'payload/config/starship').glob('*.toml'):
            tomllib.loads(path.read_text())


if __name__ == '__main__':
    unittest.main()
