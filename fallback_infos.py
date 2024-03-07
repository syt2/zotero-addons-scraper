fallback_associated_unique_id = 'p_unique_associated_id##80502300-9DE6-4510-8768-EC42B0EF14E6'
fallback_associated_exclude_ids = 'p_exclude_associated_ids##073F5543-C70A-46AA-8529-E05168852D8F'

fallback_associated_map = {
    fallback_associated_unique_id: 'repo',
    fallback_associated_exclude_ids: ['id'],
    'repo': {
      'releases': {
          fallback_associated_unique_id: 'tagName',
          fallback_associated_exclude_ids: ['currentVersion'],
      }
    }
}


def fallback_if_need(current, previous, associate_map=None):
    if associate_map is None:
        associate_map = fallback_associated_map
    if previous and current and isinstance(previous, type(current)):
        if isinstance(current, dict):
            for key, value in previous.items():
                if key in associate_map.get(fallback_associated_exclude_ids, []):
                    continue
                if key in current and (isinstance(value, (list, dict))):
                    if current[key]:
                        fallback_if_need(current[key], value, associate_map.get(key, {}))
                    else:
                        print(f'fallback {key}')
                        current[key] = value
                elif key not in current:
                    print(f'fallback {key}')
                    current[key] = value

        elif isinstance(current, list) and (uid := associate_map.get(fallback_associated_unique_id)):
            for value in previous:
                if not isinstance(value, dict):
                    continue
                if cur := next((x for x in current if isinstance(x, dict) and x[uid] == value[uid]), None):
                    fallback_if_need(cur, value, associate_map.get(uid, {}))
    return current
