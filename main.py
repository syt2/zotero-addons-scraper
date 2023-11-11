import concurrent.futures
import json
import os
import time
import urllib.parse
import requests
import argparse
import shutil
from addon_keys import *
from fallback_infos import fallback_if_need
from moz_addons import addon_details


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
        print(f'download {unique_name} from {xpi_url}')  # TODO: comment
        with open(download_filepath, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        return download_filepath
    except Exception as e:
        print(f'download {unique_name} from {xpi_url} failed: {e}')


# 输出格式参考 [zotero-chinese/zotero-plugins](https://github.com/zotero-chinese/zotero-plugins)
def parse(plugin, **kwargs):
    if repo not in plugin or len(plugin[repo].split('/')) != 2 or releases not in plugin or len(plugin[releases]) <= 0:
        return
    if name not in plugin:
        plugin[name] = plugin[repo].split('/')[-1]

    headers = {}
    if github_token := kwargs.get('github_token'):
        headers['Authorization'] = f'token {github_token}'

    # fetch author info
    author_url = f"https://api.github.com/users/{plugin[repo].split('/')[0]}"
    try:
        author_resp = requests.get(author_url, headers=headers)
        author_resp_info = json.loads(author_resp.content)
        plugin_author = {}
        if 'name' in author_resp_info:
            plugin_author[name] = author_resp_info['name']
        if 'html_url' in author_resp_info:
            plugin_author[url] = author_resp_info['html_url']
        if 'avatar_url' in author_resp_info:
            plugin_author[avatar] = author_resp_info['avatar_url']
        if plugin_author.keys():
            plugin[author] = plugin_author
    except Exception as e:
        print(f'request {author_url} failed: {e}')

    # fetch repo info
    repo_url = f'https://api.github.com/repos/{plugin[repo]}'
    try:
        repos_resp = requests.get(repo_url, headers=headers)
        repos_info = json.loads(repos_resp.content)
        if repos_info['description'] and description not in plugin:
            plugin[description] = repos_info['description']
        if repos_info['stargazers_count'] is not None:
            plugin[star] = repos_info['stargazers_count']
    except Exception as e:
        print(f'request {repo_url} failed: {e}')

    # fetch release info
    release_infos = []
    for release in plugin[releases]:
        if tagName not in release:
            continue
        release_url = f'https://api.github.com/repos/{plugin[repo]}/releases'
        if release[tagName] == 'latest':
            release_url += '/latest'
        elif release[tagName] != 'pre':
            release_url += f'/tags/{release[tagName]}'

        try:
            release_resp = requests.get(release_url, headers=headers)
            release_info = json.loads(release_resp.content)

            if release[tagName] == 'pre':
                release_info = [info for info in release_info if info['prerelease']]
                if release_info:
                    release_info = release_info[0]
                else:
                    continue
            if 'tag_name' in release_info:
                release[currentVersion] = release_info['tag_name']

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
            if 'id' in release_asset:
                release[assetId] = release_asset['id']
            if 'download_count' in release_asset:
                release[downloadCount] = release_asset['download_count']
            release[releaseData] = release_asset['updated_at']
            release[xpiDownloadUrl] = {
                'github': xpi_url,
                'ghProxy': 'https://ghproxy.com/?q=' + urllib.parse.quote(xpi_url),
                'kgithub': xpi_url.replace('github.com', 'kkgithub.com'),
            }

            xpi_filename = f'{plugin[repo].replace("/", "#")}+' \
                           f'{release.get(currentVersion, "0")}@' \
                           f'{release.get(assetId, "0")}.xpi'
            details = {}
            try:
                xpi_filepath = download_xpi(xpi_url=xpi_url,
                                            download_dir=kwargs.get('runtime_xpi_directory'),
                                            unique_name=xpi_filename,
                                            force_download=False,
                                            cache_dir=kwargs.get('cache_directory'))
                details = addon_details(xpi_filepath)
            except:
                try:
                    xpi_filepath = download_xpi(xpi_url=xpi_url,
                                                download_dir=kwargs.get('runtime_xpi_directory'),
                                                unique_name=xpi_filename,
                                                force_download=True)
                    details = addon_details(xpi_filepath)
                except Exception as e:
                    print(f'fetch addon detail of {plugin[repo]} failed: {e}')
            if details:
                xpi_info = {}
                if "id" in details:
                    xpi_info[id] = details["id"]
                if "name" in details:
                    xpi_info[name] = details["name"]
                if "version" in details:
                    xpi_info[currentVersion] = details["version"]
                if xpi_info:
                    release[xpiInfo] = xpi_info
            release_infos.append(release)

        except Exception as e:
            print(f'handle {plugin[repo]} request {release_url} failed: {e}')

    plugin[releases] = release_infos

    return plugin


def fallback(addon_infos, previous_info_url, **kwargs):
    headers = {}
    if github_token := kwargs.get('github_token'):
        headers['Authorization'] = f'token {github_token}'
    try:
        repos_resp = requests.get(previous_info_url, headers=headers)
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
            plugins.append(json.load(file))

    addon_infos = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(parse,
                                   plugin,
                                   github_token=kwargs.get('github_token'),
                                   cache_directory=kwargs.get('cache_directory'),
                                   runtime_xpi_directory=kwargs.get('runtime_xpi_directory'))
                   for plugin in plugins]

        for future in concurrent.futures.as_completed(futures):
            if addon_info := future.result():
                addon_infos.append(addon_info)

    for previous_info_url in kwargs.get('previous_info_urls', []):
        addon_infos = fallback(addon_infos, previous_info_url, github_token=kwargs.get('github_token'))

    addon_infos.sort(key=lambda item: item[star] if star in item else 0, reverse=True)

    dir = os.path.dirname(output_filepath)
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    with open(output_filepath, "w") as json_file:
        json.dump(addon_infos, json_file, ensure_ascii=False, indent='  ')

    return addon_infos


def upload_json_to_release(github_repository, release_id, upload_file_name, upload_file, **kwargs):
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        "Content-Type": "application/octet-stream",
    }
    if github_token := kwargs.get('github_token'):
        headers['Authorization'] = f'token {github_token}'
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
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if github_token := kwargs.get('github_token'):
        headers['Authorization'] = f'token {github_token}'
    create_release_url = f'https://api.github.com/repos/{github_repository}/releases'
    cur_time = int(time.time())
    param = {
        'tag_name': f'{cur_time}',
        'target_commitish': 'master',
        'name': f'{cur_time}',
        'body': 'publish addon_infos.json',
        'draft': False,
        'prerelease': False,
        'generate_release_notes': False,
    }
    try:
        create_resp = requests.post(create_release_url, json=param, headers=headers)
        if create_resp.status_code == 201:
            create_release_info = json.loads(create_resp.content)
            release_id = create_release_info['id']
            return release_id
        else:
            print(f'create release code: {create_resp.status_code}')
    except Exception as e:
        print(f'create release failed: {e}')


def update_cache(cache_directory, runtime_xpi_directory):
    if not cache_directory or not runtime_xpi_directory or cache_directory == runtime_xpi_directory:
        return
    try:
        shutil.rmtree(cache_directory)
        shutil.move(runtime_xpi_directory, cache_directory)
    except Exception as e:
        print(f'update cache failed: {e}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='params')
    parser.add_argument('--github_repository', nargs='?', type=str, required=True, help='github repository')
    parser.add_argument('--github_token', nargs='?', type=str, help='github token')
    parser.add_argument('-i', '--input', nargs='?', type=str, default="addons", help='input addon dir')
    parser.add_argument('-o', '--output', nargs='?', type=str, default="addon_infos.json", help='output addon filepath')

    parser.add_argument('--cache_directory', nargs='?', default="caches", type=str, help='folder for caches')
    parser.add_argument('--runtime_xpi_directory', nargs='?', default="xpis", type=str, help='folder for download xpi')
    parser.add_argument('--previous_info_urls', nargs='+', default=[], help='previous published info json to fallback')

    args = parser.parse_args()

    if not args.github_repository:
        raise 'Need specific github repository'

    try:
        if not os.path.isdir(args.cache_directory):
            os.makedirs(args.cache_directory, exist_ok=True)
        if not os.path.isdir(args.runtime_xpi_directory):
            os.makedirs(args.runtime_xpi_directory, exist_ok=True)
    except Exception as e:
        print(f'create cache_directory failed: {e}')

    parse_addon_infos(args.input,
                      args.output,
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

    update_cache(args.cache_directory, args.runtime_xpi_directory)
