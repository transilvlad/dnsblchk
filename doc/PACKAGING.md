# Packaging Guide

This guide covers the supported package and release paths for dnsblchk.

## Version Source

The package version is defined in `pyproject.toml`.

```bash
python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])'
```

For the RBL/DBL configuration break, the project version is `2.0.0`.

## GitHub Actions

`.github/workflows/build-packages.yml` runs:

- Unit tests.
- RPM builds for Rocky Linux 9, AlmaLinux 9, and Fedora latest.
- A DEB build on Ubuntu.
- Multi-arch Docker image publishing for version tags.
- Release asset publishing for version tags.

The DEB job calls `bash build-deb.sh`; it does not maintain separate inline
Debian package metadata.

## RPM

The canonical RPM source is `dnsblchk.spec`.

Manual RPM build:

```bash
python3 -m pip install --user --upgrade setuptools wheel build
python3 -m build --sdist
mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cp dist/dnsblchk-*.tar.gz ~/rpmbuild/SOURCES/
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
cp dnsblchk.spec ~/rpmbuild/SPECS/dnsblchk.spec
sed -i "s/@VERSION@/${VERSION}/" ~/rpmbuild/SPECS/dnsblchk.spec
rpmbuild -ba ~/rpmbuild/SPECS/dnsblchk.spec
```

The RPM installs:

- Python modules, including `domaincheck.py`.
- `dnsblchk.service`.
- `/etc/dnsblchk/config.yaml`.
- `/etc/dnsblchk/ips.txt`.
- `/etc/dnsblchk/rbls.txt`.
- `/etc/dnsblchk/dbls.txt`.

## DEB

The canonical Debian metadata lives in `packaging/debian/`.
`build-deb.sh` copies those templates to a temporary `debian/` directory and
generates the changelog from the version in `pyproject.toml`.

Prerequisites:

```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python python3 python3-setuptools python3-pip fakeroot
python3 -m pip install --user --upgrade build setuptools packaging wheel
```

Build:

```bash
bash build-deb.sh
```

The package is written one directory above the project root:

```text
../dnsblchk_<version>-1_all.deb
```

Install:

```bash
sudo apt install ./dnsblchk_<version>-1_all.deb
```

The DEB install creates the `dnsblchk` system user/group, installs the service,
and installs default config files under `/etc/dnsblchk/`.

## Docker

Build locally:

```bash
docker build -t dnsblchk:local .
```

Run with mounted config and logs:

```bash
docker run --rm \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/logs:/app/logs" \
  dnsblchk:local
```

The image starts with `config/config-docker.yaml`, which uses `/app/config` and
`/app/logs` paths.

Tagged releases publish multi-architecture images to GHCR:

```text
ghcr.io/transilvlad/dnsblchk:latest
ghcr.io/transilvlad/dnsblchk:<tag>
```

## Release Checklist

1. Confirm `pyproject.toml` has the intended version.
2. Run `PYTHONPATH=. pytest -q`.
3. Run `PYTHONPATH=. pytest --cov -q`.
4. Run `git diff --check`.
5. Build packages through CI or local package commands.
6. Tag releases as `v<version>` to trigger package and Docker publishing.
