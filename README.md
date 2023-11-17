# Zotero Addons Scraper
![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/syt2/zotero-addons-scraper/main.yml)
![GitHub Last Commit Time](https://img.shields.io/github/last-commit/syt2/zotero-addons-scraper/publish)

This is a script repository for scraping Zotero addon collections for [Zotero](https://www.zotero.org), intended for use with [Zotero addons](https://github.com/syt2/zotero-addons).

*Switch to `(addon-scraper)` source in [Zotero addons](https://github.com/syt2/zotero-addons) to use this repository.*

The script utilizes the GitHub API and GitHub Actions to automatically scrape and parse addon information from the [addons](addons) folder, and publish to [`publish`](https://github.com/syt2/zotero-addons-scraper/blob/publish/addon_infos.json) branch and the latest release every day.

## Contributing New Addons
If you have new add-ons to parse, add the json information of the add-on with the name format of `repo.replace('/', '#').json` in the [addons](addons) folder with the format 
``` json
{
  "id": "zoteroAddons@ytshen.com",
  "name": "Zotero Addons",
  "repo": "syt2/zotero-addons",
  "releases": [
    {
      "targetZoteroVersion": "7",
      "tagName": "latest"
    }
  ]
}
```

## Addon Information Format

The output format for add-on information follows the format specified in [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins), which is as follows:
```ts
export interface PluginInfo {
  id?: string;
  /**
   * 插件名称
   */
  name: string;
  /**
   * 插件仓库
   *
   * 例如：northword/zotero-format-metadata
   *
   * 注意前后均无 `/`
   */
  repo: string;
  /**
   * 插件的发布地址信息
   */
  releases: Array<{
    /**
     * 当前发布版对应的 Zotero 版本
     */
    targetZoteroVersion: string;
    /**
     * 当前发布版对应的下载通道
     *
     * `latest`：最新正式发布；
     * `pre`：最新预发布；
     * `string`：发布对应的 `git.tag_name`；
     * 注意 `git.tag_name` 有的有 `v` 而有的没有，可以通过发布链接来判断
     */
    tagName: "latest" | "pre" | string;

    currentVersion?: string;
    xpiDownloadUrl?: {
      github: string;
      gitee: string;
      ghProxy: string;
      jsdeliver: string;
      kgithub: string;
    };
    releaseData?: string;
    downloadCount?: number;
    assetId?: number;
    
    /**
     * 从插件中解析的信息
     *
     * TODO：后续视 zotero-chinese/zotero-plugins 的情况更新
     */
    xpiInfo?: {
      id?: string;
      name?: string;
      currentVersion?: string;
    };
  }>;

  description?: string;
  star?: number;
  author?: {
    name: string;
    url: string;
    avatar: string;
  };
}
```
