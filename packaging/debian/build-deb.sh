#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_NAME="jellyfin-migration-assistant"
VERSION="0.3.0"
DEBIAN_REVISION="1"
ARCHITECTURE="all"
BUILD_ROOT="$PROJECT_ROOT/build/debian/${PACKAGE_NAME}_${VERSION}-${DEBIAN_REVISION}_${ARCHITECTURE}"
OUTPUT_DIR="$PROJECT_ROOT/dist/debian"
OUTPUT_DEB="$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-${DEBIAN_REVISION}_${ARCHITECTURE}.deb"
PYTHON_PACKAGE_DIR="$BUILD_ROOT/usr/lib/python3/dist-packages/jellyfin_migration_assistant"

rm -rf "$BUILD_ROOT"
mkdir -p \
  "$BUILD_ROOT/DEBIAN" \
  "$PYTHON_PACKAGE_DIR" \
  "$BUILD_ROOT/usr/bin" \
  "$BUILD_ROOT/usr/share/doc/$PACKAGE_NAME" \
  "$OUTPUT_DIR"

cp -a "$PROJECT_ROOT/src/jellyfin_migration_assistant/." "$PYTHON_PACKAGE_DIR/"
cp "$PROJECT_ROOT/README.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE_NAME/README.md"
cp "$PROJECT_ROOT/LICENSE" "$BUILD_ROOT/usr/share/doc/$PACKAGE_NAME/copyright"

cat > "$BUILD_ROOT/usr/bin/jf-migrate" <<'EOF'
#!/usr/bin/env python3
from jellyfin_migration_assistant.cli import main

raise SystemExit(main())
EOF
chmod 0755 "$BUILD_ROOT/usr/bin/jf-migrate"

cat > "$BUILD_ROOT/DEBIAN/control" <<EOF
Package: $PACKAGE_NAME
Version: $VERSION-$DEBIAN_REVISION
Section: admin
Priority: optional
Architecture: $ARCHITECTURE
Depends: python3 (>= 3.11), python3-yaml
Maintainer: Brian Honaker
Homepage: https://github.com/brianhonaker-stevecoding/jellyfin-migration-assistant
Description: Jellyfin Windows-to-Linux migration assistant
 Validation-first assistant for moving Jellyfin from Windows to native
 Debian/Ubuntu. Provides the jf-migrate CLI for inspecting migration
 packages, checking native backup/restore transport gates, auditing paths,
 planning metadata and rollback work, and blocking unsafe target-side repair
  steps before Jellyfin performs a normal startup scan.
EOF

find "$BUILD_ROOT" -type d -exec chmod 0755 {} +
find "$BUILD_ROOT" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD_ROOT/usr/bin/jf-migrate"

dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$OUTPUT_DEB"
echo "$OUTPUT_DEB"
