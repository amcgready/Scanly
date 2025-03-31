import unittest
from src.core.file_processor import FileProcessor

class TestFileProcessor(unittest.TestCase):

    def setUp(self):
        self.file_processor = FileProcessor()

    def test_extract_show_name(self):
        filename = "ShowName.S01E01.mp4"
        expected_show_name = "ShowName"
        self.assertEqual(self.file_processor.extract_show_name(filename), expected_show_name)

    def test_extract_season_and_episode(self):
        filename = "ShowName.S01E01.mp4"
        expected_season = 1
        expected_episode = 1
        season, episode = self.file_processor.extract_season_and_episode(filename)
        self.assertEqual(season, expected_season)
        self.assertEqual(episode, expected_episode)

    def test_process_movie(self):
        filename = "MovieName (2023).mp4"
        expected_result = {
            'type': 'movie',
            'name': 'MovieName',
            'year': 2023
        }
        result = self.file_processor.process_file(filename)
        self.assertEqual(result, expected_result)

    def test_process_tv_show(self):
        filename = "ShowName.S01E01.mp4"
        expected_result = {
            'type': 'tv',
            'name': 'ShowName',
            'season': 1,
            'episode': 1
        }
        result = self.file_processor.process_file(filename)
        self.assertEqual(result, expected_result)

if __name__ == '__main__':
    unittest.main()