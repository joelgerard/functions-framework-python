import os
import pathlib
import re
import subprocess
import sys
import time

import docker
import pytest
import requests

EXAMPLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.skipif(
    sys.platform != "linux", reason="docker only works on linux in GH actions"
)
class TestSamples:
    def stop_all_containers(self, docker_client):
        containers = docker_client.containers.list()
        for container in containers:
            container.stop()

    def setup_method(self, method):
        # Call this just in case a previous test has left something running.
        self.stop_all_containers(docker.from_env())

    def teardown_method(self, method):
        self.stop_all_containers(docker.from_env())

    @pytest.fixture
    def docker_client(self):
        return docker.from_env()

    @pytest.mark.slow_integration_test
    def test_cloud_run_http(self, docker_client):
        """
        Tests the docker file runs and the function called.
        :param docker_client: The docker process to run the Dockerfile.
        """
        TAG = "cloud_run_http"
        docker_client.images.build(path=str(EXAMPLES_DIR / "cloud_run_http"), tag={TAG})
        docker_client.containers.run(
            image=TAG, detach=True, ports={8080: 8080}, environment={"PORT": "8080"}
        )
        timeout = 10
        response_text = None
        while response_text is None and timeout > 0:
            try:
                response = requests.get("http://localhost:8080")
                if response.text != "":
                    response_text = response.text
            except:
                pass

            time.sleep(1)
            timeout -= 1

        assert response_text == "Hello world!"

    def get_doc_code(self, doc_file_path, doc_tag):
        """
        Returns the inline code from an MD file that has been marked with a specific tag.
        :param doc_file_path: The path to the MD file.
        :param doc_tag: The doc tag that labels the code to extract.
        :return: The extracted inline code.
        """
        with open(doc_file_path) as open_file:
            data = open_file.read()
        m = re.search(
            "start_doc:%s.*?```.*?\n(.*?)```" % doc_tag, data, re.MULTILINE | re.DOTALL
        )
        return m.group(1)

    def compare_doc_code_file(self, doc_file_path, doc_tag, example_file_path):
        """
        Compares whether the sample code that was committed is the same as the sample code
        pasted into the MD file.
        :param doc_file_path: The path to the MD file.
        :param doc_tag: The doc tag that labels the code to extract.
        :param example_file_path: The runnable example file.
        :return: True if they are the same, False otherwise.
        """
        doc_text = self.get_doc_code(doc_file_path, doc_tag)
        with open(example_file_path) as open_file:
            data = open_file.read()
        return doc_text == data

    @pytest.mark.slow_integration_test
    def test_cloud_run_http_inline_samples(self, docker_client):
        """
        Tests whether the code in examples/cloud_run_http/README.md works.
        :param docker_client: The docker process to run the Dockerfile.
        """
        http_example_dir = EXAMPLES_DIR / "cloud_run_http"
        doc_file_path = str(http_example_dir / "README.md")
        docker_file_path = http_example_dir / "Dockerfile"

        # Make sure the code we use in the MD file is the same code
        # that actually runs.
        assert self.compare_doc_code_file(
            doc_file_path, "http_docker_file", docker_file_path
        ), "Sample code in MD file doesn't match actual code"

        # Make sure the code written down in the MD file actually runs and returns
        # what we expect.
        docker_run_code = self.get_doc_code(doc_file_path, "http_docker_run")
        os.chdir(http_example_dir)
        os.system(docker_run_code)
        curl_code = self.get_doc_code(doc_file_path, "http_curl")
        timeout = 10
        success = False
        while success == False and timeout > 0:
            try:
                result = subprocess.check_output(curl_code, shell=True)
                if result == b"Hello world!":
                    success = True
            except:
                pass

            time.sleep(1)
            timeout -= 1

        assert success
