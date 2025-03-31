import unittest
from src.api.tmdb import fetch_show_details, fetch_movie_details

class TestTMDBAPI(unittest.TestCase):

    def test_fetch_show_details_valid(self):
        show_name = "Breaking Bad"
        result = fetch_show_details(show_name)
        self.assertIsInstance(result, dict)
        self.assertIn('id', result)
        self.assertIn('name', result)
        self.assertEqual(result['name'], show_name)

    def test_fetch_show_details_invalid(self):
        show_name = "Nonexistent Show"
        result = fetch_show_details(show_name)
        self.assertIsNone(result)

    def test_fetch_movie_details_valid(self):
        movie_name = "Inception"
        result = fetch_movie_details(movie_name)
        self.assertIsInstance(result, dict)
        self.assertIn('id', result)
        self.assertIn('title', result)
        self.assertEqual(result['title'], movie_name)

    def test_fetch_movie_details_invalid(self):
        movie_name = "Nonexistent Movie"
        result = fetch_movie_details(movie_name)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()