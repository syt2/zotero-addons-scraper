import os
import shutil
import hashlib


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
