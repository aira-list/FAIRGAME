import os
import unittest

from langdetect import detect

from src.factory.fairgame_factory import FairGameFactory
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

        The factory dedupes symmetric pairs when every agent uses the same
        LLM, so 2 personalities x 2 agents collapses from 4 to 3 games:
        (a,a), (a,b), (b,b).
        """
        config = self.game_factory.load_config(self.CONFIG_FILE)
        self.game_factory.create_games(config)
        self.assertEqual(len(self.game_factory.games), 3)

    def test_factory_create_and_run_games(self):
        """
        Test that the factory creates and runs the correct number of games
        from a small test configuration, and that the results DataFrame
        has the expected shape.
        """
        results = self.game_factory.load_config_create_and_run_games(self.CONFIG_SMALL_FILE)
        results_df = self.processor.process(results)

        # 3 dedup'd permutations across 1 language; the processor schema
        # widens whenever new optional fields (e.g. ToM beliefs) are added,
        # so check the row count and a healthy column floor.
        self.assertEqual(results_df.shape[0], 3)
        self.assertGreater(results_df.shape[1], 18)

    def test_multilingual_scenario_en_fr(self):
        """
        Test that the multilingual scenario (English and French) is loaded
        and executed correctly. Verify that one of the configurations is in
        French by detecting the language of the prompt template.
        """
        config = self.game_factory.load_config(self.CONFIG_FILE_MULTILINGUAL)
        self.game_factory.create_games(config)
        all_games_config = self.game_factory.all_game_configurations()

        # 3 dedup'd permutations x 2 languages = 6 total game configurations.
        self.assertEqual(len(all_games_config), 6)

        # Verify the last (French) configuration uses French.
        prompt_template = self.game_factory.build_prompt_template(
            config, all_games_config.iloc[-1]["Language"]
        )
        language_detected = detect(prompt_template)
        self.assertEqual(language_detected, "fr")

        # Run the games and verify the results DataFrame length
        self.game_factory.run_games()
        results = self.game_factory.results_games()
        results_df = self.processor.process(results)
        self.assertEqual(len(results_df), 6)


if __name__ == "__main__":
    unittest.main()
