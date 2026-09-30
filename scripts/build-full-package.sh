#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
readonly PLATFORM_ROOT="${PMT_PLATFORM_DATA_ROOT:-${ROOT}/platform-data}"
readonly PLATFORM_COMMIT="${PMT_PLATFORM_DATA_COMMIT:-df82b1741dec619300707881114f6b17b5204f60}"
readonly NAME="pmt-raw-capture-${VERSION}"

git -C "${PLATFORM_ROOT}" cat-file -e "${PLATFORM_COMMIT}^{commit}"
if ! git -C "${PLATFORM_ROOT}" diff --quiet "${PLATFORM_COMMIT}" -- License Readme.md xml; then
    echo "platform data differs from ${PLATFORM_COMMIT}; commit or select the approved revision" >&2
    exit 1
fi

"${ROOT}/scripts/build-package.sh" >/dev/null
temporary="$(mktemp -d)"
trap 'rm -rf -- "${temporary}"' EXIT
tar -xzf "${ROOT}/dist/${NAME}.tar.gz" -C "${temporary}"
stage="${temporary}/${NAME}"
mkdir -p "${temporary}/platform"
git -C "${PLATFORM_ROOT}" archive "${PLATFORM_COMMIT}" License Readme.md xml \
    | tar -x -C "${temporary}/platform"
python3 - "${temporary}/platform" "${stage}/bundled-platform-data" <<'PY'
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

source, target = map(Path, sys.argv[1:])
approved = {(0x22473996, 14496), (0x22491753, 6272), (0x22806802, 6784),
            (0x3d4bb40a, 48), (0x3d4bb41a, 24), (0x477e9373, 6160), (0x6e94ffa0, 176)}
tree = ET.parse(str(source / "xml/pmt.xml"))
mappings = tree.getroot().find("mappings")
found = set()
target.mkdir()
for name in ("License", "Readme.md"):
    shutil.copyfile(str(source / name), str(target / name))
for mapping in list(mappings):
    identity = (int(mapping.attrib["guid"], 16), int(mapping.attrib["size"]))
    if identity not in approved:
        mappings.remove(mapping)
        continue
    if identity in found:
        raise ValueError("duplicate approved schema")
    found.add(identity)
    xmlset = mapping.find("xmlset")
    for tag in ("common", "aggregator", "aggregatorinterface"):
        relative = Path("xml") / xmlset.findtext("basedir") / xmlset.findtext(tag)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("XML reference outside package")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source / relative), str(destination))
if found != approved:
    raise ValueError("approved GNR schemas missing from pinned XML")
tree.write(str(target / "xml/pmt.xml"), encoding="utf-8", xml_declaration=True)
PY
(cd "${stage}/bundled-platform-data" &&
    find License Readme.md xml -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)

cat >"${stage}/bundled-platform-data/SOURCE.txt" <<EOF
Intel PMT GNR subset for this package
Commit: ${PLATFORM_COMMIT}
Source: approved Intel platform-data repository
Selection: seven qualified GNR GUID+Size mappings; schema files copied unchanged
Registry: bundled-platform-data/xml/pmt.xml
EOF

cat >"${stage}/BUNDLED_PLATFORM_DATA.md" <<EOF
# Bundled Intel PMT Platform Data

This package includes seven GNR mappings selected from the Intel PMT XML registry at commit
\`${PLATFORM_COMMIT}\`. Schema contents are unchanged. \`validate-platform\` and \`analyze\` use the bundled
registry automatically when \`--metadata\` is omitted. An explicit
\`--metadata\` path takes precedence. \`bundled-platform-data/SHA256SUMS\`
covers every supplied platform-data file.

The GNR compatibility matrix lists the seven included schemas. Other platforms
are not bundled. The generated registry preserves only these mappings.
EOF

archive="${ROOT}/dist/${NAME}.tar.gz"
temporary_archive="${archive}.tmp"
tar -C "${temporary}" -czf "${temporary_archive}" "${NAME}"
mv "${temporary_archive}" "${archive}"
printf '%s\n' "${archive}"