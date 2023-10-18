id                                      = "id"
name                                    = "name"
repo                                    = "repo"
releases                                = "releases"
targetZoteroVersion                     = "targetZoteroVersion"
tagName                                 = "tagName"
currentVersion                          = "currentVersion"
xpiDownloadUrl                          = "xpiDownloadUrl"
github                                  = "github"
gitee                                   = "gitee"
ghProxy                                 = "ghProxy"
jsdeliver                               = "jsdeliver"
kgithub                                 = "kgithub"
releaseData                             = "releaseData"
downloadCount                           = "downloadCount"
assetId                                 = "assetId"
description                             = "description"
star                                    = "star"
author                                  = "author"
url                                     = "url"
avatar                                  = "avatar"


# from https://github.com/zotero-chinese/zotero-plugins/blob/main/src/plugins.ts
# export interface PluginInfo {
#   /**
#    * 插件名称
#    */
#   name: string;
#   /**
#    * 插件仓库
#    *
#    * 例如：northword/zotero-format-metadata
#    *
#    * 注意前后均无 `/`
#    */
#   repo: string;
#   /**
#    * 插件的发布地址信息
#    */
#   releases: Array<{
#     /**
#      * 当前发布版对应的 Zotero 版本
#      */
#     targetZoteroVersion: string;
#     /**
#      * 当前发布版对应的下载通道
#      *
#      * `latest`：最新正式发布；
#      * `pre`：最新预发布；
#      * `string`：发布对应的 `git.tag_name`；
#      * 注意 `git.tag_name` 有的有 `v` 而有的没有，可以通过发布链接来判断
#      */
#     tagName: "latest" | "pre" | string;
#
#     currentVersion?: string;
#     xpiDownloadUrl?: {
#       github: string;
#       gitee: string;
#       ghProxy: string;
#       jsdeliver: string;
#       kgithub: string;
#     };
#     releaseData?: string;
#     downloadCount?: number;
#     assetId?: number;
#   }>;
#
#   description?: string;
#   star?: number;
#   author?: {
#     name: string;
#     url: string;
#     avatar: string;
#   };
# }