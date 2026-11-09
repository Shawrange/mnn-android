from pathlib import Path
import json
import urllib.request
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
target = root / 'evidence' / 'installation'
target.mkdir(parents=True, exist_ok=True)
url = 'https://dl.google.com/android/repository/repository2-3.xml'
with urllib.request.urlopen(url, timeout=45) as response:
    raw = response.read()
(target / 'android-repository.xml').write_bytes(raw)
tree = ET.fromstring(raw)
package = next(p for p in tree.iter('remotePackage') if p.get('path') == 'ndk;27.2.12479018')
archive = next(a for a in package.findall('./archives/archive') if a.findtext('host-os') == 'linux')
complete = archive.find('complete')
checksum = complete.find('checksum')
metadata = {
    'repository_url': url,
    'package': package.get('path'),
    'host_os': 'linux',
    'url': 'https://dl.google.com/android/repository/' + complete.findtext('url'),
    'size': int(complete.findtext('size')),
    'checksum_type': checksum.get('type'),
    'checksum': checksum.text.strip(),
}
(target / 'ndk-download.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata, indent=2))
