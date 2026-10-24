"""ListingDoctor rule data: limits, character lists and word lists per language.

All checks in ld_core.py read their thresholds from here, so a policy change is a one-line edit.
Sources and dates for every limit: references/rules.md.
"""

# ---------------------------------------------------------------- limits
TITLE_MAX = 75             # characters incl. spaces, all non-media categories, since 2026-07-27 (rules.md T1)
TITLE_MAX_MEDIA = 200      # books, music, video/DVD, software keep the Jan-2025 limit (rules.md T3)
MEDIA_PRODUCT_TYPES = {'abis_book', 'book', 'books', 'abis_music', 'music', 'abis_dvd', 'dvd', 'video', 'video_dvd',
                       'abis_video', 'software', 'abis_software'}
TITLE_SHORT = 30           # below this the title wastes ranking room (warning)
TITLE_MAX_REPEAT = 2       # same word max. 2x (articles/prepositions/conjunctions excluded) (rules.md T5)
HIGHLIGHTS_MAX = 125       # "Item Highlights" / "Artikel-Highlights", searchable, since 2026-07-27 (rules.md T2)
BULLET_RECOMMENDED = 5
BULLET_MIN_CHARS = 10
BULLET_SOFT_MAX = 255      # Amazon guideline; longer bullets get truncated in many views
BULLET_HARD_MAX = 500      # flat-file field limit in most categories
DESCRIPTION_MAX = 2000
BACKEND_MAX_BYTES = 249    # UTF-8 bytes; over the limit the whole field may be ignored

# characters Amazon does not allow in titles (unless part of the brand name)
TITLE_FORBIDDEN_CHARS = set('!$?_{}^¬¦')
TITLE_DISCOURAGED_CHARS = set('~#<>*®™©')
# special characters not allowed in bullet points
BULLET_FORBIDDEN_CHARS = set('™®©€…†‡¢£¥±¶§¿¡º')
EMOJI_RANGES = [(0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x1F000, 0x1F2FF), (0xFE0F, 0xFE0F), (0x2B00, 0x2BFF)]

# words that do not count for the "max. 2x" title rule
STOPWORDS = {
    'en': {'a', 'an', 'the', 'and', 'or', 'nor', 'but', 'for', 'of', 'in', 'on', 'at', 'to', 'by', 'with', 'from',
           'as', 'into', 'over', 'under', 'up', 'x', '&', '-', '+', 'per', 'vs'},
    'de': {'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines', 'einem', 'einen', 'und', 'oder',
           'aber', 'für', 'mit', 'von', 'vom', 'zu', 'zum', 'zur', 'im', 'in', 'am', 'an', 'auf', 'aus', 'bei', 'unter',
           'über', 'ohne', 'bis', 'x', '&', '-', '+', 'je', 'pro'},
}
STOPWORDS['fr'] = {'le', 'la', 'les', 'un', 'une', 'des', 'et', 'ou', 'pour', 'avec', 'de', 'du', 'en', 'à', 'au', 'aux', 'sur', 'sans', 'x', '&', '-'}
STOPWORDS['it'] = {'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'una', 'e', 'o', 'per', 'con', 'di', 'da', 'in', 'a', 'su', 'senza', 'x', '&', '-'}
STOPWORDS['es'] = {'el', 'la', 'los', 'las', 'un', 'una', 'y', 'o', 'para', 'con', 'de', 'del', 'en', 'a', 'al', 'sin', 'por', 'x', '&', '-'}

# promotional / sales language. STRONG = not allowed (error), SOFT = usually rejected or risky (warning)
PROMO_STRONG = {
    'en': ['free shipping', 'best seller', 'bestseller', 'best-selling', 'hot item', 'hot sale', 'on sale',
           'cheapest', 'lowest price', 'limited time', 'buy now', 'top rated', 'top-rated', '#1', 'no. 1',
           'number one', 'amazon choice', "amazon's choice", 'special offer', '100% satisfaction',
           'satisfaction guaranteed', 'money back', 'money-back', 'risk free', 'risk-free', 'award winning',
           'award-winning', 'full refund', 'lifetime guarantee', 'unconditional guarantee', 'buy it now',
           'order now', 'no questions asked', 'hassle-free return', 'hassle free return'],
    'de': ['kostenloser versand', 'gratis versand', 'versandkostenfrei', 'bestseller', 'verkaufsschlager',
           'sonderangebot', 'rabatt', 'günstigste', 'billigste', 'tiefpreis', 'nur heute', 'jetzt kaufen',
           'nur für kurze zeit', 'top bewertet', 'nr. 1', 'nr.1', 'nummer 1', 'amazons tipp', 'schnäppchen',
           'lebenslange garantie', 'volle rückerstattung', 'jetzt bestellen', 'bestellen sie jetzt', 'bei nichtgefallen',
           'rückgabegarantie', 'zufriedenheit garantiert', 'bester kundenservice',
           '100 % zufriedenheit', '100% zufriedenheit', 'zufriedenheitsgarantie', 'geld-zurück', 'geld zurück',
           'risikofrei'],
}
PROMO_SOFT = {
    'en': ['sale', 'discount', 'deal', 'limited offer', 'gift idea', 'guarantee', 'guaranteed', 'warranty',
           'new arrival', 'brand new', 'perfect gift'],
    'de': ['angebot', 'jetzt reduziert', 'stark reduziert', 'reduzierter preis', 'limitiert', 'geschenkidee', 'garantie', 'garantiert', 'neuheit', 'brandneu',
           'perfektes geschenk', 'testsieger'],
}

# health / medical / pesticide claims – need registration or proof, usually blocked by Amazon (warning)
HEALTH = {
    'en': ['cure', 'cures', 'heals', 'treats disease', 'prevents disease', 'prevent infection', 'prevents infection',
           'anti-inflammatory', 'pain relief', 'relieves pain', 'fda approved', 'fda-approved', 'clinically proven',
           'antibacterial', 'anti-bacterial', 'antimicrobial', 'anti-microbial', 'antiviral', 'anti-viral',
           'antifungal', 'kills germs', 'kills bacteria', 'kills 99', 'disinfects', 'sanitizes', 'covid',
           'coronavirus', 'detox', 'weight loss', 'boosts immunity', 'immune system', 'disinfectant',
           'mold-resistant', 'mould-resistant', 'insect repellent', 'repels mosquitoes', 'pest control',
           'fda cleared', 'fda-cleared'],
    'de': ['heilt', 'heilend', 'lindert', 'beugt krankheiten vor', 'gegen krankheiten', 'entzündungshemmend',
           'schmerzlindernd', 'klinisch bewiesen', 'klinisch getestet', 'antibakteriell', 'antimikrobiell',
           'antiviral', 'fungizid', 'tötet keime', 'tötet bakterien', 'desinfiziert', 'desinfizierend', 'keimfrei',
           'corona', 'covid', 'entgiftet', 'entgiftend', 'zum abnehmen', 'stärkt das immunsystem', 'keimtötend',
           'schimmelresistent', 'mückenschutz', 'insektenabweisend', 'schädlingsbekämpfung', 'behandelt'],
}

# EU Empowering Consumers Directive (EU) 2024/825 – generic environmental claims without proof (warning)
ECO = {
    'en': ['eco-friendly', 'eco friendly', 'environmentally friendly', 'environment friendly', 'green product',
           'sustainable', 'climate neutral', 'climate-neutral', 'carbon neutral', 'co2 neutral', 'co2-neutral',
           'biodegradable', 'nature friendly', 'planet friendly', 'planet-friendly'],
    'de': ['umweltfreundlich', 'umweltschonend', 'nachhaltig', 'nachhaltige', 'nachhaltiger', 'klimaneutral',
           'klimafreundlich', 'co2-neutral', 'co2 neutral', 'co₂-neutral', 'biologisch abbaubar', 'naturfreundlich',
           'ökologisch', 'ressourcenschonend', 'umweltbewusst'],
}

# absolute safety / material claims: allowed only with proof at hand (info) (rules.md C6)
EVIDENCE = {
    'en': ['non-toxic', 'non toxic', 'harmless', '100% safe', 'completely safe', 'all natural', 'all-natural',
           'compostable', 'hypoallergenic', 'scientifically proven', 'upf 50', 'upf 50+', 'spf 50', '100% natural',
           '100 % natural'],
    'de': ['ungiftig', 'unschädlich', '100 % sicher', '100% sicher', 'völlig unbedenklich', 'rein natürlich',
           'kompostierbar', 'hypoallergen', 'wissenschaftlich bewiesen', 'wissenschaftlich belegt', 'upf 50', 'upf 50+',
           'lsf 50', '100% natürlich', '100 % natürlich', '100% naturrein'],
}

# subjective superlatives in visible text (Amazon: no subjective claims or comparisons; rules.md T7/B8/C4) – warning
SUBJECTIVE = {
    'en': ['the best', 'best in the world', "world's best", "world's smallest", "world's first", "world's lightest",
           "world's strongest", 'in the world', "you'll ever", 'you will ever', 'ever made',
           'unbeatable', 'second to none', 'like no other'],
    'de': ['der beste', 'die beste', 'das beste', 'weltbeste', 'der welt', 'unschlagbar', 'konkurrenzlos',
           'besser als alle', 'einzigartig auf dem markt'],
}

# subjective / temporary words that do not belong in backend search terms
BACKEND_SUBJECTIVE = {
    'en': ['best', 'cheap', 'cheapest', 'amazing', 'awesome', 'perfect', 'great', 'new', 'sale', 'on sale',
           'quality', 'nice', 'cool', 'lovely', '2024', '2025', '2026'],
    'de': ['beste', 'bester', 'bestes', 'günstig', 'billig', 'toll', 'super', 'perfekt', 'neu', 'neue', 'angebot',
           'qualität', 'cool', '2024', '2025', '2026'],
}

PLACEHOLDERS = ['n/a', 'na', 'tbd', 'tba', 'not applicable', 'nicht zutreffend', 'k.a.', 'k. a.', 'lorem ipsum',
                'xxx', 'placeholder', 'platzhalter', 'todo']

LANG_HINTS = {
    'de': {'und', 'für', 'mit', 'der', 'die', 'das', 'ist', 'nicht', 'eine', 'auch', 'damen', 'herren', 'kinder'},
    'en': {'and', 'for', 'with', 'the', 'is', 'not', 'your', 'you', 'women', 'men', 'kids', 'this'},
    'fr': {'et', 'pour', 'avec', 'les', 'des', 'une', 'vous', 'femme', 'homme'},
    'it': {'e', 'per', 'con', 'gli', 'una', 'donna', 'uomo', 'bambini'},
    'es': {'y', 'para', 'con', 'los', 'las', 'una', 'mujer', 'hombre', 'niños'},
}

# score weights per severity and per area cap (points that one area can lose at most)
SEVERITY_POINTS = {'error': 12, 'warning': 5, 'info': 1}
AREA_CAP = {'title': 35, 'bullets': 30, 'backend': 15, 'compliance': 30, 'description': 10, 'keywords': 15,
            'attributes': 20, 'images': 10}

IMAGES_RECOMMENDED = 6     # Amazon shows up to 9 images (main + 8); fewer than 6 leaves conversion on the table

# values of the parentage column that mark a parent (non-buyable) row, per marketplace language
PARENT_VALUES = {'parent', 'eltern', 'übergeordnet', 'parente', 'padre', 'principal', 'parent_sku'}
# words used in the 'Required?' column of an Amazon template's Data Definitions sheet
REQUIRED_WORDS = {'required', 'pflichtfeld', 'erforderlich', 'obligatoire', 'obbligatorio', 'obligatorio', 'verplicht', 'wymagane', 'obligatoriskt'}
EXAMPLE_SKUS = {'abc123'}

# EU marketplaces (marketplace_id in category listing report headers) – EU-only checks (GPSR, textile labelling)
EU_MARKETPLACES = {'A1PA6795UKMFR9': 'DE', 'A13V1IB3VIYZZH': 'FR', 'APJ6JRA9NG5V4': 'IT', 'A1RKKUPIHCS9HS': 'ES',
                   'A1805IZSGTT6HS': 'NL', 'A1C3SOZRARQ6R3': 'PL', 'A2NODRKZP88ZB9': 'SE', 'AMEN7PMS3EDWL': 'BE',
                   'A28R8C7NBKEWEA': 'IE'}
# product types that are textiles: fibre composition must be visible before purchase (Reg. (EU) 1007/2011 Art. 16)
TEXTILE_PRODUCT_TYPES = {'apparel', 'shirt', 'pants', 'dress', 'skirt', 'coat', 'sweater', 'sweatshirt', 'hat',
                         'sweatband', 'hairband', 'headband', 'socks', 'scarf', 'towel', 'blanket', 'bed_linen',
                         'gloves', 'underwear', 'swimwear', 'leggings', 'shorts', 'outerwear', 'pajamas', 'bra',
                         'neck_gaiter', 'cap', 'beanie', 'bath_towel', 'beach_towel'}
# product words that mark a textile when the input has no product type (pasted text, public pages)
TEXTILE_WORDS = {'t-shirt', 'tshirt', 'shirt', 'hemd', 'bluse', 'pullover', 'hoodie', 'sweatshirt', 'jacke', 'hose',
                 'leggings', 'jeans', 'kleid', 'rock', 'socken', 'strümpfe', 'mütze', 'beanie', 'schal', 'loop-schal',
                 'stirnband', 'schweißband', 'handtuch', 'badetuch', 'bettwäsche', 'decke', 'unterwäsche', 'boxershorts',
                 'badeanzug', 'bikini', 'schlafanzug', 'pyjama', 'trikot', 'stutzen', 'dress', 'skirt', 'pants', 'trousers',
                 'sweater', 'jacket', 'socks', 'beanie', 'scarf', 'headband', 'sweatband', 'towel', 'blanket', 'bedding',
                 'underwear', 'swimsuit', 'pajamas', 'hoodie', 'cardigan', 'blouse'}
# fibre words that are not EU names (Reg. (EU) 1007/2011 Annex I) -> the correct name to use
NON_EU_FIBRES = {'bambus': 'Viskose (Bambus)', 'bambusfaser': 'Viskose (Bambus)', 'bamboo': 'viscose (bamboo)',
                 'spandex': 'Elasthan', 'lycra': 'Elasthan (Lycra ist ein Markenname)', 'rayon': 'Viskose'}
BULLET_MAX_SHOWN = 5       # sellers: Amazon shows up to 5 bullets
FIBRES = ['baumwolle', 'polyester', 'elasthan', 'elastan', 'polyamid', 'viskose', 'wolle', 'leinen', 'seide', 'acryl', 'modal',
          'lyocell', 'polypropylen', 'cotton', 'elastane', 'spandex', 'nylon', 'polyamide', 'viscose', 'rayon',
          'wool', 'linen', 'silk', 'acrylic', 'polypropylene', 'coton', 'laine', 'cotone', 'algodón']  # Amazon's example row in category listing reports and templates


# category rules (beauty, electronics, toys, food …) live in references/category_rules.json – data, not code
def load_category_rules():
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "..", "skills", "check", "references", "category_rules.json"),
              os.path.join(here, "..", "references", "category_rules.json")):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {}


CATEGORY_RULES = load_category_rules()
