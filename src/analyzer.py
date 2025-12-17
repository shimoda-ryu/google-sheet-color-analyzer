```python
import cv2
import numpy as np
import requests
from .utils import get_rgb_from_color_name

try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    print("⚠️ rembg module not found. Background removal will be disabled.")

class ImageAnalyzer:
    def __init__(self, config):
        self.config = config
        self.analysis_config = config.get("analysis", {})
        self.color_categories = config.get("color_categories", {})
        self.use_rembg = self.analysis_config.get("use_rembg", False)
        
        if self.use_rembg and not REMBG_AVAILABLE:
            print("⚠️ use_rembg is True but rembg library is not installed. Falling back to simple analysis.")
            self.use_rembg = False

    def download_image(self, image_url):
        timeout = self.analysis_config.get("image_download_timeout", 10)
        try:
            resp = requests.get(image_url, timeout=timeout)
            resp.raise_for_status()
            # If using rembg, we might want the raw bytes or decode carefully
            # cv2.imdecode returns BGR.
            arr = np.frombuffer(resp.content, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"❌ Image download error: {e} -> {image_url}")
            return None

    def compute_weighted_distance(self, rgb, ref, color_name):
        # Weighted distance logic
        # Red-ish colors get a weight boost on Red component
        red_keywords = ["レッド", "ワインレッド", "バーガンディ", "ピンク", "ローズ", "フクシア"]
        wR = 1.0
        if any(kw in color_name for kw in red_keywords):
            wR = 1.5

        dr = (rgb[0] - ref[0]) * wR
        dg = (rgb[1] - ref[1])
        db = (rgb[2] - ref[2])
        base_dist = (dr*dr + dg*dg + db*db)**0.5

        # Saturation/Value check for Black/Gray handling
        bgr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
        h, s, v = hsv
        
        # If highly saturated and bright, penalize gray/black matches
        if s > 70 and v > 80:
            gray_keywords = ["ブラック", "チャコール", "スモーク", "グレー", "ライトグレー", "シルバー"]
            if any(kw in color_name for kw in gray_keywords):
                base_dist += 30

        return base_dist

    def match_color_to_category(self, rgb_color):
        min_dist = float("inf")
        best_cat = None
        
        for cat, (cid, synonyms) in self.color_categories.items():
            for cname in synonyms:
                ref_rgb = get_rgb_from_color_name(cname, self.config)
                dist = self.compute_weighted_distance(rgb_color, ref_rgb, cname)
                if dist < min_dist:
                    min_dist = dist
                    best_cat = cat
        return best_cat

    def remove_background(self, img):
        """
        Use rembg to remove background.
        Input: BGR image (OpenCV format)
        Output: Masked image with transparency info, or list of valid pixels.
        """
        # rembg expects RGB or byte input, returns RGBA
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        try:
            # remove() returns the image with alpha channel
            output = remove(img_rgb)
            # output is a numpy array (H, W, 4) -> R, G, B, A
            return output
        except Exception as e:
            print(f"⚠️ Background removal failed: {e}")
            return None

    def analyze(self, image_url):
        img = self.download_image(image_url)
        if img is None:
            return "N/A"

        resize_w = self.analysis_config.get("resize_width", 100)
        resize_h = self.analysis_config.get("resize_height", 100)
        
        # If rembg is enabled
        if self.use_rembg:
            # rembg is expensive, run it on original size (or slightly smaller for speed) before resizing?
            # Re-sizing BEFORE rembg might hurt accuracy of edge detection.
            # But high-res rembg is slow.
            # For 128x128 output, maybe we don't need 4K input. 
            # Let's resize to a reasonable intermediate like 300x300, then rembg, then filter.
            
            # For speed, let's keep original unless it's huge
            h, w = img.shape[:2]
            if h > 500 or w > 500:
                 img = cv2.resize(img, (500, 500))

            output_rgba = self.remove_background(img)
            
            if output_rgba is not None:
                # Extract pixels where Alpha > 0
                # Filter out transparent pixels
                # output_rgba is (H, W, 4)
                # Flatten
                flat = output_rgba.reshape(-1, 4)
                # Filter alpha > 10 (allow some semi-transparent edge to be ignored)
                valid_pixels = flat[flat[:, 3] > 10]
                
                if len(valid_pixels) > 0:
                    # Valid pixels are [R, G, B, A]
                    # We need [B, G, R] for OpenCV processing consistency OR just use [R, G, B] if we align logic.
                    # Current downstream uses `rgb_converted` logic assuming BGR input for Kmeans.
                    # Let's standardize on RGB for Clustering to avoid confusion.
                    
                    # Take RGB part
                    pix = valid_pixels[:, :3]
                    
                    # Already RGB because rembg input was RGB and output is RGB
                    # So `pix` is RGB
                    
                    # Skip the "filtered" logic (p_min/p_max) if we trust rembg?
                    # The original filtered logic removed "white background" and "black background" by brightness.
                    # With rembg, we shouldn't filter by brightness (a white shirt is valid!).
                    # So we skip brightness filter.
                    
                    filtered = pix
                else:
                    # Fallback if rembg removed everything?
                    filtered = []
            else:
                # Fallback to standard flow
                filtered = []
        else:
            # Standard Flow
            resized = cv2.resize(img, (resize_w, resize_h))
            h, w, _ = resized.shape
            margin = 30
            
            if h > 2 * margin and w > 2 * margin:
                center = resized[margin:h-margin, margin:w-margin]
            else:
                center = resized

            if center.size == 0:
                center = resized

            # Is center BGR? Yes.
            # Convert to RGB for consistency with rembg path? 
            # Original code logic:
            #   pix = center.reshape(-1, 3) (BGR)
            #   loops pixels
            #   centers (BGR)
            #   rgb = (centers[2], centers[1], centers[0]) (RGB)
            
            # Let's convert to RGB here to unify paths
            center_rgb = cv2.cvtColor(center, cv2.COLOR_BGR2RGB)
            pix = center_rgb.reshape(-1, 3)

            p_min = self.analysis_config.get("pixel_filter_min", 20)
            p_max = self.analysis_config.get("pixel_filter_max", 230)
            
            filtered = []
            for p in pix:
                avg = np.mean(p)
                if p_min < avg < p_max:
                    filtered.append(p)

        if len(filtered) < 10:
            return "N/A"

        # K-Means clustering
        Z = np.float32(filtered)
        K = self.analysis_config.get("kmeans_k", 3)
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        
        try:
            _, labels, centers = cv2.kmeans(Z, K, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
            counts = np.bincount(labels.flatten())
            dom_idx = np.argmax(counts)
            dom_color = centers[dom_idx]
            
            # `dom_color` is RGB now (because we unified input to be RGB)
            rgb_final = (int(dom_color[0]), int(dom_color[1]), int(dom_color[2]))
            
            cat = self.match_color_to_category(rgb_final)
            if not cat:
                return "N/A"
            
            cat_id = self.color_categories[cat][0]
            return f"={cat_id}"

        except Exception as e:
            print(f"Error during analysis: {e}")
            return "N/A"
```
