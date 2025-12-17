import gspread
from google.oauth2.service_account import Credentials
from .utils import extract_color_from_product_name

class SheetManager:
    def __init__(self, credentials_path, spreadsheet_id, config):
        self.config = config
        self.spreadsheet_id = spreadsheet_id
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        self.client = gspread.authorize(creds)
        
        self.product_sheet_name = config["sheets"]["product_sheet_name"]
        self.color_mapping_sheet_name = config["sheets"]["color_mapping_sheet_name"]

    def load_color_mapping(self):
        sh = self.client.open_by_key(self.spreadsheet_id).worksheet(self.color_mapping_sheet_name)
        rows = sh.get_all_values()
        mapping = {}
        # skip header
        for row in rows[1:]:
            if len(row) >= 3:
                c_name = row[0].strip().lower()
                c_id = row[2].strip()
                if c_name:
                    mapping[c_name] = c_id
        return mapping

    def append_color_mapping_batch(self, new_colors):
        if not new_colors:
            return
        
        sheet = self.client.open_by_key(self.spreadsheet_id).worksheet(self.color_mapping_sheet_name)
        existing = set()
        exist_values = sheet.get_all_values()[1:]
        for row in exist_values:
            if row and row[0]:
                existing.add(row[0].strip())
        
        final_new = []
        for c in new_colors:
            raw_str = c.strip()
            if raw_str and (raw_str not in existing):
                final_new.append(raw_str)
        
        if not final_new:
            return

        rows_to_append = [[x, "", ""] for x in final_new]
        sheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
        print(f"✅ Added {len(rows_to_append)} new entries to color_mapping.")

    def check_predefined_synonym(self, color_name_raw):
        """
        Check if raw color name exists in synonyms of config.
        Returns category ID if found, else None.
        """
        text = color_name_raw.strip()
        color_cats = self.config.get("color_categories", {})
        
        for cat, (cid, synonyms) in color_cats.items():
            if text in synonyms:
                return cid
        return None

    def process_products(self, analyzer):
        """
        Main logic loop: iterate rows, check color, analyze image if needed, update sheet.
        """
        print(f"Reading sheet: {self.product_sheet_name}...")
        product_sheet = self.client.open_by_key(self.spreadsheet_id).worksheet(self.product_sheet_name)
        headers = product_sheet.row_values(1)

        cols = self.config["sheets"]["columns"]
        try:
            color_id_col_idx = headers.index(cols["color_id"])
            image_url_col_idx = headers.index(cols["image_url"])
            product_name_col_idx = headers.index(cols["product_name"])
        except ValueError as e:
            print(f"❌ Column not found: {e}")
            return

        data = product_sheet.get_all_values()
        color_map_dict = self.load_color_mapping()
        pending_colors = set()
        updated_values = []
        
        # Max index we need to access safely
        max_colidx = max(color_id_col_idx, image_url_col_idx, product_name_col_idx)

        # Iterate data rows (skipping header)
        for i, row in enumerate(data[1:], start=2):
            if len(row) <= max_colidx:
                updated_values.append(["N/A"])
                continue

            existing_id = row[color_id_col_idx].strip()
            
            # If already has ID, keep it (unless we want to force update? assume no for now)
            if existing_id not in ["", "N/A"]:
                updated_values.append([existing_id])
                continue

            product_name = row[product_name_col_idx].strip()
            image_url = row[image_url_col_idx].strip()
            
            raw_color = extract_color_from_product_name(product_name)
            color_key = raw_color.lower().strip()

            # (A) Check config synonyms
            predef_id = None
            if raw_color:
                predef_id = self.check_predefined_synonym(raw_color)

            new_val = "N/A"

            if predef_id:
                new_val = f"={predef_id}"
            else:
                # (B) Logic for known/unknown mapping
                if color_key:
                    cid = color_map_dict.get(color_key)
                    if cid and cid not in ["", "N/A"]:
                        # Known mapping
                        new_val = f"={cid}"
                    elif cid == "" or cid == "N/A":
                        # Known but empty ID -> Image Analysis
                        new_val = analyzer.analyze(image_url) if image_url else "N/A"
                    else:
                        # Unknown -> Image Analysis & Add to pending
                        pending_colors.add(raw_color)
                        new_val = analyzer.analyze(image_url) if image_url else "N/A"
                else:
                    # No color in name -> Image Analysis
                    new_val = analyzer.analyze(image_url) if image_url else "N/A"
            
            updated_values.append([new_val])
            if (i-1) % 10 == 0:
                print(f"Processed row {i}...")

        # Bulk Update color mapping
        if pending_colors:
            self.append_color_mapping_batch(pending_colors)

        # Bulk Update Product Sheet
        # CAUTION: This overwrites the column. We must match the range exactly.
        # Original script used `update` with column range.
        col_letter = chr(64 + (color_id_col_idx + 1)) # 1-based index to A,B,C...
        range_name = f"{col_letter}2:{col_letter}{len(updated_values)+1}"
        
        print(f"Updating {len(updated_values)} rows in range {range_name}...")
        product_sheet.update(
            range_name=range_name,
            values=updated_values,
            value_input_option='USER_ENTERED'
        )
        print("🎨 Color ID update complete!")
