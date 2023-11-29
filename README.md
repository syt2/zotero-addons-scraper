# Zotero Addons Scraper
![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/syt2/zotero-addons-scraper/main.yml)
![GitHub Last Commit Time](https://img.shields.io/github/last-commit/syt2/zotero-addons-scraper/publish)

This is a script repository for scraping Zotero addon collections for [Zotero](https://www.zotero.org), intended for use with [Zotero addons](https://github.com/syt2/zotero-addons).

*Switch to `(addon-scraper)` source in [Zotero addons](https://github.com/syt2/zotero-addons) to use this repository.*

The script utilizes the GitHub API and GitHub Actions to automatically scrape and parse addon information from the [addons](addons) folder, and publish to [`publish`](https://github.com/syt2/zotero-addons-scraper/blob/publish/addon_infos.json) branch and the latest release every day.

## Contributing New Addons
If you have a new add-on to add, add an add-on information file in the [addons](addons) folder.

> typically, name it with `repo.replace('/', '#').json`
> 
> If an add-on has different IDs for different Zotero versions, split them into multiple JSON files with different filename.

The file format should be as follows:

``` json
{
  "id": "zoteroAddons@ytshen.com",
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
or 
``` json
{
  "repo": "syt2/zotero-scipdf",
  "releases": [
    {
      "targetZoteroVersion": "7",
      "tagName": "latest"
    }
  ]
}
```

## Generated Format
The output format for add-on information follows the format specified in [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins).

