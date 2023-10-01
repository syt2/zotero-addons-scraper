# Zotero Addons Scraper

This is a script repository for scraping Zotero addon collections for [Zotero7+](https://www.zotero.org), intended for use with [Zotero addons](https://github.com/syt2/zotero-addons).

The script utilizes the GitHub API and GitHub Actions to automatically scrape, parse, and publish corresponding addon information from the [addons](addons) file to the latest release.

## Contributing New Addons
If you have new addons to parse, add a new line in the [addons](addons) file with the format 
```
...
ADDONID, OWNER/REPOSITORY
```
where `ADDONID` is the id of the addon, and `OWNER/REPOSITORY` is the full name address of the addon's GitHub repository.
