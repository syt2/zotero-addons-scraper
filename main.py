import json
import time

import requests
import argparse


def parse(addon_id, addon_fullname, **kwargs):
    result = {
        'id': addon_id,
        'homepage': f'https://github.com/{addon_fullname}'
    }
    api_url = f'https://api.github.com/repos/{addon_fullname}'
    headers = {}
    if github_token := kwargs.get('github_token'):
        headers['Authorization'] = f'token {github_token}'
    try:
        repos_resp = requests.get(api_url, headers=headers)
        repos_info = json.loads(repos_resp.content)
        description = repos_info['description']
        start_count = repos_info['watchers']
        result['description'] = description
        result['start_count'] = start_count
        try:
            release_resp = requests.get(f'{api_url}/releases/latest', headers=headers)
            release_info = json.loads(release_resp.content)
            release_info['assets']
            for asset in release_info['assets']:
                if asset['name'].endswith('.xpi'):
                    download_link = asset['browser_download_url']
                    name = asset['name'][:-4]
                    result['name'] = name
                    result['download_link'] = download_link
                    break

        except Exception as e:
            print(f'request {api_url}/releases/latest failed: {e}')
    except Exception as e:
        print(f'request {api_url} failed: {e}')

    if 'name' in result:
        return result


# todo: support multiprocess
def parse_addon_infos(input_filepath, output_filepath, **kwargs):
    with open(input_filepath, 'r', encoding='utf-8') as file:
        lines = [line.strip().split(',') for line in file.readlines()]
    addon_infos = []
    for addon_id, addon_fullname in lines:
        if addon_info := parse(addon_id.strip(), addon_fullname.strip(), github_token=kwargs.get('github_token')):
            addon_infos.append(addon_info)

    with open(output_filepath, "w") as json_file:
        json.dump(addon_infos, json_file)

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
        'body': 'body',
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='params')
    parser.add_argument('--github_repository', nargs='?', type=str, required=True, help='github repository')
    parser.add_argument('--github_token', nargs='?', type=str, help='github token')
    parser.add_argument('-i', '--input', nargs='?', type=str, default="addons", help='input addon files')
    parser.add_argument('-o', '--output', nargs='?', type=str, default="addon_infos.json", help='output addon infos')

    args = parser.parse_args()
    if not args.github_repository:
        raise 'Need specific github repository'
    if not args.input:
        raise 'need specific input addon file'
    parse_addon_infos(args.input, args.output, github_token=args.github_token)
    if release_id := create_release(args.github_repository, github_token=args.github_token):
        upload_json_to_release(args.github_repository,
                               release_id,
                               upload_file_name='addon_infos.json',
                               upload_file=args.output,
                               github_token=args.github_token)
