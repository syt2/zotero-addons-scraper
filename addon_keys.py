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
id                                      = "id"
xpiVersion                              = "xpiVersion"
description                             = "description"
star                                    = "star"
author                                  = "author"
url                                     = "url"
avatar                                  = "avatar"


# from https://github.com/zotero-chinese/zotero-plugins/blob/main/src/plugins.ts
# export interface PluginInfo {
#   // plugin id
#   // @deprecated This property is deprecated. Use the id in releases instead.
#   id?: string;
#
#   // plugin name
#   name?: string;
#
#   // plugin repository address on GitHub
#   // e.g., syt2/zotero-addons
#   repo: string;
#
#   // plugin releases information
#   releases: Array<{
#     // Zotero version corresponding to current release
#     targetZoteroVersion: string;
#
#     // Download channel corresponding to the current release version
#     // `latest`: Latest stable release
#     // `pre`: Latest pre-release
#     // `string`: Corresponding to the `git.tag_name` of the release;
#     tagName: "latest" | "pre" | string;
#     // @deprecated This property is deprecated. Use tagName instead.
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
#     // plugin xpi id
#     id?: string;
#     // plugin xpi version
#     xpiVersion?: string;
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
