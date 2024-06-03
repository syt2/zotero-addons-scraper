class AddonInfoAuthor:
    def __init__(self, name: str = None, url: str = None, avatar: str = None,
                 **kwargs):
        self.name = name
        self.url = url
        self.avatar = avatar
        [setattr(self, key, value) for (key, value) in kwargs.items()]

    @property
    def __dict__(self):
        result = {}
        if self.name:
            result["name"] = self.name
        if self.url:
            result["url"] = self.url
        if self.avatar:
            result["avatar"] = self.avatar
        return result


class AddonInfoRelease:
    def __init__(self, targetZoteroVersion: str, tagName: str,
                 xpiDownloadUrl: dict = None, releaseDate: str = None, id: str = None, xpiVersion: str = None,
                 name: str = None, description: str = None,
                 minZoteroVersion: str = None, maxZoteroVersion: str = None,
                 **kwargs):
        self.targetZoteroVersion = targetZoteroVersion
        self.tagName = tagName
        self.xpiDownloadUrl = xpiDownloadUrl
        self.releaseDate = releaseDate
        self.id = id
        self.xpiVersion = xpiVersion
        self.name = name
        self.description = description
        self.minZoteroVersion = minZoteroVersion
        self.maxZoteroVersion = maxZoteroVersion
        [setattr(self, key, value) for (key, value) in kwargs.items()]

    @property
    def zotero_check_version(self) -> str:
        if self.targetZoteroVersion == '6':
            return '6.0.*'
        elif self.targetZoteroVersion == '7':
            return '7.0.*'
        raise Exception(f'Invalid targetZoteroVersion({self.targetZoteroVersion})')

    @property
    def __dict__(self):
        result = {}
        if self.targetZoteroVersion:
            result["targetZoteroVersion"] = self.targetZoteroVersion
        if self.tagName:
            result["tagName"] = self.tagName
        if self.xpiDownloadUrl:
            result["xpiDownloadUrl"] = self.xpiDownloadUrl
        if self.releaseDate:
            result["releaseDate"] = self.releaseDate
        if self.id:
            result["id"] = self.id
        if self.xpiVersion:
            result["xpiVersion"] = self.xpiVersion
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.minZoteroVersion:
            result["minZoteroVersion"] = self.minZoteroVersion
        if self.maxZoteroVersion:
            result["maxZoteroVersion"] = self.maxZoteroVersion
        return result


class AddonInfo:
    def __init__(self, repo: str,
                 releases: list[dict] | list[AddonInfoRelease],
                 name: str = None,
                 description: str = None,
                 stars: int = None,
                 author: dict | AddonInfoAuthor = None,
                 **kwargs):
        self.repo = repo
        self.releases = [e if isinstance(e, AddonInfoRelease) else AddonInfoRelease(**(e if e else {})) for e in releases]
        self.name = name
        self.description = description
        self.stars = stars
        self.author = author if isinstance(author, AddonInfoAuthor) else AddonInfoAuthor(**(author if author else {}))
        [setattr(self, key, value) for (key, value) in kwargs.items()]

    @property
    def owner(self):
        if len(self.repo.split('/')) != 2:
            return None
        return self.repo.split('/')[0]

    @property
    def repository(self):
        if len(self.repo.split('/')) != 2:
            return None
        return self.repo.split('/')[1]

    @property
    def __dict__(self):
        result = {}
        if self.repo:
            result["repo"] = self.repo
        if self.releases:
            result["releases"] = [release.__dict__ for release in self.releases]
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.stars:
            result["stars"] = self.stars
            # todo: Deprecation, used for z7 < 1.5.3 and z6 < 0.6.7
            result["star"] = self.stars
        if self.author:
            result["author"] = self.author.__dict__
        return result
