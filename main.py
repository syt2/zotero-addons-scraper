import concurrent.futures
import json
import os
import time
import urllib.parse
import requests
import argparse
import shutil
import hashlib
from addon_info import *
from fallback_infos import fallback_if_need
from moz_addons import addon_details


def github_api_headers(**kwargs):
    result = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if github_token := kwargs.get('github_token'):
        result['Authorization'] = f'token {github_token}'
    return result


def report_issue(repo: str, title: str, body: str, **kwargs):
    if not repo:
        print('report issue repo not found')
        return
    try:
        response = requests.post(f'https://api.github.com/repos/{repo}/issues',
                                 headers=github_api_headers(github_token=kwargs.get('github_token')),
                                 json={
                                     'title': title,
                                     'body': body
                                 })

        # 检查响应
        if response.status_code == 201:
            print('Issue created successfully.')
            print('Issue URL:', response.json()['html_url'])
        else:
            print('Failed to create issue.')
            print('Response:', response.content)
    except Exception as e:
        print(f'report issue failed: {e}')


def download_xpi(xpi_url: str, download_dir: str, unique_name: str, force_download: bool, **kwargs):
    try:
        download_filepath = os.path.join(download_dir, unique_name)
        folder = os.path.dirname(download_filepath)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        if cache_dir := kwargs.get('cache_dir'):
            cache_filepath = os.path.join(cache_dir, unique_name)
            if not force_download and os.path.isfile(cache_filepath):
                shutil.copy(cache_filepath, download_filepath)  # copy to download filepath
                return download_filepath

        if not force_download and os.path.isfile(download_filepath):
            return download_filepath

        response = requests.get(xpi_url, stream=True)
        print(f'download {unique_name} from {xpi_url}')
        with open(download_filepath, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        return download_filepath
    except Exception as e:
        print(f'download {unique_name} from {xpi_url} failed: {e}')


# 输出格式参考 [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins)
def parse(plugin: AddonInfo, **kwargs):
    if not plugin.owner or not plugin.releases or len(plugin.releases) <= 0:
        return
    plugin.name = plugin.repository
    headers = github_api_headers(github_token=kwargs.get('github_token'))

    # fetch author info
    author_url = f"https://api.github.com/users/{plugin.owner}"
    try:
        author_resp = requests.get(author_url, headers=headers)
        author_resp_info = json.loads(author_resp.content)

        plugin.author.name = author_resp_info['name'] if 'name' in author_resp_info and author_resp_info['name'] else plugin.owner
        if 'html_url' in author_resp_info:
            plugin.author.url = author_resp_info['html_url']
        if 'avatar_url' in author_resp_info:
            plugin.author.avatar = author_resp_info['avatar_url']
    except Exception as e:
        print(f'request {author_url} failed: {e}')

    # fetch repo info
    repo_url = f'https://api.github.com/repos/{plugin.repo}'
    try:
        repos_resp = requests.get(repo_url, headers=headers)
        repos_info = json.loads(repos_resp.content)
        if 'description' in repos_info and repos_info['description'] and not plugin.description:
            plugin.description = repos_info['description']
        if 'stargazers_count' in repos_info and repos_info['stargazers_count'] is not None:
            plugin.stars = repos_info['stargazers_count']
    except Exception as e:
        print(f'request {repo_url} failed: {e}')

    # fetch release info
    invalid_releases = []
    for release in plugin.releases:
        if not release.tagName:
            continue
        release_url = f'https://api.github.com/repos/{plugin.repo}/releases'
        if release.tagName == 'latest':
            release_url += '/latest'
        elif release.tagName != 'pre':
            release_url += f'/tags/{release.tagName}'

        try:
            release_resp = requests.get(release_url, headers=headers)
            release_info = json.loads(release_resp.content)

            if release.tagName == 'pre':
                release_info = [info for info in release_info if info['prerelease']]
                if release_info:
                    release_info = release_info[0]
                else:
                    continue
            if 'tag_name' in release_info:
                release.tagName = release_info['tag_name']

            if 'assets' not in release_info:
                continue
            release_assets = release_info['assets']
            release_assets.sort(key=lambda item: item['updated_at'] if 'updated_at' in item else '', reverse=True)
            release_assets = [asset for asset in release_assets if asset['content_type'] == 'application/x-xpinstall']
            if not release_assets:
                continue
            release_asset = release_assets[0]
            if 'browser_download_url' not in release_asset:
                continue
            xpi_url = release_asset['browser_download_url']
            release.releaseDate = release_asset['updated_at']
            release.xpiDownloadUrl = {
                'github': xpi_url,
                'ghProxy': 'https://ghproxy.com/?q=' + urllib.parse.quote(xpi_url),
                'kgithub': xpi_url.replace('github.com', 'kkgithub.com'),
            }
            xpi_filename = f'{plugin.owner}#{plugin.repository}+{release.tagName}@{release_asset["id"]}.xpi'
            details = {}
            try:
                xpi_filepath = download_xpi(xpi_url=xpi_url,
                                            download_dir=kwargs.get('runtime_xpi_directory'),
                                            unique_name=xpi_filename,
                                            force_download=False,
                                            cache_dir=kwargs.get('cache_directory'))
                details = addon_details(xpi_filepath, zotero_versions=[release.zotero_check_version])
            except:
                try:
                    xpi_filepath = download_xpi(xpi_url=xpi_url,
                                                download_dir=kwargs.get('runtime_xpi_directory'),
                                                unique_name=xpi_filename,
                                                force_download=True)
                    details = addon_details(xpi_filepath, zotero_versions=[release.zotero_check_version])
                except Exception as e:
                    report_issue(kwargs.get('github_repository'),
                                 title=f'Parse xpi detail failed',
                                 body=f'url:{xpi_url}\n'
                                      f'repo:{plugin.repo}\n'
                                      f'reason:{e}',
                                 github_token=kwargs.get('github_token'))
                    print(f'fetch addon detail of {plugin.repo} with {xpi_url} failed: {e}')

            if details:
                if detail_id := details.get('id'):
                    release.id = detail_id
                if detail_name := details.get('name'):
                    release.name = detail_name
                if detail_version := details.get('version'):
                    release.xpiVersion = detail_version
                if detail_desc := details.get('description'):
                    release.description = detail_desc
            if release.zotero_check_version not in details.get('zotero_versions', []):
                invalid_releases.append(release)

        except Exception as e:
            print(f'handle {plugin.repo} request {release_url} failed: {e}')

        for invalid_release in invalid_releases:
            print(plugin.repo, 'invalid', invalid_release.zotero_check_version)
            report_issue(kwargs.get('github_repository'),
                         title=f'Invalid xpi with zotero version {invalid_release.zotero_check_version}',
                         body=f'xpi:{plugin.repo}@{invalid_release.tagName}\n'
                              f'expect zotero version:{invalid_release.zotero_check_version}\n',
                         github_token=kwargs.get('github_token'))
            plugin.releases.remove(invalid_release)
    return plugin


def fallback(addon_infos, previous_info_url, **kwargs):
    try:
        repos_resp = requests.get(previous_info_url, headers=github_api_headers(github_token=kwargs.get('github_token')))
        repos_info = json.loads(repos_resp.content)
        addon_infos = fallback_if_need(addon_infos, repos_info)
    except Exception as e:
        print(f'request previous addon_info.json to merge failed: {e}')
    return addon_infos


def parse_addon_infos(input_dir, output_filepath, **kwargs):
    plugins = []
    for addon_json_filename in os.listdir(input_dir):
        if not addon_json_filename.endswith('.json'):
            continue
        addon_json_filepath = os.path.join(input_dir, addon_json_filename)
        with open(addon_json_filepath, 'r') as file:
            try:
                plugins.append(AddonInfo(**json.load(file)))
            except Exception as e:
                print(f'parse initial addon info from {addon_json_filepath} failed: {e}')

    addon_infos = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(parse,
                                   plugin,
                                   github_token=kwargs.get('github_token'),
                                   cache_directory=kwargs.get('cache_directory'),
                                   runtime_xpi_directory=kwargs.get('runtime_xpi_directory'),
                                   github_repository=kwargs.get('github_repository'))
                   for plugin in plugins]

        for future in concurrent.futures.as_completed(futures):
            if addon_info := future.result():
                addon_infos.append(addon_info)

    addon_infos = [info.__dict__ for info in addon_infos]
    for previous_info_url in kwargs.get('previous_info_urls', []):
        addon_infos = fallback(addon_infos, previous_info_url, github_token=kwargs.get('github_token'))

    addon_infos.sort(key=lambda item: item.get('stars') if item.get('stars') else 0, reverse=True)

    dir = os.path.dirname(output_filepath)
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    with open(output_filepath, "w") as json_file:
        json.dump(addon_infos, json_file, ensure_ascii=False)

    return addon_infos


def upload_json_to_release(github_repository, release_id, upload_file_name, upload_file, **kwargs):
    headers = github_api_headers(github_token=kwargs.get('github_token'))
    headers["Content-Type"] = "application/octet-stream"
    upload_url = f'https://uploads.github.com/repos/{github_repository}/releases/{release_id}/assets?name={upload_file_name}'
    try:
        with open(upload_file, "rb") as file:
            upload_resp = requests.post(upload_url, data=file, headers=headers)
            if upload_resp.status_code != 201:
                print(f'upload release assets code: {upload_resp.status_code}')
            else:
                print('upload release assets succeed')
    except Exception as e:
        print(f'upload release assets failed: {e}')


def create_release(github_repository, **kwargs):
    create_release_url = f'https://api.github.com/repos/{github_repository}/releases'
    cur_time = int(time.time())
    param = {
        'tag_name': f'{cur_time}',
        'target_commitish': 'master',
        'name': f'{cur_time}',
        'body': f'![](https://img.shields.io/github/downloads/{github_repository}/{cur_time}/total?label=downloads)\npublish addon_infos.json',
        'draft': False,
        'prerelease': False,
        'generate_release_notes': False,
    }
    try:
        create_resp = requests.post(create_release_url, json=param, headers=github_api_headers(github_token=kwargs.get('github_token')))
        if create_resp.status_code == 201:
            create_release_info = json.loads(create_resp.content)
            release_id = create_release_info['id']
            return release_id
        else:
            print(f'create release code: {create_resp.status_code}')
    except Exception as e:
        print(f'create release failed: {e}')


def folder_filename_hash(dir):
    filenames = sorted(os.listdir(dir))
    folder_hash = hashlib.new('sha256')
    for filename in filenames:
        hash_obj = hashlib.new('sha256')
        hash_obj.update(filename.encode('utf-8'))
        folder_hash.update(hash_obj.hexdigest().encode('utf-8'))
    return folder_hash.hexdigest()


def update_cache(cache_directory, runtime_xpi_directory, cache_hash_filename):
    if not cache_directory or not runtime_xpi_directory or cache_directory == runtime_xpi_directory:
        return
    try:
        shutil.rmtree(cache_directory)
        shutil.move(runtime_xpi_directory, cache_directory)
        folder_hash = folder_filename_hash(cache_directory)
        with open(os.path.join(cache_directory, cache_hash_filename), 'w') as file:
            file.write(folder_hash)
        print(folder_hash)
    except Exception as e:
        print(f'update cache failed: {e}')


def delete_cache(github_repository, github_token, remain_count=2):
    headers = github_api_headers(github_token=github_token)
    get_caches_url = f'https://api.github.com/repos/{github_repository}/actions/caches?per_page=100&sort=last_accessed_at&direction=desc'
    try:
        caches_resp = requests.get(get_caches_url, headers=headers)
        caches = json.loads(caches_resp.content)
        if caches.get('total_count', 0) < remain_count:
            return
        delete_cache_url = f'https://api.github.com/repos/{github_repository}/actions/caches/'
        for cache in caches.get('actions_caches', [])[remain_count:]:
            cache_key = cache.get('key')
            if cache_id := cache.get('id'):
                try:
                    delete_cache_resp = requests.delete(f'{delete_cache_url}{cache_id}', headers=headers)
                    if delete_cache_resp.status_code == 204:
                        print(f'delete {cache_key} succeed')
                    else:
                        print(f'delete {cache_key} failed: {delete_cache_resp.text}')
                except Exception as e:
                    print(f'delete cache for {cache_key} failed: {e}')
    except Exception as e:
        print(f'get caches failed: {e}')


def rate_limit(github_token):
    try:
        resp = requests.get('https://api.github.com/rate_limit', headers=github_api_headers(github_token=github_token))
        rate = json.loads(resp.content)
        print(f'token rate {rate.get("rate")}')
    except Exception as e:
        print(f'get rate limit failed: {e}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='params')
    parser.add_argument('--github_repository', nargs='?', type=str, required=True, help='github repository')
    parser.add_argument('--github_token', nargs='?', type=str, help='github token')
    parser.add_argument('-i', '--input', nargs='?', type=str, default="addons", help='input addon dir')
    parser.add_argument('-o', '--output', nargs='?', type=str, default="addon_infos.json", help='output addon filepath')

    parser.add_argument('--cache_directory', nargs='?', default="caches", type=str, help='folder for caches')
    parser.add_argument('--cache_lockfile', nargs='?', default="caches_lockfile", type=str, help='hashfile for caches')
    parser.add_argument('--runtime_xpi_directory', nargs='?', default="xpis", type=str, help='folder for download xpi')
    parser.add_argument('--previous_info_urls', nargs='+', default=[], help='previous published info json to fallback')

    args = parser.parse_args()

    if not args.github_repository:
        raise 'Need specific github repository'

    if args.github_token:
        rate_limit(args.github_token)

    try:
        if not os.path.isdir(args.cache_directory):
            os.makedirs(args.cache_directory, exist_ok=True)
        if not os.path.isdir(args.runtime_xpi_directory):
            os.makedirs(args.runtime_xpi_directory, exist_ok=True)
    except Exception as e:
        print(f'create cache_directory failed: {e}')

    parse_addon_infos(args.input,
                      args.output,
                      github_repository=args.github_repository,
                      github_token=args.github_token,
                      cache_directory=args.cache_directory,
                      runtime_xpi_directory=args.runtime_xpi_directory,
                      previous_info_urls=args.previous_info_urls)

    if release_id := create_release(args.github_repository, github_token=args.github_token):
        upload_json_to_release(args.github_repository,
                               release_id,
                               upload_file_name='addon_infos.json',
                               upload_file=args.output,
                               github_token=args.github_token)

    update_cache(args.cache_directory, args.runtime_xpi_directory, args.cache_lockfile)

    if args.github_token:
        delete_cache(args.github_repository, args.github_token, remain_count=1)
