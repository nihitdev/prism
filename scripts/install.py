#!/usr/bin/env python3
"""Install Prism's terminal configs with per-file backups and rollback."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
PACKAGES = ['python', 'starship', 'fastfetch', 'kitty', 'fish', 'zsh', 'nushell',
            'fzf', 'fd', 'bat', 'eza', 'zoxide']


def directory(value, label):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts or path == Path('/'):
        raise ValueError(f'{label} must be a specific absolute directory: {path}')
    return path


def reject_symlinks(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'Refusing to overwrite through a symlink: {part}')


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.prism-', dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore(snapshot):
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    if manifest.get('format') != 'prism-install-v1':
        raise ValueError('Not a Prism installer backup')
    for entry in manifest['files']:
        destination = directory(entry['destination'], 'backup destination')
        reject_symlinks(destination)
        if entry['existed'] and not (snapshot / entry['backup']).is_file():
            raise ValueError(f'Incomplete backup for {destination}')
    for entry in reversed(manifest['files']):
        destination = Path(entry['destination'])
        if entry['existed']:
            atomic_copy(snapshot / entry['backup'], destination)
        else:
            destination.unlink(missing_ok=True)
    print(f'Restored files from {snapshot}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='list changes without installing anything')
    parser.add_argument('--theme', choices=['arch-blue', 'catppuccin', 'rose-pine'], default='rose-pine')
    parser.add_argument('--install-packages', action='store_true', help='install runtime packages with pacman (Arch only)')
    parser.add_argument('--restore', type=Path, metavar='BACKUP', help='restore an installer backup instead of installing')
    args = parser.parse_args()
    if args.restore:
        if args.dry_run:
            print(f'Would restore: {args.restore}')
        else:
            restore(args.restore)
        return
    home = directory(Path.home(), 'HOME')
    config = directory(os.environ.get('XDG_CONFIG_HOME', home / '.config'), 'XDG_CONFIG_HOME')
    state = directory(os.environ.get('XDG_STATE_HOME', home / '.local/state'), 'XDG_STATE_HOME')
    bindir = home / '.local/bin'
    zshdir = directory(os.environ.get('ZDOTDIR', home), 'ZDOTDIR')
    targets = [(p, config / p.relative_to(SOURCE / 'payload/config'))
               for p in sorted((SOURCE / 'payload/config').rglob('*')) if p.is_file()]
    targets += [(SOURCE / 'payload/home/.bashrc', home / '.bashrc'),
                (SOURCE / 'payload/home/.zshrc', zshdir / '.zshrc')]
    destinations = [target for _, target in targets] + [bindir / 'prism']
    for target in destinations + [state / 'prism/install-backups']:
        reject_symlinks(target)
        if target.exists() and not target.is_file() and target in destinations:
            raise ValueError(f'Expected a regular file: {target}')
    print('Prism: Bash, Zsh, Fish, Nushell, Starship, Kitty, Fastfetch and theme engine')
    print(f'Theme: {args.theme}')
    for target in destinations:
        print(f'{"Replace" if target.exists() else "Install"}: {target}')
    if args.install_packages:
        if not shutil.which('pacman'):
            raise ValueError('--install-packages currently supports Arch Linux only; install dependencies manually elsewhere')
        print('Packages: ' + ' '.join(PACKAGES))
    if args.dry_run:
        print('Dry run: no files or packages changed.')
        return
    if args.install_packages:
        prefix = [] if os.geteuid() == 0 else ['sudo']
        subprocess.run(prefix + ['pacman', '-S', '--needed', *PACKAGES], check=True)
    missing = [name for name in ('starship', 'fastfetch', 'kitty') if not shutil.which(name)]
    if missing:
        print('Optional applications not installed: ' + ', '.join(missing))
    # Generate colors and shell integrations in a staging tree, never the live config.
    with tempfile.TemporaryDirectory(prefix='prism-stage-') as temporary:
        stage = Path(temporary)
        staged_config = stage / 'config'
        shutil.copytree(SOURCE / 'payload/config', staged_config)
        env = dict(os.environ, XDG_CONFIG_HOME=str(staged_config))
        subprocess.run([sys.executable, str(staged_config / 'prism/prism.py'),
                        '--no-reload', 'theme', 'switch', args.theme], env=env, check=True)
        for tool, shell in [('starship', 'nu'), ('zoxide', 'nushell')]:
            if shutil.which(tool):
                result = subprocess.run([tool, 'init', shell], capture_output=True, text=True, check=True)
                (staged_config / 'nushell/dotfiles-init' / (tool + '.nu')).write_text(result.stdout)
        launcher = stage / 'prism-launcher'
        launcher.write_text('#!/usr/bin/env sh\nexec python3 "${XDG_CONFIG_HOME:-$HOME/.config}/prism/prism.py" "$@"\n')
        launcher.chmod(0o755)
        sources = [(staged_config / p.relative_to(SOURCE / 'payload/config'), target)
                   if p.is_relative_to(SOURCE / 'payload/config') else (p, target) for p, target in targets]
        sources.append((launcher, bindir / 'prism'))
        # Engine-generated previous-theme state belongs to this installation too.
        previous = staged_config / 'prism/previous'
        if previous.exists():
            sources.append((previous, config / 'prism/previous'))
        for _, target in sources:
            reject_symlinks(target)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        snapshot = state / 'prism/install-backups' / stamp
        snapshot.mkdir(parents=True, mode=0o700)
        shutil.copy2(Path(__file__), snapshot / 'restore.py')
        entries = []
        for i, (_, target) in enumerate(sources):
            entry = dict(destination=str(target), existed=target.exists(), backup=f'files/{i}')
            if target.exists():
                atomic_copy(target, snapshot / entry['backup'])
            entries.append(entry)
        (snapshot / 'manifest.json').write_text(json.dumps(dict(format='prism-install-v1', files=entries), indent=2))
        try:
            for source, target in sources:
                atomic_copy(source, target)
        except BaseException:
            restore(snapshot)
            raise
    print(f'Installed. Backup: {snapshot}')
    print(f'Restore: python3 {snapshot / "restore.py"} --restore "{snapshot}"')
    print('Open a new shell, then run: prism theme list')
    print('Ensure ~/.local/bin is in PATH. Login shell and running terminals were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Prism installation failed: {error}', file=sys.stderr)
        sys.exit(1)
