import zipfile
import json
import os
from xml.dom import minidom


# modify from `https://github.com/mozilla/gecko-dev/blob/ac19e2c0d7c09a2deaedbe6afc4cdcf1a4561456/testing/mozbase/mozprofile/mozprofile/addons.py#L213`
def addon_details(addon_path):
    """
    Returns a dictionary of details about the addon.

    :param addon_path: path to the add-on directory or XPI

    Returns::

        {'id':      u'rainbow@colors.org', # id of the addon
         'version': u'1.4',                # version of the addon
         'name':    u'Rainbow',            # name of the addon
         'unpack':  False }                # whether to unpack the addon
    """

    details = {"id": None, "unpack": False, "name": None, "version": None}

    def get_namespace_id(doc, url):
        attributes = doc.documentElement.attributes
        namespace = ""
        for i in range(attributes.length):
            if attributes.item(i).value == url:
                if ":" in attributes.item(i).name:
                    # If the namespace is not the default one remove 'xlmns:'
                    namespace = attributes.item(i).name.split(":")[1] + ":"
                    break
        return namespace

    def get_text(element):
        """Retrieve the text value of a given node"""
        rc = []
        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return "".join(rc).strip()

    if not os.path.exists(addon_path):
        raise IOError("Add-on path does not exist: %s" % addon_path)

    is_webext = False
    try:
        if zipfile.is_zipfile(addon_path):
            # Bug 944361 - We cannot use 'with' together with zipFile because
            # it will cause an exception thrown in Python 2.6.
            try:
                compressed_file = zipfile.ZipFile(addon_path, "r")
                filenames = [f.filename for f in (compressed_file).filelist]
                if "manifest.json" in filenames:
                    is_webext = True
                    manifest = compressed_file.read("manifest.json").decode()
                    manifest = json.loads(manifest)
                elif "install.rdf" in filenames:
                    manifest = compressed_file.read("install.rdf")
                else:
                    raise KeyError("No manifest")
            finally:
                compressed_file.close()
        elif os.path.isdir(addon_path):
            try:
                with open(os.path.join(addon_path, "manifest.json")) as f:
                    manifest = json.loads(f.read())
                    is_webext = True
            except IOError:
                with open(os.path.join(addon_path, "install.rdf")) as f:
                    manifest = f.read()
        else:
            raise IOError(
                "Add-on path is neither an XPI nor a directory: %s" % addon_path
            )
    except (IOError, KeyError) as e:
        # reraise(AddonFormatError, AddonFormatError(str(e)), sys.exc_info()[2])
        raise e

    if is_webext:
        details["version"] = manifest["version"]
        details["name"] = manifest["name"]
        # Bug 1572404 - we support two locations for gecko-specific
        # metadata.
        for location in ("applications", "browser_specific_settings"):
            for app in ("gecko", "zotero"):
                try:
                    details["id"] = manifest[location][app]["id"]
                    break
                except KeyError:
                    pass
        # if details["id"] is None:
        #     details["id"] = cls._gen_iid(addon_path)
        details["unpack"] = False
    else:
        try:
            doc = minidom.parseString(manifest)

            # Get the namespaces abbreviations
            em = get_namespace_id(doc, "http://www.mozilla.org/2004/em-rdf#")
            rdf = get_namespace_id(
                doc, "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            )

            description = doc.getElementsByTagName(rdf + "Description").item(0)
            try:
                descriptions = [e for e in doc.getElementsByTagName(rdf + "Description")
                                if len(e.getElementsByTagName(em + "targetApplication")) > 0]
                if descriptions:
                    description = descriptions[0]
            except Exception as e:
                pass

            for entry, value in description.attributes.items():
                # Remove the namespace prefix from the tag for comparison
                entry = entry.replace(em, "")
                if entry in details.keys():
                    details.update({entry: value})
            for node in description.childNodes:
                # Remove the namespace prefix from the tag for comparison
                entry = node.nodeName.replace(em, "")
                if entry in details.keys():
                    details.update({entry: get_text(node)})
        except Exception as e:
            raise e

    # turn unpack into a true/false value
    if isinstance(details["unpack"], str):
        details["unpack"] = details["unpack"].lower() == "true"

    # If no ID is set, the add-on is invalid
    # if details.get("id") is None and not is_webext:
    #     raise AddonFormatError("Add-on id could not be found.")

    return details

