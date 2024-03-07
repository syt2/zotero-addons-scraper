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
Adding a new add-on entry `{owner}#{repo}.json` in the [addons](addons) folder.  
e.g.,
``` json
{
  "repo": "syt2/zotero-addons",
  "releases": [
    {   
      "targetZoteroVersion": "7",
      "tagName": "latest"
    },
    {
      "targetZoteroVersion": "6", 
      "tagName": "0.6.0-6"
    }
  ]
}
```
 
- `repo`(required):  
  GitHub repository of the plugin.  
- `releases`(required):  
  XPI releases information of the Add-on.  
  Provide at least one valid release information.
- `targetZoteroVersion`(required):  
  Zotero compatibility version for the add-on.
  Supports `"6"` or `"7"`.
- `tagName`(required):
  The release tag name in the GitHub repository.  
  Supports `"latest"`, `"pre"` or `a specified tag name`.  
  *If `"latest"` is used, script will automatically retrieve the latest release tag.* 
  *If `"pre"` is used, script will automatically retrieve the latest pre-release tag.* 


## Usage
1. `fork` this repository
2. Enable actions and scheduled workflow in `Actions` page of forked repository
3. Add a `Deploy key` in forked repository and named it with `ACTIONS_DEPLOY_KEY`

## Generated Format
The output format for add-on information follows the format specified in [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins).

