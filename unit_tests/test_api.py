import json
import subprocess
import time
import unittest
from pathlib import Path
import pandas as pd
import requests

from src.results_processing.results_processor import ResultsProcessor


class TestFairgameAPI(unittest.TestCase):
    """
    Integration tests for the Fairgame API endpoint.

    These tests start a local Flask subprocess (from `api.py`) and send requests
    to verify the behavior of creating and running Fairgame games.
    """

    @classmethod
    def setUpClass(cls):
        """
        Start the Flask app as a subprocess before any tests run.
        Wait a few seconds to ensure the server is ready to accept requests.
        """
        cls.process = subprocess.Popen(["python", "api.py"])
        time.sleep(3)  # Allow some time for the server to start up

        # Define test resource directories for clarity and maintainability
        base_dir = Path(__file__).resolve().parent
        cls.config_dir = base_dir / 'config'
        cls.template_dir = base_dir / 'game_templates'

        # Define config/template paths and the API URL
        cls.config_filepath = cls.config_dir / 'prisoner_dilemma_no_template.json'
        cls.template_filepath = cls.template_dir / 'prisoner_dilemma_en.txt'
        cls.api_url = "http://127.0.0.1:5003/create_and_run_games"

    @classmethod
    def tearDownClass(cls):
        """
        Terminate the Flask app subprocess after all tests complete.
        """
        cls.process.terminate()

    def _load_json_config(self, filepath: Path) -> dict:
        """
        Load and return JSON content from the specified config file.

        Args:
            filepath (Path): The path to the JSON configuration file.

        Returns:
            dict: The loaded JSON content as a Python dictionary.
        """
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)

    def _load_text_template(self, filepath: Path) -> str:
        """
        Load and return the text content of a template file.

        Args:
            filepath (Path): The path to the text template file.

        Returns:
            str: The complete text content of the file.
        """
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()

    def _create_and_run_games(self, config: dict) -> requests.Response:
        """
        Send a POST request to the Fairgame API to create and run games.

        Args:
            config (dict): Game configuration to be sent in the request body.

        Returns:
            requests.Response: The HTTP response from the API.
        """
        headers = {"Content-Type": "application/json"}
        return requests.post(
            self.api_url,
            data=json.dumps(config),
            headers=headers
        )

    def test_malformed_template(self):
        """
        Test that providing a malformed template returns an error (status code 500).

        This test loads a valid config but injects a potentially malformed
        template. The API should respond with an HTTP 500 (internal server error).
        """
        config = self._load_json_config(self.config_filepath)
        template_content = self._load_text_template(self.template_filepath)

        # Inject the template data (which is malformed for this test)
        config['promptTemplate'] = {'en': template_content}
        config['templateFilename'] = "prisoner_dilemma"

        response = self._create_and_run_games(config)
        self.assertEqual(
            response.status_code,
            500,
            msg="Expected 500 status code for malformed template."
        )

    def test_create_and_run_games(self):
        """
        Test the successful creation and execution of games.

        This test sends a well-formed configuration to the API, then processes
        the results into a DataFrame for further validation.
        """
        config = self._load_json_config(self.config_filepath)
        template_content = self._load_text_template(self.template_filepath)

        # Inject the correct, well-formed template
        config['promptTemplate'] = {"en": template_content}

        response = self._create_and_run_games(config)
        self.assertEqual(
            response.status_code,
            200,
            msg="Expected 200 status code for a valid configuration."
        )

        results_df = pd.DataFrame.from_dict(response.json(), orient="index")
        
        # Example assertion (update as appropriate for your data)
        self.assertGreater(
            len(results_df),
            0,
            msg="Results DataFrame should have at least one row."
        )


if __name__ == '__main__':
    unittest.main()
