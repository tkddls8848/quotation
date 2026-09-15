"""Container entry point: fixed paths, no user-supplied command arguments."""
import os
from pathlib import Path
import subprocess

profile = Path('/tmp/profile')
profile.mkdir()
(profile / 'user').mkdir()
# Disable macros and updating external document links in this fresh profile.
(profile / 'user/registrymodifications.xcu').write_text('''<?xml version="1.0"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
</oor:items>''', encoding='utf-8')
os.environ['HOME'] = '/tmp'
os.environ['XDG_CACHE_HOME'] = '/tmp/cache'
# The HWP filter must be chosen by type detection. Forcing it with
# --infilter=Hwp2002_Reader makes H2Orestart abort with "Unspecified
# Application Error" because its detect service never runs. Only H2Orestart
# claims the .hwp extension here, and the API validates the HWP 5.0 header
# before the file ever reaches this container.
result = subprocess.run([
    'soffice', '-env:UserInstallation=file:///tmp/profile', '--headless',
    '--nologo', '--nodefault', '--nofirststartwizard',
    '--convert-to', 'pdf:writer_pdf_Export',
    '--outdir', '/output', '/input/source.hwp',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=110)
output = Path('/output/source.pdf')
if result.returncode or not output.is_file() or output.stat().st_size == 0:
    raise SystemExit('HWP conversion failed')
