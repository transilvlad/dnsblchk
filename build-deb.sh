#!/bin/bash
# build-deb.sh: Build a Debian package for dnsblchk
# Usage: ./build-deb.sh
set -euo pipefail

echo "Cleaning previous build artifacts..."
rm -rf debian dist *.egg-info

echo "Building source distribution..."
python3 -m build --sdist

VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
echo "Detected version: ${VERSION}"

echo "Creating debian/ packaging files from templates..."
mkdir -p debian
cp packaging/debian/control debian/control
cp packaging/debian/rules debian/rules
cp packaging/debian/install debian/install
cp packaging/debian/postinst debian/postinst
cp packaging/debian/postrm debian/postrm
chmod +x debian/rules
chmod 755 debian/postinst debian/postrm

cat > debian/changelog <<EOF
dnsblchk (${VERSION}-1) unstable; urgency=medium
  * Automated release.
 -- Vlad Marian <transilvlad@gmail.com>  $(date -u '+%a, %d %b %Y %H:%M:%S +0000')
EOF

echo "Building .deb package..."
DEB_BUILD_OPTIONS="${DEB_BUILD_OPTIONS:-nocheck}" dpkg-buildpackage -us -uc -b

DEB_FILE="../dnsblchk_${VERSION}-1_all.deb"
if [ -f "${DEB_FILE}" ]; then
    echo "Built package: ${DEB_FILE}"
    echo "Install with: sudo apt install ./dnsblchk_${VERSION}-1_all.deb"
else
    echo "Build finished, but .deb file not found. Check for errors." >&2
    exit 1
fi
