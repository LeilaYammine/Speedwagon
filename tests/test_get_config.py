import configparser
import os

import speedwagon.config
from speedwagon import config
import pytest


class MockConfig(config.AbsConfig):
        def __init__(self):

            super().__init__()
            self.user_data_dir = ""
            self.app_data_dir = ""

        def get_user_data_directory(self) -> str:
            return self.user_data_dir

        def get_app_data_directory(self) -> str:
            return self.app_data_dir


@pytest.fixture(scope="module")
def dummy_config(tmpdir_factory):
    root_dir = tmpdir_factory.mktemp("settings")
    dummy = MockConfig()
    dummy.user_data_dir = os.path.join(root_dir, "user_data_directory")
    os.mkdir(dummy.user_data_dir)

    dummy.app_data_dir = os.path.join(root_dir, "app_data_directory")
    os.mkdir(dummy.app_data_dir)

    return dummy


def test_get_config(dummy_config):
    config = speedwagon.config.get_platform_settings(dummy_config)
    assert config is not None
    assert isinstance(config, MockConfig)


def test_get_config__getitem__(dummy_config):
    assert os.path.exists(dummy_config['user_data_directory'])
    assert os.path.exists(dummy_config['app_data_directory'])


def test_get_config__contains__(dummy_config):
    assert ("user_data_directory" in dummy_config) is True
    assert ("foo" in dummy_config) is False


def test_get_config__iter__(dummy_config):
    for i in dummy_config:
        print(i)


def test_read_settings(tmpdir):
    config_file = tmpdir.mkdir("settings").join("config.ini")

    global_settings = {
        "tessdata": "~/mytesseractdata"
    }

    with open(config_file, "w") as f:
        cfg_parser = configparser.ConfigParser()
        cfg_parser["GLOBAL"] = global_settings
        cfg_parser.write(f)

    with config.ConfigManager(config_file) as cfg:
        assert cfg.global_settings['tessdata'] == "~/mytesseractdata"