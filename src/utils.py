import yaml
import os

def load_config(config_path="config/settings.yaml"):
    """
    Load configuration from a YAML file.
    """
    # Adjust path if running from root or src
    if not os.path.exists(config_path):
        # try one level up if we are inside src/
        alt_path = os.path.join("..", config_path)
        if os.path.exists(alt_path):
            config_path = alt_path
        else:
            # try absolute path based on this file's location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "settings.yaml")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_rgb_from_color_name(color_name, config):
    """
    Retrieve RGB tuple from config based on color name.
    Returns default gray (128, 128, 128) if not found.
    """
    color_defs = config.get("color_definitions", {})
    rgb = color_defs.get(color_name)
    if rgb:
        return tuple(rgb)
    return (128, 128, 128)

def extract_color_from_product_name(product_name):
    """
    Extract color hint from product name (assuming 'Product Name　ColorName' format).
    """
    # Using the same logic as original: split by full-width space "　"
    parts = product_name.split("\u3000", 1)  # \u3000 is full-width space
    if len(parts) > 1:
        return parts[1].strip()
    return ""
