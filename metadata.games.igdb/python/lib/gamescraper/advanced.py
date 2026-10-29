"""Switch a few image-quality entries in Kodi's advancedsettings.xml on and off.

When ON the file contains
    <advancedsettings>
        <videolibrary><avoidtruefalse>true</avoidtruefalse></videolibrary>
        <imageres>9999</imageres>
        <fanartres>9999</fanartres>
    </advancedsettings>
When OFF those three entries are removed (an empty <videolibrary> goes with them,
and the file itself is deleted if nothing else is left in it).

Safety rules:
* everything else in the file (other settings, comments) is kept;
* a file that is not valid XML, or whose root is not <advancedsettings>, is never touched;
* the original file is copied to a .bak file once, before the first change;
* writes are atomic (temp file + rename).

Kodi reads advancedsettings.xml only at start-up, so a restart is needed afterwards.
"""
import json
import os
import xml.etree.ElementTree as ET

ROOT_TAG = 'advancedsettings'
LIBRARY_TAG = 'videolibrary'
ROOT_ENTRIES = (('imageres', '9999'), ('fanartres', '9999'))
LIBRARY_ENTRIES = (('avoidtruefalse', 'true'),)
BACKUP_SUFFIX = '.metadata.games.igdb.bak'


class AdvancedSettingsError(Exception):
    """The file could not be read or written safely; it has been left untouched."""


def _load(path):
    """Return the parsed tree, or None if the file does not exist."""
    if not os.path.exists(path):
        return None
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        tree = ET.parse(path, parser)
    except (ET.ParseError, OSError) as exc:
        raise AdvancedSettingsError('advancedsettings.xml could not be read (%s)' % exc)
    if tree.getroot().tag != ROOT_TAG:
        raise AdvancedSettingsError('advancedsettings.xml has an unexpected root element')
    return tree


def _write(tree, path):
    if hasattr(ET, 'indent'):
        ET.indent(tree)
    tmp = path + '.tmp'
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        tree.write(tmp, encoding='utf-8', xml_declaration=True)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise AdvancedSettingsError('advancedsettings.xml could not be written (%s)' % exc)


def _backup(path):
    backup = path + BACKUP_SUFFIX
    if os.path.exists(path) and not os.path.exists(backup):
        try:
            with open(path, 'rb') as src, open(backup, 'wb') as dst:
                dst.write(src.read())
        except OSError as exc:
            raise AdvancedSettingsError('could not back up advancedsettings.xml (%s)' % exc)


def _child(parent, tag):
    for element in parent:
        if element.tag == tag:
            return element
    return None


def _value(parent, tag):
    element = _child(parent, tag) if parent is not None else None
    return (element.text or '').strip().lower() if element is not None else None


def is_enabled(path):
    """True when all three entries are present with the expected values."""
    try:
        tree = _load(path)
    except AdvancedSettingsError:
        return False
    if tree is None:
        return False
    root = tree.getroot()
    library = _child(root, LIBRARY_TAG)
    return (all(_value(root, tag) == value for tag, value in ROOT_ENTRIES)
            and all(_value(library, tag) == value for tag, value in LIBRARY_ENTRIES))


def enable(path):
    """Write the entries (creating the file if needed). Returns True if the file changed."""
    if is_enabled(path):
        return False
    tree = _load(path)
    if tree is None:
        tree = ET.ElementTree(ET.Element(ROOT_TAG))
    else:
        _backup(path)
    root = tree.getroot()

    def put(parent, tag, value):
        element = _child(parent, tag)
        if element is None:
            element = ET.SubElement(parent, tag)
        element.text = value

    for tag, value in ROOT_ENTRIES:
        put(root, tag, value)
    library = _child(root, LIBRARY_TAG)
    if library is None:
        library = ET.SubElement(root, LIBRARY_TAG)
    for tag, value in LIBRARY_ENTRIES:
        put(library, tag, value)
    _write(tree, path)
    return True


def disable(path):
    """Remove the entries. Returns True if the file changed."""
    tree = _load(path)
    if tree is None:
        return False
    root = tree.getroot()
    changed = False
    for tag, _ in ROOT_ENTRIES:
        element = _child(root, tag)
        if element is not None:
            root.remove(element)
            changed = True
    library = _child(root, LIBRARY_TAG)
    if library is not None:
        for tag, _ in LIBRARY_ENTRIES:
            element = _child(library, tag)
            if element is not None:
                library.remove(element)
                changed = True
        if len(library) == 0 and not (library.text or '').strip():
            root.remove(library)
            changed = True
    if not changed:
        return False
    _backup(path)
    if len(root) == 0:          # nothing left, not even a comment: drop the empty file
        try:
            os.remove(path)
        except OSError as exc:
            raise AdvancedSettingsError('advancedsettings.xml could not be removed (%s)' % exc)
    else:
        _write(tree, path)
    return True


# -- remembering what we last applied, so only real toggle changes act ---------------

def load_state(state_path):
    """The last toggle value we applied, or None if we never have."""
    try:
        with open(state_path, 'r', encoding='utf-8') as handle:
            value = json.load(handle).get('applied')
        return value if isinstance(value, bool) else None
    except (OSError, ValueError, AttributeError):
        return None


def save_state(state_path, applied):
    try:
        os.makedirs(os.path.dirname(state_path) or '.', exist_ok=True)
        with open(state_path, 'w', encoding='utf-8') as handle:
            json.dump({'applied': bool(applied)}, handle)
    except OSError:
        pass


def adopt(xml_path, state_path):
    """First run: take the file's current state as the starting point; returns it.

    This is how an existing hand-written entry set is recognised (the toggle then
    starts ON) instead of being removed because the toggle defaults to OFF.
    """
    state = load_state(state_path)
    if state is None:
        state = is_enabled(xml_path)
        save_state(state_path, state)
    return state


def sync(want, xml_path, state_path):
    """Apply the toggle if (and only if) it differs from what was last applied.

    Returns 'enabled', 'disabled', or None when nothing needed doing. Raises
    AdvancedSettingsError if the file could not be changed; the remembered state
    is then left as it was.
    """
    last = adopt(xml_path, state_path)
    if bool(want) == last:
        return None
    if want:
        enable(xml_path)
    else:
        disable(xml_path)
    save_state(state_path, bool(want))
    return 'enabled' if want else 'disabled'
