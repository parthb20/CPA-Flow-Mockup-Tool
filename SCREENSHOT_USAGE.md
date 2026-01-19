# 📸 Screenshot API Usage Explanation

## 🎯 How Many Screenshots Per Flow?

### **Current Behavior (FIXED):**

Screenshots are **ONLY generated for 403 errors** now (not every page load).

### **Per Flow Breakdown:**

**3 URLs per flow:**
1. Publisher URL
2. SERP URL
3. Landing Page URL

**Per URL Behavior:**
- ✅ **Normal case (200 OK)**: Renders HTML directly → **0 screenshots**
- 🚫 **403 Error**: Uses ScreenshotOne API → **1 screenshot**

### **Example Scenarios:**

#### Scenario 1: All URLs work fine
- Publisher: 200 OK → renders HTML → **0 screenshots**
- SERP: 200 OK → renders HTML → **0 screenshots**  
- Landing Page: 200 OK → renders HTML → **0 screenshots**
- **Total: 0 screenshots per flow** ✅

#### Scenario 2: Landing page blocks access
- Publisher: 200 OK → **0 screenshots**
- SERP: 200 OK → **0 screenshots**
- Landing Page: 403 → **1 screenshot** (forbes.com, etc.)
- **Total: 1 screenshot per flow**

#### Scenario 3: All pages block access (rare)
- Publisher: 403 → **1 screenshot**
- SERP: 403 → **1 screenshot**
- Landing Page: 403 → **1 screenshot**
- **Total: 3 screenshots per flow** (worst case)

---

## 🔄 Device-Specific Screenshots

**Each device uses different viewport dimensions:**
- Mobile: 390×844px
- Tablet: 1024×768px
- Laptop: 1920×1080px

**Cache key = (URL + device)**

### Example:
If you view `forbes.com` (403 error) on all 3 devices:
- Mobile: `forbes.com` + mobile → **1 API call** → cached
- Tablet: `forbes.com` + tablet → **1 API call** → cached
- Laptop: `forbes.com` + laptop → **1 API call** → cached
- **Total: 3 API calls for same URL across devices**

---

## 💾 Caching Strategy

```python
@st.cache_data(ttl=604800, show_spinner=False)  # 7 days
def get_screenshot_url(url, device='mobile'):
    # Generates ScreenshotOne API URL
```

**Cache duration: 7 days (604800 seconds)**

### What Gets Cached:
✅ Screenshot URLs (not re-generated for 7 days)
✅ OCR text extraction results (7 days)
✅ Similarity calculations (1 week)

### Cache Invalidation:
- After 7 days, next view will regenerate screenshot
- Clearing Streamlit cache will force regeneration
- Different devices = different cache entries

---

## 🚫 Why Your Limit Got Used Up

### **Previous Behavior (BEFORE FIX):**

❌ **Problem**: `capture_with_playwright()` was called for **EVERY URL**, and it ALWAYS called Screenshot API as fallback (even for 200 OK responses).

**Result:**
- Every page view: 3 URLs × 1 screenshot each = **3 API calls**
- Switching devices: 3 URLs × 3 devices = **9 API calls**
- Refreshing 10 times: 3 × 10 = **30 API calls**
- Switching devices 3 times: 9 × 3 = **27 API calls**

**Total for normal usage: ~50-90 API calls easily hit!**

### **New Behavior (AFTER FIX):**

✅ **Fixed**: Screenshots ONLY for 403 errors

**Result:**
- Normal page (200 OK): **0 API calls**
- 403 error page: **1 API call** → cached for 7 days
- Subsequent views: **0 API calls** (uses cache)

**Typical usage now: 1-3 API calls per NEW flow** (only if 403s)

---

## 📊 API Call Examples

### Example 1: Fresh Flow (1 403 error)
1. View flow with `forbes.com` landing page (403)
   - Publisher: 0 calls (200 OK)
   - SERP: 0 calls (200 OK)
   - Landing: **1 call** (403)
   - **Total: 1 call**

2. Refresh same flow
   - All cached → **0 calls**

3. Switch to tablet
   - Publisher: 0 calls (cached HTML)
   - SERP: 0 calls (cached HTML)
   - Landing: **1 call** (new device dimension)
   - **Total: 1 call**

### Example 2: Different Flow
1. View new flow with `cnn.com` (403)
   - **1 call** (new URL, not cached)

2. Back to `forbes.com` flow
   - **0 calls** (cached from before)

---

## 🔍 OCR (Image-to-Text) Behavior

**Used ONLY when page content fetch fails (403 errors):**

1. Try to fetch page HTML/text directly
2. If fails (403) → generate screenshot
3. Download screenshot → run EasyOCR → extract text
4. Use extracted text for similarity calculations

**OCR Cache:**
- Same 7-day cache as screenshots
- Key = screenshot URL
- Results cached permanently during session

**Models Downloaded (First Run Only):**
- ~500MB for EasyOCR models
- Downloaded once, cached forever on Streamlit Cloud

---

## ⚡ Performance Tips

### To Minimize API Calls:

1. **Don't refresh unnecessarily** - cache lasts 7 days
2. **Stick to one device** while exploring flows
3. **Use same flows** - switching to new URLs = new screenshots
4. **Wait for cache** - refreshing immediately wastes calls

### Current Limits:

**ScreenshotOne API Free Tier:**
- 100 screenshots/month
- Resets monthly
- Each unique (URL + device) = 1 screenshot

**Typical Usage:**
- Testing 1 flow: 1-3 calls
- Testing 10 flows: 10-30 calls (if all have 403s)
- Normal usage: <30 calls/month easily

---

## ✅ Summary

**Before Fix:**
- ❌ Every page view = 3 screenshots
- ❌ 90% limit used in few refreshes

**After Fix:**
- ✅ Only 403 errors = screenshots
- ✅ Everything else = direct HTML rendering
- ✅ 7-day caching prevents repeated calls
- ✅ <30 API calls/month for normal usage

**Your app is now efficient! 🎉**
