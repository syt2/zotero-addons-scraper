# modify from `https://github.com/
# mozilla/gecko-dev/blob/ac19e2c0d7c09a2deaedbe6afc4cdcf1a4561456/testing/mozbase/mozprofile/mozprofile/addons.py#L213`

import zipfile
import commentjson as json
import os
from xml.dom import minidom
import re


def compare_versions(version1, version2):
    parts1 = version1.replace('-', '.').split('.')
    parts2 = version2.replace('-', '.').split('.')

    for i in range(max(len(parts1), len(parts2))):
        v1 = parts1[i] if i < len(parts1) else '0'
        v2 = parts2[i] if i < len(parts2) else '0'
        try:
            num1 = int(v1)
        except ValueError:
            num1 = v1
        try:
            num2 = int(v2)
        except ValueError:
            num2 = v2

        if isinstance(num1, int) and isinstance(num2, int):
            if num1 < num2:
                return -1
            if num1 > num2:
                return 1
        else:
            if v1 < v2:
                return -1
            if v1 > v2:
                return 1
    return 0


class XpiDetail:
    def __init__(self):
        self.id = None
        self.name = None
        self.version = None
        self.description = None
        self.min_version = "*"
        self.max_version = "*"

    def _append_info(self, details: dict):
        if id := details.get('id'):
            if self.id and self.id != id:
                print(f'Xpi ID not match? {self.id} <==> {id}')
                return
            self.id = id
        if name := details.get('name'):
            self.name = name
        if version := details.get('version'):
            self.version = version
        if description := details.get('description'):
            self.description = description
        if (min_version := details.get('min_version')) and (max_version := details.get('max_version')):
            if compare_versions(min_version.replace('*', '0'), self.min_version.replace('*', '999')) <= 0:
                self.min_version = min_version
            if compare_versions(max_version.replace('*', '999'), self.max_version.replace('*', '0')) >= 0:
                self.max_version = max_version

    def check_compatible_for_zotero_version(self, version: str | int):
        if isinstance(version, int):
            version = str(version) + '.*'
        if (min_version := self.min_version.replace('*', '0')) and (max_version := self.max_version.replace('*', '999')):
            return (compare_versions(min_version, version.replace('*', '999')) <= 0
                    <= compare_versions(max_version, version.replace('*', '0')))


def get_namespace_id(doc, url):
    attributes = doc.documentElement.attributes
    for i in range(attributes.length):
        if attributes.item(i).value == url and ":" in attributes.item(i).name:
            return attributes.item(i).name.split(":")[1] + ":"
    return ""


def get_text(element):
    """Retrieve the text value of a given node"""
    rc = []
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return "".join(rc).strip()


def manifest_from_json(addon_path):
    try:
        if zipfile.is_zipfile(addon_path):
            with zipfile.ZipFile(addon_path, "r") as compressed_file:
                filenames = [f.filename for f in compressed_file.filelist]
                if "manifest.json" in filenames:
                    manifest = compressed_file.read("manifest.json").decode()
                    manifest = json.loads(manifest)
                    return manifest
        elif os.path.isdir(addon_path):
            with open(os.path.join(addon_path, "manifest.json")) as f:
                manifest = json.loads(f.read())
                return manifest
    except Exception as e:
        print(f'Invalid Addon Path {addon_path}: {e}')


def manifest_from_rdf(addon_path):
    try:
        if zipfile.is_zipfile(addon_path):
            with zipfile.ZipFile(addon_path, "r") as compressed_file:
                filenames = [f.filename for f in compressed_file.filelist]
                if "install.rdf" in filenames:
                    manifest = compressed_file.read("install.rdf")
                    return manifest
        elif os.path.isdir(addon_path):
            with open(os.path.join(addon_path, "install.rdf")) as f:
                manifest = json.loads(f.read())
                return manifest
    except Exception as e:
        print(f'Invalid Addon Path {addon_path}: {e}')


def detail_from_manifest_json(addon_path, manifest):
    details = {
        "name": manifest.get("name"), "version": manifest.get("version"), "description": manifest.get("description"),
        "id": None, "min_version": None, "max_version": None
    }
    for location in ("applications", "browser_specific_settings"):
        if details["id"]:
            break
        for app in ("zotero", "gecko"):
            try:
                details["id"] = manifest[location][app].get("id")
                details["min_version"] = manifest[location][app].get("strict_min_version")
                details["max_version"] = manifest[location][app].get("strict_max_version")
                break
            except KeyError:
                continue

    # handler for __MSG_{}__ items
    def extract_msg_placeholder(text):
        if match := re.search(r'__MSG_(.*?)__', text):
            return match.group(1)

    def load_locale_for_msg():
        default_locale = manifest.get('default_locale')
        locale_filename = f"_locales/{default_locale}/messages.json"
        try:
            if zipfile.is_zipfile(addon_path):
                with zipfile.ZipFile(addon_path, "r") as compressed_file:
                    filenames = [f.filename for f in compressed_file.filelist]
                    if locale_filename in filenames:
                        locale = compressed_file.read(locale_filename).decode()
                        return json.loads(locale)
            elif os.path.isdir(addon_path):
                with open(os.path.join(addon_path, locale_filename)) as f:
                    return json.loads(f.read())
        except Exception as e:
            raise e

    locale_for_msg = None
    for key in details:
        if isinstance(details[key], str) and (placeholder := extract_msg_placeholder(details[key])):
            if not locale_for_msg:
                locale_for_msg = load_locale_for_msg()
            if not locale_for_msg:
                break
            if value := locale_for_msg.get(placeholder, {}).get('message'):
                details[key] = value

    return details


def detail_from_manifest_rdf(manifest):
    details = {"id": None, "name": None, "version": None, "description": None, "min_version": None, "max_version": None}
    try:
        doc = minidom.parseString(manifest)

        # Get the namespaces abbreviations
        em = get_namespace_id(doc, "http://www.mozilla.org/2004/em-rdf#")
        rdf = get_namespace_id(doc, "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

        description = doc.getElementsByTagName(rdf + "Description").item(0)
        try:
            descriptions = [e for e in doc.getElementsByTagName(rdf + "Description")
                            if len(e.getElementsByTagName(em + "targetApplication")) > 0]
            if descriptions:
                description = descriptions[0]
        except Exception as e:
            pass

        def extract_info(node, result):
            try:
                for entry, value in node.attributes.items():
                    entry = entry.replace(em, "")
                    if entry in result.keys():
                        result.update({entry: value})
                for child_node in node.childNodes:
                    entry = child_node.nodeName.replace(em, "")
                    if entry in result.keys():
                        result.update({entry: get_text(child_node)})
            except:
                return
        extract_info(description, details)

        def update_details(version_info):
            if version_info['id'] != 'zotero@chnm.gmu.edu':
                return
            if (min_version := version_info['minVersion']) and (max_version := version_info['maxVersion']):
                if exist_min_version := details['min_version']:
                    if compare_versions(min_version.replace('*', '0'), exist_min_version.replace('*', '999')) <= 0:
                        details['min_version'] = min_version
                else:
                    details['min_version'] = min_version

                if compare_versions(max_version.replace('*', '999'), '6.*') > 0:
                    # rdf not support z7
                    max_version = '6.*'
                if exist_max_version := details['max_version']:
                    if compare_versions(max_version.replace('*', '999'), exist_max_version.replace('*', '0')) >= 0:
                        details['max_version'] = max_version
                else:
                    details['max_version'] = max_version


        for targetApplication in description.getElementsByTagName(em + "targetApplication"):
            version_info = {'id': None, 'minVersion': None, 'maxVersion': None}
            extract_info(targetApplication, version_info)
            update_details(version_info)

            for node in targetApplication.childNodes:
                version_info = {'id': None, 'minVersion': None, 'maxVersion': None}
                extract_info(node, version_info)
                update_details(version_info)

        return details
    except Exception as e:
        raise e


def addon_details(addon_path) -> XpiDetail:
    if not os.path.exists(addon_path):
        raise IOError(f"Add-on path does not exist: {addon_path}")
    xpi_detail = XpiDetail()
    if ((manifest := manifest_from_json(addon_path)) and
            (details := detail_from_manifest_json(addon_path, manifest))):
        xpi_detail._append_info(details)
    if ((manifest := manifest_from_rdf(addon_path)) and
            (details := detail_from_manifest_rdf(manifest))):
        xpi_detail._append_info(details)
    return xpi_detail
