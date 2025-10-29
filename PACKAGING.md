# Packaging Guide

This guide explains how to package the `dnsblchk` application into an RPM for easy distribution and installation
on RPM-based Linux systems like CentOS, Fedora, Rocky Linux, and AlmaLinux, as well as produce Debian/Ubuntu `.deb` packages.

## Note on CentOS Lifecycle
CentOS Linux (the downstream rebuild of RHEL) reached end-of-life for version 8 at the end of 2021. For long‑term RPM builds you should prefer one of:
- CentOS Stream (rolling preview of next RHEL minor release)
- Rocky Linux (community rebuild of RHEL)
- AlmaLinux (community rebuild of RHEL)
- Fedora (if you want newer toolchains)

The examples below use a CentOS 7 container for broad compatibility, but you may adapt them to Rocky/Alma/Fedora. Replace `yum` with `dnf` where appropriate.

## Automated Build (GitHub Actions) – RPM

This repository is configured with a GitHub Actions workflow to automatically build the RPM package
whenever changes are pushed to the `main` branch.

### How it Works
- The workflow is defined in `.github/workflows/build-rpm.yml`.
- It uses a CentOS 7 container to ensure a consistent build environment.
- It installs all necessary build dependencies, creates the source distribution, and builds the RPM.
- The resulting RPM file is uploaded as an artifact to the workflow run.

### Downloading the RPM
1. Go to the "Actions" tab in the GitHub repository.
2. Click on the latest workflow run for the `main` branch.
3. Under "Artifacts", you will find the `rpm-package` artifact.
4. Download the artifact, which will be a ZIP file containing the RPM.

## Automated Build (GitHub Actions) – Debian/Ubuntu `.deb`
A separate workflow builds a Debian package on pushes to `main`.

### How it Works
- Defined in `.github/workflows/build-deb.yml` (see below if not yet committed).
- Runs on `ubuntu-latest` and uses standard `debhelper`/`pybuild` tooling.
- Dynamically extracts the Python version from `setup.py`.
- Produces a `.deb` artifact you can download from the workflow run.

### Downloading the DEB
1. Open the latest `build-deb` workflow run under the "Actions" tab.
2. Download the `deb-package` artifact ZIP containing the `.deb` file.

## Excluded Test Suite
The `test/` directory (unit tests) is intentionally excluded from published source distributions and RPM contents:
- `MANIFEST.in` uses `prune test` to prevent tests entering the sdist archive.
- `setup.py` excludes `test` packages via `find_packages(exclude=["test", "test.*"]).`
This keeps production packages lean and avoids shipping development-only code. Retain tests in VCS for CI.

## Manual Build Process (RPM)

If you need to build the RPM manually, follow the steps below.

## Prerequisites (RPM)

- A build environment (ideally a Rocky/AlmaLinux/CentOS Stream/Fedora system or a Docker container).
- `setuptools` and `wheel` for building Python packages.
- `rpm-build` tools.

```bash
# Install build tools on a RHEL-compatible system
sudo yum groupinstall -y "Development Tools"
sudo yum install -y rpm-build python3-devel

# Install Python packaging tools
pip3 install --user --upgrade setuptools wheel
```

## 1. Prepare the Source Distribution (sdist)

First, create a source distribution of the application.
This will bundle up all the necessary files for the RPM build.

```bash
# From the root of the project
python3 setup.py sdist
```

This command will create a `dist/dnsblchk-1.0.0.tar.gz` file.
This is the source archive we'll use for the RPM.

## 2. Set up the RPM Build Environment

RPM builds are done in a specific directory structure.

```bash
# Create the RPM build directories in your home directory
mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
```

## 3. Create the .spec File

The `.spec` file is the recipe for `rpmbuild`.
It tells RPM how to build and package the application.
Create a file named `dnsblchk.spec` in `~/rpmbuild/SPECS/`.

```spec
# ~/rpmbuild/SPECS/dnsblchk.spec

%global src_name dnsblchk

Name:           %{src_name}
Version:        1.0.0
Release:        1%{?dist}
Summary:        A DNS Blacklist Checker service

License:        MIT
URL:            https://github.com/example/dnsblchk
Source0:        %{_topdir}/SOURCES/%{src_name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3
Requires:       python3-pip
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description
A service to monitor IP addresses against DNS blacklists (DNSBLs) and send email alerts.

%prep
%setup -q -n %{src_name}-%{version}

%build
# This is a pure Python package, so no build command is needed.

%install
# Install the Python package into the build root.
pip3 install --root %{buildroot} --no-deps .

# Create necessary directories
install -d -m 755 %{buildroot}/%{_sysconfdir}/%{src_name}
install -d -m 755 %{buildroot}/%{_unitdir}
install -d -m 755 %{buildroot}/var/log/%{src_name}
install -d -m 755 %{buildroot}/var/run/%{src_name}

# Install service and config files
install -m 644 dnsblchk.service %{buildroot}/%{_unitdir}/dnsblchk.service
install -m 644 config/config.yaml.template %{buildroot}/%{_sysconfdir}/%{src_name}/config.yaml

%post
# Reload systemd to recognize the new service
%systemd_post dnsblchk.service

# Create the service user
/usr/sbin/useradd -r -s /bin/false -d /opt/%{src_name} %{src_name} >/dev/null 2>&1 || :

# Set permissions
chown -R %{src_name}:%{src_name} /var/log/%{src_name}
chown -R %{src_name}:%{src_name} /var/run/%{src_name}

echo "Installation complete. Please configure /etc/dnsblchk/config.yaml"
echo "To start the service, run: systemctl start dnsblchk.service"

%preun
# Stop and disable the service before uninstalling
%systemd_preun dnsblchk.service

%postun
# Reload systemd after the service file is removed
%systemd_postun_with_restart dnsblchk.service

# Remove the service user
/usr/sbin/userdel %{src_name} >/dev/null 2>&1 || :

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/%{src_name}/*
%{python3_sitelib}/%{src_name}-*.dist-info/*
%{_bindir}/dnsblchk
%config(noreplace) %{_sysconfdir}/%{src_name}/config.yaml
%{_unitdir}/dnsblchk.service
/var/log/%{src_name}
/var/run/%{src_name}

%changelog
* Tue Oct 28 2025 Your Name <you@example.com> - 1.0.0-1
- Initial RPM packaging.
```

## 4. Build the RPM

Now, you can build the RPM package.

```bash
# Copy the source archive to the SOURCES directory
cp dist/dnsblchk-1.0.0.tar.gz ~/rpmbuild/SOURCES/

# Build the RPM
rpmbuild -ba ~/rpmbuild/SPECS/dnsblchk.spec
```

If the build is successful, you will find the RPM file in `~/rpmbuild/RPMS/noarch/` (exact name depends on distro tag).

## 5. Installation and Verification (RPM)

```bash
sudo yum install ~/rpmbuild/RPMS/noarch/dnsblchk-1.0.0-1*.noarch.rpm
rpm -q dnsblchk
systemctl status dnsblchk
ls /etc/dnsblchk/
ls /usr/lib/systemd/system/dnsblchk.service
```

---

## Debian/Ubuntu Packaging (Manual)

Below is an example of creating a native Debian package using `debhelper` and `pybuild`.

### Prerequisites (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python python3-all python3-setuptools python3-pip fakeroot
```

### 1. Source Distribution (Optional)
You can either build from the live source tree or create an sdist like for RPM:
```bash
python3 setup.py sdist
```

### 2. Create the `debian/` Directory
In the project root:
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

cat > debian/compat <<'EOF'
13
EOF

cat > debian/rules <<'EOF'
#!/usr/bin/make -f
%:
	dh $@ --with python3 --buildsystem=pybuild
EOF
chmod +x debian/rules

# Service and config install mapping
cat > debian/install <<'EOF'
dnsblchk.service usr/lib/systemd/system/
config/config.yaml.template etc/dnsblchk/config.yaml
EOF

# Changelog (update date/time as needed)
cat > debian/changelog <<'EOF'
dnsblchk (1.0.0-1) unstable; urgency=medium
  * Initial release.
 -- DNSBL Checker <contact@example.com>  Tue, 29 Oct 2025 00:00:00 +0000
EOF
```

### 3. Build the DEB
```bash
dpkg-buildpackage -us -uc -b
```
Resulting `.deb` will appear one level above the project root (e.g. `../dnsblchk_1.0.0-1_all.deb`).

### 4. Install and Verify (Debian/Ubuntu)
```bash
sudo apt install ./../dnsblchk_1.0.0-1_all.deb
systemctl status dnsblchk.service
ls /etc/dnsblchk/
```

### Notes
- The current `setup.py` uses `data_files` with absolute system paths; Debian packaging prefers installing into standard locations via `debian/install`. The above approach overrides that.
- For more formal Debian submission, additional metadata (copyright, watch, source format) is required.

## Alternative Quick Build Using `fpm`
If you prefer a single-command build and can install Ruby:
```bash
sudo apt install -y ruby ruby-dev build-essential
sudo gem install --no-document fpm
python3 setup.py sdist
fpm -s python -t deb dist/dnsblchk-1.0.0.tar.gz \
    --name dnsblchk \
    --depends python3 \
    --description "DNS Blacklist Checker service" \
    --maintainer "DNSBL Checker <contact@example.com>"
```
Produces `dnsblchk_1.0.0_all.deb`.

## Distribution
The generated RPM or DEB file is the distributable artifact.
You can host these in a YUM/DNF repository or an APT repository, or distribute directly.
