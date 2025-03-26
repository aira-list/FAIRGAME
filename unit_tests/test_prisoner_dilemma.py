import os
import unittest
from langdetect import detect

from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor


class TestPrisonerDilemma(unittest.TestCase):
    """
    Unit tests for the Prisoner's Dilemma game logic and scenarios using
    the FairGameFactory, IoManager, and ResultsProcessor classes.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up class-level constants, including resource paths and configuration file names.
        This method is called once before any tests run.
        """
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)

        cls.RESOURCES_PATH = script_dir
        cls.CONFIG_FILE = "prisoner_dilemma.json"
        cls.CONFIG_SMALL_FILE = "prisoner_dilemma_few_permutations.json"
        cls.CONFIG_FILE_MULTILINGUAL = "prisoner_dilemma_en_fr_few_permutations.json"

    def setUp(self):
        """
        Create the IoManager and FairGameFactory for each test.
        This method is called before every test method.
        """
        self.io_manager = IoManager(root_path=self.RESOURCES_PATH)
        self.game_factory = FairGameFactory()
        self.game_factory.set_io_manager(self.io_manager)
        self.processor = ResultsProcessor()

    def test_factory_create_games(self):
        """
        Test that the factory creates the expected number of games
        from the standard configuration file.
        """
        config = self.game_factory.load_config(self.CONFIG_FILE)
        self.game_factory.create_games(config)
        self.assertEqual(len(self.game_factory.games), 4)

    def test_factory_create_and_run_games(self):
        """
        Test that the factory creates and runs the correct number of games
        from a small test configuration, and that the results DataFrame
        has the expected shape.
        """
        results = self.game_factory.load_config_create_and_run_games(self.CONFIG_SMALL_FILE)
        results_df = self.processor.process(results)

        # Expecting 4 rows and 20 columns as per the configuration setup
        self.assertEqual(results_df.shape[0], 4)
        self.assertEqual(results_df.shape[1], 20)

    def test_multilingual_scenario_en_fr(self):
        """
        Test that the multilingual scenario (English and French) is loaded
        and executed correctly. Verify that one of the configurations is in
        French by detecting the language of the prompt template.
        """
        config = self.game_factory.load_config(self.CONFIG_FILE_MULTILINGUAL)
        self.game_factory.create_games(config)
        all_games_config = self.game_factory.all_game_configurations()

        # We expect 8 total game configurations for the bilingual scenario
        self.assertEqual(len(all_games_config), 8)

        # Verify the 8th game uses French
        prompt_template = self.game_factory.build_prompt_template(
            config,
            all_games_config.iloc[7]['Language']
        )
        language_detected = detect(prompt_template)
        self.assertEqual(language_detected, 'fr')

        # Run the games and verify the results DataFrame length
        self.game_factory.run_games()
        results = self.game_factory.results_games()
        results_df = self.processor.process(results)
        self.assertEqual(len(results_df), 8)


if __name__ == "__main__":
    unittest.main()
