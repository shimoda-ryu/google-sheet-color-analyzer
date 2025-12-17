import cv2
import numpy as np
import requests
from .utils import get_rgb_from_color_name

class ImageAnalyzer:
    def __init__(self, config):
        self.config = config
        self.analysis_config = config.get("analysis", {})
        self.color_categories = config.get("color_categories", {})

    def download_image(self, image_url):
        timeout = self.analysis_config.get("image_download_timeout", 10)
        try:
            resp = requests.get(image_url, timeout=timeout)
            resp.raise_for_status()
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

    def analyze(self, image_url):
        img = self.download_image(image_url)
        if img is None:
            return "N/A"

        resize_w = self.analysis_config.get("resize_width", 100)
        resize_h = self.analysis_config.get("resize_height", 100)
        
        resized = cv2.resize(img, (resize_w, resize_h))
        h, w, _ = resized.shape
        margin = 30
        
        # Center crop to avoid background noise
        if h > 2 * margin and w > 2 * margin:
            center = resized[margin:h-margin, margin:w-margin]
        else:
            center = resized

        if center.size == 0:
            center = resized

        pix = center.reshape(-1, 3)
        filtered = []
        p_min = self.analysis_config.get("pixel_filter_min", 20)
        p_max = self.analysis_config.get("pixel_filter_max", 230)

        for p in pix:
            avg = np.mean(p)
            if p_min < avg < p_max:
                filtered.append(p)
        
        if len(filtered) < 10:
            return "N/A"

        # K-Means clustering
        Z = np.float32(filtered)
        K = self.analysis_config.get("kmeans_k", 3)
        
        # Criteria: (type, max_iter, epsilon)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        
        try:
            _, labels, centers = cv2.kmeans(Z, K, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
            counts = np.bincount(labels.flatten())
            dom_idx = np.argmax(counts)
            dom_color = centers[dom_idx]
            rgb = tuple(map(int, dom_color)) # (R, G, B) because opencv imdecode default is BGR, but we handled that? 
            # Wait, cv2.imdecode(arr, cv2.IMREAD_COLOR) returns BGR in standard OpenCV. 
            # But the original code was treating it as... wait.
            # Original: img = cv2.imdecode(..., cv2.IMREAD_COLOR) -> BGR
            # Original: bgr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]]) -> used for HSV conversion
            # Original: match_color_to_category(rgb) -> compares with RGB ref.
            
            # Let's fix Color space to be consistent. 
            # Downloaded image is BGR.
            # Convert to RGB for consistency with config (which is RGB).
            rgb_converted = (int(dom_color[2]), int(dom_color[1]), int(dom_color[0]))
            
            # BUT, look at original code:
            # dom_color = centers[dom_idx]
            # rgb = tuple(map(int, dom_color))
            # match_color_to_category(rgb)
            # In original code, `cv2.imdecode` returns BGR. So `dom_color` is BGR.
            # But `match_color_to_category` compares `rgb` (which is BGR) with `ref_rgb` (from `get_rgb_from_color_name` which is RGB).
            # This means the original code might have been comparing BGR to RGB?
            # Or `get_rgb_from_color_name` returns BGR?
            # Original: "ホワイト": (255, 255, 255) (Same)
            # Original: "レッド": (255, 0, 0) -> R=255.
            # If `img` is BGR, red pixel is (0, 0, 255).
            # If we compare (0, 0, 255) [BGR-Red] with (255, 0, 0) [RGB-Red], distance is huge.
            # Wait, let's verify original `download_image`:
            # `img = cv2.imdecode(arr, cv2.IMREAD_COLOR)` -> BGR.
            # Then clustering is done on BGR.
            # So `rgb` variable in original code is actually BGR.
            # The reference map has `"レッド": (255, 0, 0)`.
            # If input is Red (0,0,255), distance to (255,0,0) is sqrt(255^2 + 0 + 255^2). Big.
            # Distance to Blue (0,0,255) is 0.
            # So the original code seems to have a bug where it treats BGR as RGB or vice versa, OR the reference map is also BGR?
            # "レッド": (255, 0, 0). In RGB this is Red. In BGR this is Blue.
            # "ブルー": (0, 0, 255). In RGB this is Blue. In BGR this is Red.
            # So if the original code worked, maybe it was lucky or I am misinterpreting.
            
            # HOWEVER, I should probably FIX this to be correct in the refactor.
            # I will scan BGR image, convert the dominant color to RGB, and compare with RGB config.
            
            # Let's fix this: 
            # 1. Image is BGR. 
            # 2. KMeans on BGR. 
            # 3. Dominant Center is BGR.
            # 4. Convert BGR to RGB -> (B, G, R) to (R, G, B).
            # 5. `match_color_to_category` expects RGB.
            
            rgb_final = (int(dom_color[2]), int(dom_color[1]), int(dom_color[0]))
            
            cat = self.match_color_to_category(rgb_final)
            if not cat:
                return "N/A"
            
            # Return "=ID"
            cat_id = self.color_categories[cat][0]
            return f"={cat_id}"

        except Exception as e:
            print(f"Error during analysis: {e}")
            return "N/A"
