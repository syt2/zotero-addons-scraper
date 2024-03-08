import json
import os

# convert addon from zotero-chinese

repo = 'repo'
releases = 'releases'
targetZoteroVersion = 'targetZoteroVersion'
tagName = 'tagName'

PluginInfoBase = []


for addon in PluginInfoBase:
    filename = addon[repo].replace('/', '#') + '.json'
    with open(os.path.join('addons', filename), 'w') as f:
        json.dump(addon, f, ensure_ascii=False, indent='  ')
