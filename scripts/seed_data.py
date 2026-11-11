"""Demo data: 3 FICTIONAL restaurants in Al-Ahsa (names are invented; locations are real areas).

Prices are whole halalas (100 halalas = 1 SAR). Calories are rough per-serving estimates.
Diet tags: vegetarian, vegan, gluten_free, dairy_free, high_protein, spicy.
"""

RESTAURANTS = [
    {
        "slug": "nakhla-kitchen",
        "name": "Nakhla Kitchen",
        "nameAr": "مطبخ النخلة",
        "description": "Traditional Hasawi home cooking: rice, harees and jareesh.",
        "city": "Al-Hofuf",
        "district": "Al-Kut",
        "lat": 25.3797,
        "lng": 49.5867,
        "hours": "12:00-23:30",
        "owner": {"email": "owner.nakhla@example.com", "name": "Abdullah Al-Nakhli", "phone": "+966500000101"},
        "items": [
            {"slug": "hasawi-rice-chicken", "name": "Hasawi Red Rice with Chicken", "nameAr": "رز حساوي بالدجاج",
             "category": "Mains", "priceHalalas": 3500, "calories": 850, "dietTags": ["gluten_free", "high_protein"]},
            {"slug": "lamb-kabsa", "name": "Lamb Kabsa", "nameAr": "كبسة لحم",
             "category": "Mains", "priceHalalas": 5500, "calories": 1100, "dietTags": ["gluten_free", "high_protein", "dairy_free"]},
            {"slug": "harees", "name": "Harees", "nameAr": "هريس",
             "category": "Mains", "priceHalalas": 2200, "calories": 520, "dietTags": ["high_protein"]},
            {"slug": "jareesh", "name": "Jareesh", "nameAr": "جريش",
             "category": "Mains", "priceHalalas": 2000, "calories": 480, "dietTags": ["vegetarian"]},
            {"slug": "vegetable-saloona", "name": "Vegetable Saloona", "nameAr": "صالونة خضار",
             "category": "Sides", "priceHalalas": 1800, "calories": 260, "dietTags": ["vegan", "gluten_free", "dairy_free"]},
            {"slug": "laban", "name": "Laban", "nameAr": "لبن",
             "category": "Drinks", "priceHalalas": 500, "calories": 120, "dietTags": ["vegetarian", "gluten_free"]},
        ],
    },
    {
        "slug": "qaisariya-grill",
        "name": "Qaisariya Grill",
        "nameAr": "مشويات القيصرية",
        "description": "Charcoal grills and fresh mezze near the old souq.",
        "city": "Al-Hofuf",
        "district": "Al-Rifaah",
        "lat": 25.3712,
        "lng": 49.5741,
        "hours": "13:00-01:00",
        "owner": {"email": "owner.qaisariya@example.com", "name": "Khalid Al-Qaisi", "phone": "+966500000102"},
        "items": [
            {"slug": "shish-tawook", "name": "Shish Tawook Plate", "nameAr": "صحن شيش طاووق",
             "category": "Grills", "priceHalalas": 3200, "calories": 640, "dietTags": ["gluten_free", "high_protein"]},
            {"slug": "lamb-kofta", "name": "Lamb Kofta Plate", "nameAr": "صحن كفتة لحم",
             "category": "Grills", "priceHalalas": 3000, "calories": 720, "dietTags": ["gluten_free", "high_protein", "dairy_free"]},
            {"slug": "mixed-grill", "name": "Mixed Grill (for 2)", "nameAr": "مشاوي مشكلة لشخصين",
             "category": "Grills", "priceHalalas": 6500, "calories": 1500, "dietTags": ["gluten_free", "high_protein"]},
            {"slug": "hummus", "name": "Hummus", "nameAr": "حمص",
             "category": "Mezze", "priceHalalas": 1200, "calories": 330, "dietTags": ["vegan", "gluten_free", "dairy_free"]},
            {"slug": "fattoush", "name": "Fattoush", "nameAr": "فتوش",
             "category": "Mezze", "priceHalalas": 1500, "calories": 210, "dietTags": ["vegan", "dairy_free"]},
            {"slug": "spicy-chicken-wrap", "name": "Spicy Chicken Wrap", "nameAr": "راب دجاج حار",
             "category": "Sandwiches", "priceHalalas": 1800, "calories": 560, "dietTags": ["high_protein", "spicy"]},
        ],
    },
    {
        "slug": "mubarraz-dates-coffee",
        "name": "Mubarraz Dates & Coffee",
        "nameAr": "تمر وقهوة المبرز",
        "description": "Saudi coffee, Khalas dates and Hasawi sweets.",
        "city": "Al-Mubarraz",
        "district": "Al-Mubarraz Center",
        "lat": 25.4086,
        "lng": 49.5823,
        "hours": "07:00-23:00",
        "owner": {"email": "owner.mubarraz@example.com", "name": "Noura Al-Mubarrak", "phone": "+966500000103"},
        "items": [
            {"slug": "saudi-coffee", "name": "Saudi Coffee (dallah)", "nameAr": "قهوة سعودية (دلة)",
             "category": "Drinks", "priceHalalas": 800, "calories": 10, "dietTags": ["vegan", "gluten_free", "dairy_free"]},
            {"slug": "khalas-dates", "name": "Khalas Dates Box (250 g)", "nameAr": "علبة تمر خلاص ٢٥٠ غ",
             "category": "Dates", "priceHalalas": 2500, "calories": 700, "dietTags": ["vegan", "gluten_free", "dairy_free"]},
            {"slug": "kleija", "name": "Kleija (4 pcs)", "nameAr": "كليجا (٤ حبات)",
             "category": "Sweets", "priceHalalas": 1500, "calories": 520, "dietTags": ["vegetarian"]},
            {"slug": "luqaimat", "name": "Luqaimat with Date Syrup", "nameAr": "لقيمات بدبس التمر",
             "category": "Sweets", "priceHalalas": 1600, "calories": 480, "dietTags": ["vegetarian"]},
            {"slug": "balaleet", "name": "Balaleet", "nameAr": "بلاليط",
             "category": "Breakfast", "priceHalalas": 1700, "calories": 450, "dietTags": ["vegetarian"]},
            {"slug": "date-smoothie", "name": "Date & Milk Smoothie", "nameAr": "سموذي تمر وحليب",
             "category": "Drinks", "priceHalalas": 1800, "calories": 340, "dietTags": ["vegetarian", "gluten_free"]},
        ],
    },
]

# Menu categories owners can choose from (stored as CONFIG/CATEGORIES; extend later via CLI/console).
CATEGORIES = ["Breakfast", "Dates", "Drinks", "Grills", "Mains", "Mezze", "Sandwiches", "Sides", "Sweets"]

# Order numbers start after this, so the first order is #101.
COUNTER_START = 100
