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
## Debian/Ubuntu Packaging (Manual)

Example native Debian packaging using `debhelper` + `pybuild`.

### Prerequisites

```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python python3 python3-setuptools python3-pip fakeroot
```

### 1. (Optional) Source Distribution
```bash
python3 -m build --sdist
```

### 2. Create the `debian/` Directory

```bash
mkdir debian
cat > debian/control <<'EOF'
Source: dnsblchk
Section: utils
Priority: optional
Maintainer: DNSBL Checker <contact@example.com>
Build-Depends: debhelper-compat (= 13), python3, python3-setuptools, dh-python
Standards-Version: 4.6.0
Homepage: https://github.com/example/dnsblchk

Package: dnsblchk
Architecture: all
Depends: ${python3:Depends}, ${misc:Depends}
Description: DNS Blacklist Checker service
 Monitors IPs against DNSBLs and can email alerts.
EOF

cat > debian/rules <<'EOF'
#!/usr/bin/make -f
%:
	dh $@ --with python3 --buildsystem=pybuild
EOF
chmod +x debian/rules

cat > debian/install <<'EOF'
dnsblchk.service usr/lib/systemd/system/
config/config.yaml.template etc/dnsblchk/config.yaml
EOF

VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
cat > debian/changelog <<EOF
dnsblchk (${VERSION}-1) unstable; urgency=medium
  * Initial release.
 -- DNSBL Checker <contact@example.com>  $(date -u '+%a, %d %b %Y %H:%M:%S +0000')
EOF
```

### 3. Build the DEB
```bash
dpkg-buildpackage -us -uc -b
```
Resulting `.deb` appears one level above (`../dnsblchk_<version>-1_all.deb`).

### 4. Install and Verify
```bash
sudo apt install ./../dnsblchk_*_all.deb
systemctl status dnsblchk.service
ls /etc/dnsblchk/
```

### Notes
- `python3-all` is omitted to speed builds (single interpreter sufficient).
- For formal distribution, add copyright/licensing metadata (`debian/copyright`), `debian/source/format`, and optionally a `debian/watch` file.

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
    --maintainer "DNSBL Checker <contact@example.com>"
```
Produces a `dnsblchk_<version>_all.deb`.

## Distribution
The generated RPM or DEB file is the distributable artifact. You can host these in a DNF/YUM repository or an APT repository, or distribute directly. For Docker, use the published multi‑arch images tagged with `v<version>` and `latest`; the workflow step summary includes the manifest digest for verification.
