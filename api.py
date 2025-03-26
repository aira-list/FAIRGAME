import os
from datetime import datetime
from flask import Flask, jsonify, request

from src.fairgame_factory import FairGameFactory
from src.results_processing.results_processor import ResultsProcessor

class S3Uploader:
    """Handles the logic for uploading files to an S3-compatible storage."""

    def __init__(self) -> None:
        """
        Initializes the S3Uploader, pulling environment variables for
        endpoint, bucket name, and credentials.
        """
        self.endpoint = os.getenv('S3_ENDPOINT')
        self.bucket_name = os.getenv('BUCKET_NAME')
        self.key = os.getenv('S3_KEY')
        self.secret = os.getenv('S3_SECRET')

    def is_configured(self) -> bool:
        """
        Checks if S3-related environment variables are properly set.

        Returns:
            bool: True if all necessary environment variables are present,
            False otherwise.
        """
        return bool(self.endpoint and self.bucket_name and self.key and self.secret)

    def get_s3_credentials(self) -> dict:
        """
        Constructs and returns a dictionary of S3 credentials, usable
        as storage options in `pandas.DataFrame.to_csv()`.

        Returns:
            dict: Dictionary with S3 access credentials and endpoint url.
        """
        return {
            "key": self.key,
            "secret": self.secret,
            "client_kwargs": {
                "endpoint_url": self.endpoint
            }
        }

    def save(self, dataframe, filepath: str) -> None:
        """
        Attempts to upload the given dataframe as a CSV to S3, if configuration is valid.

        Args:
            dataframe (pandas.DataFrame): The dataframe to be saved.
            filepath (str): The desired path (including folder structure) within the S3 bucket.
        """
        if not self.is_configured():
            print("S3 environment variables not set or incomplete. Skipping upload.")
            return

        try:
            storage_options = self.get_s3_credentials()
            dataframe.to_csv(
                f"s3://{self.bucket_name}/{filepath}",
                index=False,
                sep=';',
                quotechar='"',
                quoting=1,
                storage_options=storage_options,
                encoding='utf_8'
            )
            print(f"Results successfully uploaded to s3://{self.bucket_name}/{filepath}")
        except Exception as e:
            print(f"Error uploading file to S3: {e}")
            raise


class FairGameAPI:
    """Flask routes and logic for the FairGame application."""

    DEFAULT_FOLDER = 'Fairgame_results'

    def __init__(self, uploader: S3Uploader) -> None:
        """
        Initializes the FairGameAPI with an S3Uploader for optional file storage.

        Args:
            uploader (S3Uploader): An instance of S3Uploader used for saving files to S3.
        """
        self.uploader = uploader
        self.game_factory = FairGameFactory()
        self.results_processor = ResultsProcessor()

    def create_and_run_games(self, config: dict):
        """
        Creates and runs games based on input configuration, processes outcomes,
        and optionally saves results to S3.

        Args:
            config (dict): Configuration dictionary for the games to be created and run.

        Returns:
            dict: JSON-serializable dictionary of results (DataFrame in dict form).
        """
        outcomes = self.game_factory.create_and_run_games(config)
        df = self.results_processor.process(outcomes)
        
        current_date = datetime.now().strftime('%Y%m%d')
        results_filepath = f"{self.DEFAULT_FOLDER}/{config['llm']}/{current_date}_{config['name']}.csv"

        # Attempt saving to S3 (skip if not configured)
        self.uploader.save(df, results_filepath)
        
        return df.to_dict(orient="index")

    def health_check(self):
        """
        Simple health check endpoint.

        Returns:
            dict: JSON object indicating status of the service.
        """
        return {
            "status": "OK",
            "message": "Service is running"
        }


app = Flask(__name__)

# Create a single S3Uploader and FairGameAPI instance
s3_uploader = S3Uploader()
fair_game_api = FairGameAPI(s3_uploader)

@app.route('/create_and_run_games', methods=['POST'])
def create_and_run_games_route():
    """Flask route for creating and running games."""
    config = request.json
    json_data = fair_game_api.create_and_run_games(config)
    return jsonify(json_data), 200

@app.route('/health', methods=['GET'])
def health_check_route():
    """Flask route for health check."""
    response = fair_game_api.health_check()
    return jsonify(response), 200

if __name__ == '__main__':
    # Launch the Flask application
    app.run(host='0.0.0.0', port=5003)
