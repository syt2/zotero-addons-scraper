# 从 zotero-chinese 仓库解析json并更新此仓库的json
import json
import os.path

from addon_keys import *

# 从 https://raw.githubusercontent.com/zotero-chinese/zotero-plugins/main/src/plugins.ts 替换为最新的plugins信息
plugins = [
  {
    name: "Zotero 插件合集",
    repo: "syt2/zotero-addons",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.6.0-3",
      },
    ],
  },
  {
    name: "Actions and Tags for Zotero",
    repo: "windingwind/zotero-actions-tags",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Awesome GPT",
    repo: "MuiseDestiny/zotero-gpt",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Better BibTex for Zotero",
    repo: "retorquere/zotero-better-bibtex",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Better Notes for Zotero",
    repo: "windingwind/zotero-better-notes",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Chartero",
    repo: "volatile-static/Chartero",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "1.3.3",
      },
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Crush Reference",
    repo: "MuiseDestiny/zotero-reference",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "DelItemWithAtt",
    repo: "redleafnew/delitemwithatt",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.1.06",
      },
    ],
  },
  {
    name: "Eaiser Citation",
    repo: "MuiseDestiny/eaiser-citation",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.3.1",
      },
    ],
  },
  {
    name: "Ethereal Style",
    repo: "MuiseDestiny/ZoteroStyle",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Green Frog",
    repo: "redleafnew/zotero-updateifsE",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.13.0",
      },
    ],
  },
  {
    name: "PMCID fetcher for Zotero",
    repo: "retorquere/zotero-pmcid-fetcher",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Jasminum",
    repo: "l0o0/jasminum",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "KeepZotero",
    repo: "yhmtsai/KeepZotero",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Linter for Zotero",
    repo: "northword/zotero-format-metadata",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.4.4",
      },
    ],
  },
  {
    name: "LyZ",
    repo: "wshanks/lyz",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "MarkDBConnect",
    repo: "daeh/zotero-obsidian-citations",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Mdnotes for Zotero",
    repo: "argenos/zotero-mdnotes",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Night for Zotero",
    repo: "tefkah/zotero-night",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Notero",
    repo: "dvanoni/notero",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Open PDF",
    repo: "retorquere/zotero-open-pdf",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "PDF Figure",
    repo: "MuiseDestiny/zotero-figure",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "6",
        tagName: "0.0.7",
      },
    ],
  },
  {
    name: "Preview for Zotero",
    repo: "windingwind/zotero-pdf-preview",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
    ],
  },
  {
    name: "Reading List for Zotero",
    repo: "Dominic-DallOsto/zotero-reading-list",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Sci-Hub Plugin for Zotero",
    repo: "ethanwillis/zotero-scihub",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "scite Plugin for Zotero",
    repo: "scitedotai/scite-zotero-plugin",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Storage Scanner for Zotero",
    repo: "retorquere/zotero-storage-scanner",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Tara",
    repo: "l0o0/tara",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Translate for Zotero",
    repo: "windingwind/zotero-pdf-translate",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "ZotCard",
    repo: "018/zotcard",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero Better Authors",
    repo: "github-young/zotero-better-authors",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero Citation Counts Manager",
    repo: "eschnett/zotero-citationcounts",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero Storage Scanner",
    repo: "retorquere/zotero-storage-scanner",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero Inspire",
    repo: "fkguo/zotero-inspire",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "pre",
      },
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero OCR",
    repo: "UB-Mannheim/zotero-ocr",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero ShortDOI",
    repo: "bwiernik/zotero-shortdoi",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero TL;DR",
    repo: "syt2/Zotero-TLDR",
    releases: [
      {
        targetZoteroVersion: "7",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zotero 更新影响因子",
    repo: "redleafnew/zotero-updateifs",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "ZotFile",
    repo: "jlegewie/zotfile",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "ZotFile 汉化版",
    repo: "lychichem/zotfile",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
  {
    name: "Zutilo Utility for Zotero",
    repo: "wshanks/Zutilo",
    releases: [
      {
        targetZoteroVersion: "6",
        tagName: "latest",
      },
    ],
  },
]

for plugin in plugins:
    json_name = plugin[repo].replace('/', '#')
    file_path = os.path.join('../addons', json_name + '.json')

    content = {}
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            content = json.load(file)

    for key in plugin:
        content[key] = plugin[key]
    with open(file_path, "w") as json_file:
        json.dump(content, json_file, ensure_ascii=False, indent='  ')
