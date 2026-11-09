#!/usr/bin/env bash
set -euo pipefail
evidence=/mnt/e/DUANCE/gate0/evidence/installation
mkdir -p "$evidence"
exec > >(tee "$evidence/ndk-install.log") 2>&1
trap 'code=$?; printf "%s\n" "$code" > "$evidence/ndk-install.exit.txt"' EXIT
python3 - <<'PY'
from pathlib import Path
import hashlib, json, os, stat, zipfile
root=Path('/mnt/e/DUANCE/gate0')
archive=root/'downloads/android-ndk-r27c-linux.zip'
metadata=json.loads((root/'evidence/installation/ndk-download.json').read_text())
with archive.open('rb') as f:
    assert hashlib.file_digest(f,'sha1').hexdigest()==metadata['checksum']
install=Path.home()/'Android'
ndk=install/'android-ndk-r27c'
if ndk.exists():
    raise SystemExit(f'Installation directory already exists; inspect before replacing: {ndk}')
install.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        target=install/member.filename
        assert target.resolve().is_relative_to(install.resolve())
        mode=member.external_attr >> 16
        if stat.S_ISLNK(mode):
            target.parent.mkdir(parents=True,exist_ok=True)
            link=z.read(member).decode()
            assert (target.parent/link).resolve().is_relative_to(install.resolve())
            os.symlink(link,target)
        else:
            z.extract(member,install)
            if mode:
                target.chmod(stat.S_IMODE(mode))
print(f'Installed Linux NDK at {ndk}')
(root/'evidence/installation/ndk-path.txt').write_text(str(ndk)+'\n')
PY
ndk_path=$(cat "$evidence/ndk-path.txt")
cat "$ndk_path/source.properties"
file "$ndk_path/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
"$ndk_path/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++" --version
