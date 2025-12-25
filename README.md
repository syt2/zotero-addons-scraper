# Zotero Addons Scraper
![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/syt2/zotero-addons-scraper/main.yml?logo=githubactions)
![GitHub Last Commit Time](https://img.shields.io/github/last-commit/syt2/zotero-addons-scraper/publish?logo=github)
![jsdelivr hits](https://img.shields.io/jsdelivr/gh/hw/syt2/zotero-addons-scraper?logo=jsdelivr)


This is a script repository for scraping [Zotero](https://www.zotero.org) add-ons, intended for use with [Zotero Addons](https://github.com/syt2/zotero-addons).  
> Switch to `addon-scraper` source in [Zotero Addons](https://github.com/syt2/zotero-addons) to use this repository.

## Workflows
This repository utilizes GitHub Actions workflow for automation. 
including the following steps:
- Retrieve [Zotero](https://www.zotero.org) add-on information specified in [addons](addons) folder
- Parse add-on information into JSON data
- Publish the JSON data to the [`publish`](https://github.com/syt2/zotero-addons-scraper/blob/publish/addon_infos.json) branch and the [latest release](https://github.com/syt2/zotero-addons-scraper/releases/latest)

## Contributing
Adding a new add-on entry `{owner}@{repo}` in the [addons](addons) folder.

## Usage
1. `fork` this repository
2. Enable actions and scheduled workflow in `Actions` page of forked repository

## Generated Format
The output format for add-on information follows the format specified in [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins).

