import os
import glob
import json
import zerver.lib.cache_manager as cache_manager

from typing import Any, List, Dict
from zerver.lib.test_classes import ZulipTestCase

test_fixtures_dir = cache_manager.normalize_path('zerver/fixtures/')
test_file_path = os.path.join(test_fixtures_dir, 'cache_manager_test_file.txt')

# create test file if not created already
if not os.path.exists(test_file_path):
    with open(test_file_path, 'w') as test_file:
        test_file.write('Initial Content')  # nocoverage

# change default's
cache_manager.cache_file_path = os.path.join(test_fixtures_dir, 'cache_version.json')
cache_manager.CACHE_FILES = {'zerver/fixtures/cache_manager_test_file.txt': os.path.getmtime(test_file_path)}
cache_manager.DATA['cache_files'] = cache_manager.CACHE_FILES

class CacheManagerTests(ZulipTestCase):
    current_data = cache_manager.CACHE_FILES

    def test_check_version_increments(self) -> None:
        with open(test_file_path, 'r') as test_file:
            original_contents = test_file.read()

        with open(test_file_path, 'w') as test_file:
            current_version = cache_manager.CACHE_VERSION
            test_file.write('change file')
            cache_manager.check()
            self.assertEqual(cache_manager.CACHE_VERSION, current_version + 1)

            test_file.truncate()
            test_file.write(original_contents)

    def test_update_version(self) -> None:
        current_version = cache_manager.CACHE_VERSION
        cache_manager.update_version()

        new_version = current_version + 1
        version_file = self.read_version_file()

        self.assertEqual(version_file['cache_version'], new_version)
        self.assertEqual(cache_manager.CACHE_VERSION, new_version)

    def test_get_cache_files_array(self) -> None:
        default_file = 'zerver/fixtures/cache_manager_test_file.txt'
        output = cache_manager.get_cache_files_array()
        self.check_file_included(output, default_file)

        # check if regex works as expected
        self.add_file('test_file')
        output = cache_manager.get_cache_files_array()

        result = self.check_file_included(output, default_file)
        self.assertTrue(result)
        result = self.check_file_included(output, 'test_file')
        self.assertTrue(result)
        result = self.check_file_included(output, 'UnkownFile')
        self.assertEqual(result, False)
        self.reset_files()

    def test_include(self) -> None:
        should_include = {}  # type: Dict[str, str]
        should_include = self.generate_files_dict(glob.glob(cache_manager.current_dir + '/cache_*.py'))
        files_included = cache_manager.include(['zerver/lib/cache_*.py'])
        self.assertEqual(should_include, files_included)

        files_included = cache_manager.include(['zerver/lib/none-exisiting.file'])
        self.assertEqual(files_included, {})

    def test_check_service_worker_view(self) -> None:
        result = self.client_get('/zulip-sw.js')
        self.assertEqual(result.status_code, 200)

    def read_version_file(self) -> Dict[str, Any]:
        version_file = os.path.join(test_fixtures_dir, 'cache_version.json')
        with open(version_file, 'r') as cache_version_file:
            data = json.load(cache_version_file)
        return data

    def add_file(self, file: str) -> None:
        cache_manager.CACHE_FILES[file] = ''
        cache_manager.DATA['cache_files'] = cache_manager.CACHE_FILES

    def check_file_included(self, output: str, file_name: str) -> bool:
        if output.find(file_name) is not -1:
            return True
        return False

    def generate_files_dict(self, files: List[str]) -> Dict[str, str]:
        generated_files = {}  # type: Dict[str, str]
        zulip_dir = os.path.abspath(cache_manager.current_dir + '/../../')
        for file_name in files:
            file_name = file_name.replace(zulip_dir, '')
            generated_files[file_name] = ''
        return generated_files

    def reset_files(self) -> None:
        cache_manager.CACHE_FILES = self.current_data
        cache_manager.DATA['cache_files'] = self.current_data
