import pytest
from src.analyzer import ImageAnalyzer
from src.utils import load_config

# Mock Config
MOCK_CONFIG = {
    "color_categories": {
        "Red系": [4, ["レッド"]],
        "Blue系": [5, ["ブルー"]],
    },
    "color_definitions": {
        "レッド": [255, 0, 0],
        "ブルー": [0, 0, 255],
    },
    "analysis": {}
}

@pytest.fixture
def analyzer():
    return ImageAnalyzer(MOCK_CONFIG)

def test_weighted_distance_red_boost(analyzer):
    # Test that red keywords get weight boost
    # Red target vs Red reference
    # If perfect match, distance is 0
    rgb = (255, 0, 0)
    ref = (255, 0, 0)
    dist = analyzer.compute_weighted_distance(rgb, ref, "レッド")
    assert dist == 0.0

    # Red target vs slightly off reference
    # "レッド" has wR=1.5
    rgb_off = (245, 0, 0) # diff 10
    # distance = sqrt( (10*1.5)^2 + 0 + 0 ) = 15.0
    dist_red = analyzer.compute_weighted_distance(rgb_off, ref, "レッド")
    assert dist_red == 15.0
    
    # "ブルー" (no boost)
    # distance = sqrt( (10*1.0)^2 ) = 10.0
    dist_blue = analyzer.compute_weighted_distance(rgb_off, ref, "ブルー")
    assert dist_blue == 10.0

def test_match_color_to_category_exact(analyzer):
    # Red Match
    rgb_red = (255, 0, 0)
    cat = analyzer.match_color_to_category(rgb_red)
    assert cat == "Red系"

    # Blue Match
    rgb_blue = (0, 0, 255)
    cat = analyzer.match_color_to_category(rgb_blue)
    assert cat == "Blue系"

def test_match_color_to_category_approximate(analyzer):
    # Close to Red
    rgb_near_red = (250, 10, 10) 
    cat = analyzer.match_color_to_category(rgb_near_red)
    assert cat == "Red系"
