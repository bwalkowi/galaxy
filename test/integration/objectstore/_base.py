import json
import os
import random
import string
import subprocess

from galaxy_test.base.populators import DatasetPopulator
from galaxy_test.driver import integration_util

OBJECT_STORE_HOST = os.environ.get("GALAXY_INTEGRATION_OBJECT_STORE_HOST", "127.0.0.1")
OBJECT_STORE_PORT = int(os.environ.get("GALAXY_INTEGRATION_OBJECT_STORE_PORT", 9000))
OBJECT_STORE_ACCESS_KEY = os.environ.get("GALAXY_INTEGRATION_OBJECT_STORE_ACCESS_KEY", "minioadmin")
OBJECT_STORE_SECRET_KEY = os.environ.get("GALAXY_INTEGRATION_OBJECT_STORE_SECRET_KEY", "minioadmin")
OBJECT_STORE_CONFIG = string.Template(
    """
<object_store type="hierarchical" id="primary">
    <backends>
        <object_store id="swifty" type="generic_s3" weight="1" order="0">
            <auth access_key="${access_key}" secret_key="${secret_key}" />
            <bucket name="galaxy" use_reduced_redundancy="False" max_chunk_size="250"/>
            <connection host="${host}" port="${port}" is_secure="False" conn_path="" multipart="True"/>
            <cache path="${temp_directory}/object_store_cache" size="1000" cache_updated_data="${cache_updated_data}" />
            <extra_dir type="job_work" path="${temp_directory}/job_working_directory_swift"/>
            <extra_dir type="temp" path="${temp_directory}/tmp_swift"/>
        </object_store>
    </backends>
</object_store>
"""
)

ONEDATA_DEMO_SPACE_NAME = "demo-space"
ONEDATA_OBJECT_STORE_CONFIG = string.Template("""
<object_store type="onedata">
    <auth access_token="${access_token}" />
    <connection onezone_domain="${onezone_domain}" disable_tls_certificate_validation="True"/>
    <space name="${space_name}" ${optional_space_params} />
    <cache path="${temp_directory}/object_store_cache" size="1000" cache_updated_data="${cache_updated_data}" />
    <extra_dir type="job_work" path="${temp_directory}/job_working_directory_onedata"/>
    <extra_dir type="temp" path="${temp_directory}/tmp_onedata"/>
</object_store>
"""
)


class BaseObjectStoreIntegrationTestCase(integration_util.IntegrationTestCase, integration_util.ConfiguresObjectStores):
    dataset_populator: DatasetPopulator
    framework_tool_and_types = True

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)


def get_files(directory):
    for rel_directory, _, files in os.walk(directory):
        for file_ in files:
            yield os.path.join(rel_directory, file_)


def files_count(directory):
    return sum(1 for _ in get_files(directory))


@integration_util.skip_unless_docker()
class BaseSwiftObjectStoreIntegrationTestCase(BaseObjectStoreIntegrationTestCase):
    object_store_cache_path: str

    @classmethod
    def setUpClass(cls):
        cls.container_name = f"{cls.__name__}_container"
        start_minio(cls.container_name)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        docker_rm(cls.container_name)
        super().tearDownClass()

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        super().handle_galaxy_config_kwds(config)
        temp_directory = cls._test_driver.mkdtemp()
        cls.object_stores_parent = temp_directory
        cls.object_store_cache_path = f"{temp_directory}/object_store_cache"
        config_path = os.path.join(temp_directory, "object_store_conf.xml")
        config["object_store_store_by"] = "uuid"
        config["metadata_strategy"] = "extended"
        config["outputs_to_working_directory"] = True
        config["retry_metadata_internally"] = False
        with open(config_path, "w") as f:
            f.write(
                OBJECT_STORE_CONFIG.safe_substitute(
                    {
                        "temp_directory": temp_directory,
                        "host": OBJECT_STORE_HOST,
                        "port": OBJECT_STORE_PORT,
                        "access_key": OBJECT_STORE_ACCESS_KEY,
                        "secret_key": OBJECT_STORE_SECRET_KEY,
                        "cache_updated_data": cls.updateCacheData(),
                    }
                )
            )
        config["object_store_config_file"] = config_path

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)

    @classmethod
    def updateCacheData(cls):
        return True


@integration_util.skip_unless_docker()
class BaseOnedataObjectStoreIntegrationTestCase(BaseObjectStoreIntegrationTestCase):
    object_store_cache_path: str

    @classmethod
    def setUpClass(cls):
        cls.oz_container_name = f"{cls.__name__}_oz_container"
        cls.op_container_name = f"{cls.__name__}_op_container"

        start_onezone(cls.oz_container_name)

        oz_ip_address = get_onezone_ip_address(cls.oz_container_name)
        start_oneprovider(cls.op_container_name, oz_ip_address)
        await_oneprovider_demo_readiness(cls.op_container_name)

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        docker_rm(cls.op_container_name)
        docker_rm(cls.oz_container_name)

        super().tearDownClass()

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        super().handle_galaxy_config_kwds(config)
        temp_directory = cls._test_driver.mkdtemp()
        cls.object_stores_parent = temp_directory
        cls.object_store_cache_path = f"{temp_directory}/object_store_cache"
        config_path = os.path.join(temp_directory, "object_store_conf.xml")
        config["object_store_store_by"] = "uuid"
        config["metadata_strategy"] = "extended"
        config["outputs_to_working_directory"] = True
        config["retry_metadata_internally"] = False
        with open(config_path, "w") as f:
            f.write(ONEDATA_OBJECT_STORE_CONFIG.safe_substitute(
                {
                    "temp_directory": temp_directory,
                    "access_token": get_onedata_access_token(cls.oz_container_name),
                    "onezone_domain": get_onezone_ip_address(cls.oz_container_name),
                    "space_name": ONEDATA_DEMO_SPACE_NAME,
                    "optional_space_params": random.choice([
                        '',
                        'path=""',
                        'path="a/b/c/d"'
                    ]),
                    "cache_updated_data": cls.updateCacheData(),
                }
            ))

        config["object_store_config_file"] = config_path

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)

    @classmethod
    def updateCacheData(cls):
        return True


def start_minio(container_name):
    ports = [(OBJECT_STORE_PORT, 9000)]
    docker_run("minio/minio:latest", container_name, "server", "/data", ports=ports)


def start_onezone(oz_container_name):
    docker_run("onedata/onezone:21.02.5-dev", oz_container_name, "demo")


def get_onezone_ip_address(oz_container_name):
    cmd = [
        "docker",
        "inspect",
        '-f',
        '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
        oz_container_name,
    ]
    return subprocess.check_output(cmd).decode('utf-8').strip()


def start_oneprovider(op_container_name, oz_ip_address):
    docker_run("onedata/oneprovider:21.02.5-dev", op_container_name, "demo", oz_ip_address)


def await_oneprovider_demo_readiness(op_container_name):
    docker_exec(op_container_name, "await-demo", output=False)


def get_onedata_access_token(oz_container_name):
    return docker_exec(oz_container_name, "demo-access-token").decode('utf-8').strip()


def docker_run(image, name, *args, detach=True, remove=True, ports=None):
    cmd = ["docker", "run"]

    if ports:
        for (container_port, host_port) in ports:
            cmd.extend(["-p", f"{container_port}:{host_port}"])

    if detach:
        cmd.append("-d")

    cmd.extend(["--name", name])

    if remove:
        cmd.append("--rm")

    cmd.append(image)
    cmd.extend(args)

    subprocess.check_call(cmd)


def docker_exec(container_name, *args, output=True):
    cmd = ["docker", "exec", container_name]
    cmd.extend(args)

    if output:
        return subprocess.check_output(cmd)
    else:
        subprocess.check_call(cmd)


def docker_rm(container_name):
    subprocess.check_call(["docker", "rm", "-f", container_name])
