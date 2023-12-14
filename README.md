# Zotero Addons Scraper
![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/syt2/zotero-addons-scraper/main.yml)
![GitHub Last Commit Time](https://img.shields.io/github/last-commit/syt2/zotero-addons-scraper/publish)

This is a script repository for scraping Zotero addon collections for [Zotero](https://www.zotero.org), intended for use with [Zotero addons](https://github.com/syt2/zotero-addons).  
> Switch to `(addon-scraper)` source in [Zotero addons](https://github.com/syt2/zotero-addons) to use this repository.

The script utilizes the GitHub API and GitHub Actions to automatically scrape and parse addon information from the [addons](addons) folder, and publish to [`publish`](https://github.com/syt2/zotero-addons-scraper/blob/publish/addon_infos.json) branch and the latest release every day.

## Contributing New Addons
If you have a new add-on to add, add an add-on information file in the [addons](addons) folder.

The file format should be as follows:  
``` json
{
  "name": "Zotero Addons",
  "repo": "syt2/zotero-addons",
  "releases": [
    {   
      "targetZoteroVersion": "7",
      "tagName": "latest"
    },
    {   
      "targetZoteroVersion": "6", 
      "tagName": "0.6.0-3"
    }
  ]
}
```

- `name`(optional):  
  The name of the plugin.  
  If not provided, the name will be extracted automatically from the XPI provided in release.
- `repo`(required):  
  The GitHub repository address of the plugin.
- `releases`(required):  
  Information about the plugin's XPI releases.  
  Provide at least one valid plugin release information.
- `targetZoteroVersion`(required):  
  The Zotero compatibility version for the plugin.
  Supports `"6"` or `"7"`.
- `tagName`(required):
  The release information in the GitHub repository.  
  Supports `"latest"`, `"pre"` or a specified tag name.  
  If `"latest"` or `"pre"` is used, the script will automatically retrieve the latest release information.  

## Generated Format
The output format for add-on information follows the format specified in [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins).

