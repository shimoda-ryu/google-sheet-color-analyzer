import os
import sys
from dotenv import load_dotenv
from .utils import load_config
from .sheets import SheetManager
from .analyzer import ImageAnalyzer

def main():
    print("🚀 Starting Google Sheets Color Analyzer...")
    
    # Load .env
    load_dotenv()
    
    # Load Config
    try:
        config = load_config()
        print("✅ Configuration loaded.")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

    # Validate Environment Variables
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not spreadsheet_id or not credentials_path:
        print("❌ Missing environment variables. Please check .env file.")
        print("Required: SPREADSHEET_ID, GOOGLE_APPLICATION_CREDENTIALS")
        sys.exit(1)

    if not os.path.exists(credentials_path):
        print(f"❌ Credentials file not found at: {credentials_path}")
        sys.exit(1)

    # Initialize Components
    try:
        analyzer = ImageAnalyzer(config)
        manager = SheetManager(credentials_path, spreadsheet_id, config)
        print("✅ Components initialized.")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

    # Run Process
    try:
        manager.process_products(analyzer)
        print("🎉 All tasks completed successfully.")
    except Exception as e:
        print(f"❌ An error occurred during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
