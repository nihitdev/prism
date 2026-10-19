# Prism

One palette across your terminal: **Kitty, Starship, Fastfetch, Bash, Zsh, Fish,
Nushell and FZF**. Includes the complete terminal dotfiles and a Python theme
engine, with Arch Blue, Catppuccin and Rosé Pine presets.

## Install

Requires Linux, Bash, Python **3.11+**, curl and tar. Preview first:

```bash
curl -fsSL https://raw.githubusercontent.com/nihitdev/prism/main/install.sh -o /tmp/prism-install.sh
bash /tmp/prism-install.sh --dry-run
bash /tmp/prism-install.sh
```

Or run the raw GitHub installer directly:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/nihitdev/prism/main/install.sh)
```

On Arch Linux, add `--install-packages` to install the terminal applications and
CLI tools with pacman. Other distributions: install Python 3.11+, Starship,
Fastfetch, Kitty and whichever shells you use with your package manager. FZF,
fd, bat, eza and zoxide enable the optional helpers. A Nerd Font is recommended;
the bundled Kitty configuration uses **SpaceMono Nerd Font**. Change
`~/.config/kitty/user.conf` to use another installed font.

```bash
bash /tmp/prism-install.sh --install-packages --theme catppuccin
```

The raw installer resolves GitHub `main` to a commit and downloads that revision
as one archive. Git is not required. To inspect everything before installation:

```bash
git clone https://github.com/nihitdev/prism.git
cd prism
./install.sh --dry-run
./install.sh --theme rose-pine
```

## What gets installed

The installer copies the files in `payload/config` into
`${XDG_CONFIG_HOME:-~/.config}` and installs Bash/Zsh entrypoints in your home
(`ZDOTDIR` is honored for `.zshrc`). The `prism` launcher goes in `~/.local/bin`.
Ensure that directory is in your PATH. Files not included in the payload are
left alone; existing managed files are backed up before replacement. This is a
complete terminal configuration installation, so review the dry run if you have
custom shell startup files. Symlinked destinations are rejected before changes.

Nushell integrations are generated from your installed Starship/Zoxide binaries;
empty integration stubs allow startup when those tools are absent. Zsh works
without Oh My Zsh; install optional Zsh plugins separately if desired. No shell
plugins are downloaded automatically. No histories, tokens, caches or usernames
are bundled. Settings use HOME and XDG paths.

Installation does **not** change your login shell, enable services, or signal
running terminals. Open a new shell and restart Kitty to load the dotfiles.
Thereafter, switching themes reloads Kitty instances owned by your user.

## Theme commands

```bash
prism                             # Current theme and quick help
prism theme list
prism theme preview rose-pine      # Swatches; no writes
prism theme switch arch-blue
prism theme back                   # Previous palette
prism theme current
prism --no-reload theme switch catppuccin
```

Bash, Zsh, Fish and Nushell wrappers refresh syntax/FZF colors in the shell where
you switch. Other open shells need reloading. Existing Fastfetch output is static:
run `fastfetch` again. Starship keeps each shell's prompt layout and Zsh's
right-aligned command-duration display.

Edit palettes in `~/.config/prism/prism.py`. Theme changes back up overwritten
files under `$XDG_CONFIG_HOME/config-backups/prism-switch-*`. `theme back` restores
a palette, not arbitrary previous file contents. Desktop/editor themes are outside
Prism's scope. Fastfetch's bundled `.jsonc` file uses ordinary JSON; retain that
format when editing it for theme switching.

## Backups and restore

Each install creates a backup under
`${XDG_STATE_HOME:-~/.local/state}/prism/install-backups/<timestamp>` and prints a
restore command. The restore program is saved with the backup, so it remains
available after the downloaded installer is cleaned up:

```bash
python3 /path/to/backup/restore.py --restore /path/to/backup
```

Restoring replaces managed files with their pre-install copies and removes files
that installation created. It leaves unrelated files and directories alone. A
failed file installation rolls back automatically. Package-manager operations
are not rolled back.

## Development

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh payload/home/.bashrc
```

Tests cover zero-write previews, all palettes, custom XDG paths, paths with spaces,
installation/restore, theme-write rollback, and symlink rejection. GitHub Actions
runs the Python tests without requiring a graphical session.

## License

GPL-3.0, matching the original terminal configuration collection. See [LICENSE](LICENSE).
