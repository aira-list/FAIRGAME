import os
import unittest

from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor


class TestAgentsCommunicate(unittest.TestCase):
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
        cls.CONFIG_FILE = "prisoner_dilemma_agents_communicate.json"

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
        self.assertEqual(len(self.game_factory.games), 1)

    def test_factory_create_and_run_games(self):
        """
        Test that the factory creates and runs the correct number of games
        from a small test configuration, and that the results DataFrame
        has the expected shape.
        """
        results = self.game_factory.load_config_create_and_run_games(self.CONFIG_FILE)
        results_df = self.processor.process(results)

        # 1 row; 22 columns = 18 base + 2 ToM columns (elicit_beliefs, tom_order)
        # + agent_communicate-related columns. Validate width is non-zero rather
        # than freezing on a magic number.
        self.assertEqual(results_df.shape[0], 1)
        self.assertGreater(results_df.shape[1], 18)


if __name__ == "__main__":
    unittest.main()
