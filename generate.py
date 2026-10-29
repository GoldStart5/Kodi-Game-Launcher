import os, re, zipfile, hashlib, shutil

OUT = "zips"
SKIP_DIRS = {".git", "__pycache__"}
os.makedirs(OUT, exist_ok=True)
entries = []

for d in sorted(os.listdir(".")):
    xml_path = os.path.join(d, "addon.xml")
    if d == OUT or not os.path.isfile(xml_path):
        continue
    xml = open(xml_path, encoding="utf-8").read()
    addon_id = re.search(r'<addon[^>]*\sid="([^"]+)"', xml).group(1)
    version = re.search(r'<addon[^>]*\sversion="([^"]+)"', xml).group(1)
    if addon_id != d:
        raise SystemExit(f"Folder '{d}' does not match addon id '{addon_id}'")
    entries.append(re.sub(r'<\?xml[^>]*\?>\s*', '', xml).strip())

    dest = os.path.join(OUT, d)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(os.path.join(dest, f"{d}-{version}.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                p = os.path.join(root, f)
                z.write(p, p)  # zip root folder must equal the addon id

    # Kodi fetches icon/fanart from <datadir>/<id>/<path declared in <assets>>
    for tag in ("icon", "fanart", "banner", "clearlogo"):
        m = re.search(rf"<{tag}>([^<]+)</{tag}>", xml)
        if m:
            rel = m.group(1).strip()
            src = os.path.join(d, rel)
            if os.path.isfile(src):
                target = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(src, target)

index = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + "\n".join(entries) + "\n</addons>\n"
with open(os.path.join(OUT, "addons.xml"), "w", encoding="utf-8", newline="\n") as f:
    f.write(index)
with open(os.path.join(OUT, "addons.xml.md5"), "w") as f:
    f.write(hashlib.md5(index.encode("utf-8")).hexdigest())
print("Done:", len(entries), "addons")
