#!/bin/bash
# build-deb.sh: Build a Debian package for dnsblchk
# Usage: ./build-deb.sh
set -euo pipefail

# Clean up any previous build artifacts
echo "Cleaning previous build artifacts..."
rm -rf debian dist *.egg-info

# Build source distribution (may be used by pybuild internally)
echo "Building source distribution..."
python3 -m build --sdist

# Extract version from pyproject.toml
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
echo "Detected version: $VERSION"

# Create debian/ directory and files
echo "Creating debian/ packaging files..."
mkdir -p debian
cat > debian/control <<'EOF'
Source: dnsblchk
Section: utils
Priority: optional
Maintainer: <transilvlad@gmail.com>
Build-Depends: debhelper-compat (= 13), python3, python3-setuptools, dh-python
Standards-Version: 4.6.0
Homepage: https://github.com/example/dnsblchk

Package: dnsblchk
Architecture: all
Depends: ${python3:Depends}, ${misc:Depends}
Description: DNS RBL Checker service
 Monitor IP addresses against DNS RBLs and alert by email or web hook.
EOF

cat > debian/rules <<'EOF'
#!/usr/bin/make -f
%:
	dh $@ --with python3 --buildsystem=pybuild
EOF
chmod +x debian/rules

# Install directives:
# - systemd unit -> /usr/lib/systemd/system/
# - python sources -> /opt/dnsblchk/ (service ExecStart points here)
# - config assets -> /opt/dnsblchk/config/
cat > debian/install <<'EOF'
dnsblchk.service usr/lib/systemd/system/
*.py opt/dnsblchk/
# Package the runtime config (use config/config.yaml in repo)
config/config.yaml opt/dnsblchk/config/
config/ips.txt opt/dnsblchk/config/
config/servers.txt opt/dnsblchk/config/
EOF

cat > debian/changelog <<EOF
dnsblchk (${VERSION}-1) unstable; urgency=medium
  * Automated release.
  * Ensure config/config.yaml packaged where application expects it.
 -- <transilvlad@gmail.com>  $(date -u '+%a, %d %b %Y %H:%M:%S +0000')
EOF

# Create debian/postinst to add user/group, set permissions, and create config symlink if needed
cat > debian/postinst <<'EOF'
#!/bin/sh
set -e
# Add dnsblchk group if it does not exist
if ! getent group dnsblchk >/dev/null; then
    addgroup --system dnsblchk
fi
# Add dnsblchk user if it does not exist
if ! id dnsblchk >/dev/null 2>&1; then
    adduser --system --ingroup dnsblchk --home /opt/dnsblchk --no-create-home dnsblchk
fi
# Ensure application directory exists and ownership is correct
mkdir -p /opt/dnsblchk
chown -R dnsblchk:dnsblchk /opt/dnsblchk
# Ensure /etc/dnsblchk exists
mkdir -p /etc/dnsblchk
# If /etc/dnsblchk/config.yaml missing, create symlink to packaged default
if [ ! -e /etc/dnsblchk/config.yaml ]; then
    ln -s /opt/dnsblchk/config/config.yaml /etc/dnsblchk/config.yaml
else
    # If it's a directory, move it out of the way and create the symlink
    if [ -d /etc/dnsblchk/config.yaml ]; then
        BACKUP_DIR="/etc/dnsblchk/config.yaml.orig.$(date +%s)"
        mv /etc/dnsblchk/config.yaml "$BACKUP_DIR" || true
        ln -s /opt/dnsblchk/config/config.yaml /etc/dnsblchk/config.yaml || true
    fi
fi
# Symlink other config files if they don't exist (handle existing directories similarly)
if [ ! -e /etc/dnsblchk/ips.txt ]; then
    ln -s /opt/dnsblchk/config/ips.txt /etc/dnsblchk/ips.txt
else
    if [ -d /etc/dnsblchk/ips.txt ]; then
        BACKUP_DIR="/etc/dnsblchk/ips.txt.orig.$(date +%s)"
        mv /etc/dnsblchk/ips.txt "$BACKUP_DIR" || true
        ln -s /opt/dnsblchk/config/ips.txt /etc/dnsblchk/ips.txt || true
    fi
fi
if [ ! -e /etc/dnsblchk/servers.txt ]; then
    ln -s /opt/dnsblchk/config/servers.txt /etc/dnsblchk/servers.txt
else
    if [ -d /etc/dnsblchk/servers.txt ]; then
        BACKUP_DIR="/etc/dnsblchk/servers.txt.orig.$(date +%s)"
        mv /etc/dnsblchk/servers.txt "$BACKUP_DIR" || true
        ln -s /opt/dnsblchk/config/servers.txt /etc/dnsblchk/servers.txt || true
    fi
fi
# Create and set permissions for log directory under /var
mkdir -p /var/log/dnsblchk
chown dnsblchk:dnsblchk /var/log/dnsblchk
# Create and set permissions for runtime directory under /run
mkdir -p /run/dnsblchk
chown dnsblchk:dnsblchk /run/dnsblchk
# Restart systemd daemon to pick up unit file (not enabling automatically here)
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
fi
exit 0
EOF
chmod 755 debian/postinst

# Create debian/postrm to optionally remove user/group on purge
cat > debian/postrm <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "purge" ]; then
    deluser --system dnsblchk 2>/dev/null || true
    delgroup --system dnsblchk 2>/dev/null || true
    rm -f /etc/dnsblchk/config.yaml 2>/dev/null || true
    rmdir /etc/dnsblchk 2>/dev/null || true
fi
exit 0
EOF
chmod 755 debian/postrm

# Build the .deb package
echo "Building .deb package..."
dpkg-buildpackage -us -uc -b

# Show result
DEB_FILE="../dnsblchk_${VERSION}-1_all.deb"
if [ -f "$DEB_FILE" ]; then
    echo "\nDebian package built: $DEB_FILE"
    echo "Install with: sudo apt install ./dnsblchk_${VERSION}-1_all.deb"
else
    echo "\nBuild finished, but .deb file not found. Check for errors." >&2
fi
