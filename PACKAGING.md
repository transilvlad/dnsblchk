# Packaging Guide

This guide explains how to package the `dnsblchk` application into an RPM for easy distribution and installation
on RPM‑based Linux systems (Rocky Linux, AlmaLinux, Fedora) as well as produce Debian/Ubuntu `.deb` packages.

## Supported RPM Platforms
Use one (or more) of:
- Rocky Linux (RHEL community rebuild)
- AlmaLinux (RHEL community rebuild)
- Fedora (fast‑moving, newer toolchains)

These instructions avoid legacy platform assumptions and work with any current RHEL‑compatible distribution.

## Automated Build (GitHub Actions) – RPM & DEB
A unified GitHub Actions workflow (`.github/workflows/build-packages.yml`) builds:
- RPM packages (matrix: Rocky Linux 9, AlmaLinux 9, Fedora latest)
- Debian/Ubuntu `.deb` package (ubuntu-latest)
- Multi‑arch Docker images (amd64/arm64) for tagged releases

### How it Works
- The workflow runs tests first, then builds RPMs and a DEB, then (on version tags) publishes release assets and pushes Docker images.
- RPM builds happen inside container images for each target distro.
- Debian build uses `debhelper` + `pybuild` with a single Python version for speed.
- Docker build outputs a multi‑platform manifest including an image digest.

### Downloading the RPMs
1. Open the workflow run under the "Actions" tab.
2. Locate artifacts named like `rpm-package-rockylinux-9`, `rpm-package-almalinux-9`, `rpm-package-fedora-latest`.
3. Each artifact contains the built RPM(s) for its respective distro.

### Downloading the DEB
1. From the same run, download the `deb-package` artifact.
2. It contains one or more `.deb` files (architecture `all`).

## Excluded Test Suite
The `test/` directory (unit tests) is intentionally excluded from published source distributions and RPM/DEB contents:
- `MANIFEST.in` uses `prune test` to prevent tests entering the sdist archive.
- `setup.py` excludes `test` packages via `find_packages(exclude=["test", "test.*"]).`
This keeps production packages lean and avoids shipping development-only code. Tests remain in version control for CI.

---
## Manual Build Process (RPM)

If you need to build an RPM manually outside CI.

### Prerequisites (RPM)
On a RHEL‑compatible system (Rocky/AlmaLinux) or Fedora:

```bash
# Install build tools (Development Tools group optional but helpful)
sudo dnf groupinstall -y "Development Tools" || true
sudo dnf install -y rpm-build python3-devel python3-pip

# Upgrade Python packaging tools
python3 -m pip install --user --upgrade setuptools wheel build
```

Fedora users may already have newer toolchains; adjust as needed.

### 1. Prepare the Source Distribution (sdist)

```bash
python3 -m build --sdist
```

This creates `dist/dnsblchk-<version>.tar.gz` (version from `pyproject.toml`).
Use that archive for a reproducible RPM build.

### 2. Set up the RPM Build Environment

```bash
mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cp dist/dnsblchk-*.tar.gz ~/rpmbuild/SOURCES/
```

### 3. Use the Existing Spec File
An maintained spec file already exists at the project root: `dnsblchk.spec`.
Copy it into the SPECS directory and substitute the `@VERSION@` placeholder with the actual version extracted from `pyproject.toml`.

```bash
# From project root (where dnsblchk.spec lives)
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
cp dnsblchk.spec ~/rpmbuild/SPECS/dnsblchk.spec
sed -i "s/@VERSION@/${VERSION}/" ~/rpmbuild/SPECS/dnsblchk.spec

# Confirm placeholder replaced
grep Version ~/rpmbuild/SPECS/dnsblchk.spec
```

Notes:
- `Source0` in `dnsblchk.spec` expects the tarball filename (`dnsblchk-<version>.tar.gz`). Ensure it matches the file you copied to `~/rpmbuild/SOURCES/`.
- Adjust file lists or dependencies in `dnsblchk.spec` only if project layout changes; otherwise reuse as-is for consistency with CI builds.

### 4. Build the RPM

```bash
rpmbuild -ba ~/rpmbuild/SPECS/dnsblchk.spec
ls -1 ~/rpmbuild/RPMS/noarch/
```

### 5. Install and Verify

```bash
sudo dnf install -y ~/rpmbuild/RPMS/noarch/dnsblchk-${VERSION}-1*.noarch.rpm
rpm -q dnsblchk
systemctl status dnsblchk.service
ls /etc/dnsblchk/
ls /usr/lib/systemd/system/dnsblchk.service
```

---
## Debian/Ubuntu Packaging

Debian/Ubuntu packages are built using `debhelper` + `pybuild`. A helper script `build-deb.sh` automates the entire process, which handles:
- Creating the Debian package metadata (`debian/` directory with control files)
- Configuring permissions and system user/group setup via postinst hook
- Running `dpkg-buildpackage` to produce the final `.deb` file

### Prerequisites

```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python python3 python3-setuptools python3-pip fakeroot
```

### Quick Build: Using build-deb.sh

From the project root directory, simply run:

```bash
bash build-deb.sh
```

The script will:
1. Clean previous build artifacts
2. Build the source distribution
3. Create the `debian/` directory with all necessary control files (control, rules, install, changelog, postinst, postrm)
4. Invoke `dpkg-buildpackage` to produce the `.deb` package

The resulting `.deb` package will be located at `../dnsblchk_<version>-1_all.deb`.

### Manual Build Process

If you prefer to build step-by-step without the script:

#### 1. Build Source Distribution
```bash
python3 -m build --sdist
```

#### 2. Create the `debian/` Directory Structure
```bash
mkdir debian
```

#### 3. Create debian/control
```bash
cat > debian/control <<'EOF'
Source: dnsblchk
Section: utils
Priority: optional
Maintainer: DNSBL Checker <transilvlad@gmail.com>
Build-Depends: debhelper-compat (= 13), python3, python3-setuptools, dh-python
Standards-Version: 4.6.0
Homepage: https://github.com/example/dnsblchk

Package: dnsblchk
Architecture: all
Depends: ${python3:Depends}, ${misc:Depends}
Description: DNS Blacklist Checker service
 Monitors IPs against DNSBLs and can email alerts.
EOF
```

#### 4. Create debian/rules
```bash
cat > debian/rules <<'EOF'
#!/usr/bin/make -f
%:
	dh $@ --with python3 --buildsystem=pybuild
EOF
chmod +x debian/rules
```

#### 5. Create debian/install
This specifies what files get packaged where:
```bash
cat > debian/install <<'EOF'
dnsblchk.service usr/lib/systemd/system/
*.py opt/dnsblchk/
config/config.yaml opt/dnsblchk/config/
config/ips.txt opt/dnsblchk/config/
config/servers.txt opt/dnsblchk/config/
EOF
```

#### 6. Create debian/changelog
```bash
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
cat > debian/changelog <<EOF
dnsblchk (${VERSION}-1) unstable; urgency=medium
  * Automated release.
 -- DNSBL Checker <transilvlad@gmail.com>  $(date -u '+%a, %d %b %Y %H:%M:%S +0000')
EOF
```

#### 7. Build the DEB
```bash
dpkg-buildpackage -us -uc -b
```

The resulting `.deb` appears one level above the project root: `../dnsblchk_<version>-1_all.deb`.

### Package Behaviour on Installation

The installer automatically performs several setup steps via the `debian/postinst` hook:

- **System User/Group**: Creates `dnsblchk` system user and group if missing
- **Application Directory**: Ensures `/opt/dnsblchk` exists and is owned by `dnsblchk:dnsblchk` (avoids systemd namespace failures)
- **Config Symlinks**: Creates symlinks at:
  - `/etc/dnsblchk/config.yaml` → `/opt/dnsblchk/config/config.yaml`
  - `/etc/dnsblchk/ips.txt` → `/opt/dnsblchk/config/ips.txt`
  - `/etc/dnsblchk/servers.txt` → `/opt/dnsblchk/config/servers.txt`
  
  If any of these already exist as directories on the system, they are backed up to a timestamped `.orig.<unix>` file and replaced with the symlink.

- **Log Directory**: Creates `/var/log/dnsblchk` and sets ownership to `dnsblchk:dnsblchk`
- **Runtime Directory**: Creates `/run/dnsblchk` and sets ownership to `dnsblchk:dnsblchk`
- **Systemd Daemon Reload**: Runs `systemctl daemon-reload` to register the new service unit

### Installation and Verification

```bash
sudo apt install ./dnsblchk_<version>-1_all.deb
```

After installation, you can verify and enable autorun:

```bash
# Check service status
sudo systemctl status dnsblchk.service

# Enable service to autorun on boot
sudo systemctl enable dnsblchk.service

# Start the service manually (if not auto-started)
sudo systemctl start dnsblchk.service

# View installed configuration
ls /etc/dnsblchk/
cat /etc/dnsblchk/config.yaml
```

To verify that the service is configured for autorun:
```bash
sudo systemctl is-enabled dnsblchk.service
```
Should output: `enabled`

---
## Troubleshooting and Debugging

If the `dnsblchk` service fails to start after installation, use these commands to diagnose the issue.

### 1. Check Service Status
This command provides a snapshot of the service's state and shows recent log entries, which often include the error that caused the failure.
```bash
sudo systemctl status dnsblchk.service
```
Look for the `Active:` line. If it says `failed`, review the log output at the bottom of the command's response.

### 2. View Detailed Service Logs
To get the complete log history from the `systemd` journal, use `journalctl`:
```bash
sudo journalctl -u dnsblchk.service
```
To follow the logs in real-time while you attempt to start the service, use the `-f` (follow) flag:
```bash
sudo journalctl -u dnsblchk.service -f
```

### 3. Check Application Log File
If the service starts but encounters issues later, it will write logs to its dedicated log file. The log directory is created at `/var/log/dnsblchk/` by the installer.
```bash
# Check for the log file
ls -l /var/log/dnsblchk/

# View the entire log
cat /var/log/dnsblchk/dnsblchk.log

# Follow the log in real-time
tail -f /var/log/dnsblchk/dnsblchk.log
```
Common startup problems are often related to misconfigured paths or permissions issues. The logs from `journalctl` are usually the best place to start debugging.

---
## Alternative Quick Build Using `fpm`

```bash
sudo apt install -y ruby ruby-dev build-essential
sudo gem install --no-document fpm
python3 -m build --sdist
fpm -s python -t deb dist/dnsblchk-*.tar.gz \
    --name dnsblchk \
    --depends python3 \
    --description "DNS Blacklist Checker service" \
    --maintainer "DNSBL Checker <transilvlad@gmail.com>"
```
Produces a `dnsblchk_<version>_all.deb`.

## Distribution
The generated RPM or DEB file is the distributable artifact. You can host these in a DNF/YUM repository or an APT repository, or distribute directly. For Docker, use the published multi‑arch images tagged with `v<version>` and `latest`; the workflow step summary includes the manifest digest for verification.
