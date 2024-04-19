import json
import time
import requests
from datetime import datetime, timedelta, UTC


def github_api_headers(**kwargs):
    result = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if github_token := kwargs.get('github_token'):
        result['Authorization'] = f'token {github_token}'
    return result


def report_issue(github_repository: str, title: str, body: str, **kwargs):
    if not github_repository:
        print('report issue repository not found')
        return
    try:
        if issue_check_id := kwargs.get('id'):
            body = f'{body}\n----{issue_check_id}'
            try:
                response = requests.get(f'https://api.github.com/repos/{github_repository}/issues',
                                        headers=github_api_headers(github_token=kwargs.get('github_token')),
                                        params={
                                            'state': 'open',
                                            'since': (datetime.now(UTC) - timedelta(days=10)).strftime('%Y-%m-%dT%H:%M:%S') + 'Z',
                                            'per_page': 100,
                                        })
                exist_issues = response.json()
                for issue in exist_issues:
                    if issue.get('body').endswith(f'----{issue_check_id}'):
                        return
            except Exception as e:
                print(f'fetch from exist issues failed: {e}')

        response = requests.post(f'https://api.github.com/repos/{github_repository}/issues',
                                 headers=github_api_headers(github_token=kwargs.get('github_token')),
                                 json={
                                     'title': title,
                                     'body': body
                                 })

        if response.status_code == 201:
            print('Issue created successfully.')
            print('Issue URL:', response.json()['html_url'])
        else:
            print('Failed to create issue.')
            print('Response:', response.content)
    except Exception as e:
        print(f'report issue failed: {e}')


def upload_json_to_release(github_repository, release_id, upload_file_name, upload_file, **kwargs):
    headers = github_api_headers(github_token=kwargs.get('github_token'))
    headers["Content-Type"] = "application/octet-stream"
    upload_url = (f'https://uploads.github.com/repos/{github_repository}'
                  f'/releases/{release_id}/assets?name={upload_file_name}')
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
        'target_commitish': 'publish',
        'name': f'{cur_time}',
        'body': f'![](https://img.shields.io/github/downloads/{github_repository}/{cur_time}/total?label=downloads)\n'
                f'publish addon_infos.json',
        'draft': False,
        'prerelease': False,
        'generate_release_notes': False,
    }
    try:
        create_resp = requests.post(create_release_url, json=param,
                                    headers=github_api_headers(github_token=kwargs.get('github_token')))
        if create_resp.status_code == 201:
            create_release_info = json.loads(create_resp.content)
            release_id = create_release_info['id']
            return release_id
        else:
            print(f'create release code: {create_resp.status_code}')
    except Exception as e:
        print(f'create release failed: {e}')


def delete_cache(github_repository, github_token, remain_count=2):
    headers = github_api_headers(github_token=github_token)
    get_caches_url = (f'https://api.github.com/repos/{github_repository}'
                      f'/actions/caches?per_page=100&sort=last_accessed_at&direction=desc')
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


def delete_release(github_repository, github_token, remain_count=2):
    headers = github_api_headers(github_token=github_token)
    get_release_url = (f'https://api.github.com/repos/{github_repository}'
                       f'/releases?per_page=100&page=1')
    try:
        releases_resp = requests.get(get_release_url, headers=headers)
        releases = json.loads(releases_resp.content)
        if len(releases) < remain_count:
            return
        releases.sort(key=lambda release: release['tag_name'], reverse=True)
        delete_release_url = f'https://api.github.com/repos/{github_repository}/releases/'
        for release in releases[remain_count:]:
            release_tag = release.get('tag_name')
            if release_id := release.get('id'):
                try:
                    delete_release_resp = requests.delete(f'{delete_release_url}{release_id}', headers=headers)
                    if delete_release_resp.status_code == 204:
                        print(f'delete release {release_tag} succeed')
                    else:
                        print(f'delete release {release_tag} failed: {delete_release_resp.text}')
                except Exception as e:
                    print(f'delete release for {release_tag} failed: {e}')
    except Exception as e:
        print(f'get releases failed: {e}')


def delete_tag(github_repository, github_token, remain_count=2):
    headers = github_api_headers(github_token=github_token)
    get_tags_url = (f'https://api.github.com/repos/{github_repository}'
                    f'/git/refs/tags')
    try:
        tags_response = requests.get(get_tags_url, headers=headers)
        tags = json.loads(tags_response.content)
        if len(tags) < remain_count:
            return
        tags.sort(key=lambda tag: tag['ref'], reverse=True)
        delete_tag_url = f'https://api.github.com/repos/{github_repository}/git/refs/tags/'
        for tag in tags[remain_count:]:
            if ref := tag.get('ref').replace('refs/tags/', ''):
                if len(ref) < 10:
                    continue
                try:  # automatically tag name is timestamp
                    int(ref)
                except ValueError:
                    continue
                try:
                    delete_tag_resp = requests.delete(f'{delete_tag_url}{ref}', headers=headers)
                    if delete_tag_resp.status_code == 204:
                        print(f'delete tag {ref} succeed')
                    else:
                        print(f'delete tag {ref} failed: {delete_tag_resp.text}')
                except Exception as e:
                    print(f'delete tag for {ref} failed: {e}')
    except Exception as e:
        print(f'get tags failed: {e}')


def rate_limit(github_token):
    try:
        resp = requests.get('https://api.github.com/rate_limit', headers=github_api_headers(github_token=github_token))
        rate = json.loads(resp.content)
        print(f'token rate {rate.get("rate")}')
    except Exception as e:
        print(f'get rate limit failed: {e}')
