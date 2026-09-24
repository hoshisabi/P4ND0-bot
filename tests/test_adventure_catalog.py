from utils.adventure_catalog import (
    canonical_catalog_name,
    catalog_names_for_product,
    find_matching_name,
    load_prepped_names,
    mark_prepped,
    match_prepped_file,
    normalize,
    parse_catalog,
    resolve_adventure_name,
    suggest_adventures,
)
from utils.wishlist_format import build_wishlist_catalog, match_wishlist_adventure

CATALOG = parse_catalog({
    "adventures": [
        {"n": "Spider Hunt", "c": "PS-DC-PUB-15", "h": "2", "t": 2, "d": "20250101"},
        {"n": "Absent without Leave", "c": "PS-DC-PUB-10", "h": "2", "t": 2, "d": "20240101"},
        {"n": "Fallen for You", "c": "PS-DC-PUB-11", "h": "2", "t": 2, "d": "20240301"},
        {"n": "A Dish Best Served Cold", "c": "DDAL05-05", "h": "2", "t": 2, "d": "20170101"},
        {"n": "Spells on the Loose", "c": "FR-DC-LOOSE-01", "h": "2", "t": 1, "d": "20260801"},
        {"n": "Window to the Past", "c": "DDAL00-01", "h": "4", "t": 1, "d": "20170601"},
        {"n": "Window to the Past (tier 2)", "c": "DDAL00-01", "h": "4", "t": 2, "d": "20170601"},
        {"n": "The Rescue", "c": "CCC-AAA-01", "h": "4", "t": 1, "d": "20180101"},
        {"n": "The Rescue", "c": "CCC-BBB-01", "h": "2", "t": 1, "d": "20190101"},
        {"n": "Peril in Pinebrook", "c": "", "h": "1", "t": 1, "d": "20180101"},
        {"n": "Spider Queen's Lair", "c": "DDAL99-01", "h": "2", "t": 3, "d": "20260101"},
        {"n": "Spider Sanctum", "c": "DDAL99-02", "h": "4", "t": 3, "d": "20260201"},
        {"n": "The Beast", "c": "DDAL04-02", "h": "2", "t": 2, "d": "20160101"},
    ]
})


def test_parse_catalog_names_adventures_like_warhorn():
    names = [entry["name"] for entry in CATALOG]
    assert "PS-DC-PUB-15 Spider Hunt" in names
    assert "Peril in Pinebrook" in names


def test_normalize_ignores_case_punctuation_articles_and_leading_zeros():
    assert normalize("FR-DC-LOOSE-001") == normalize("fr-dc-loose-01")
    assert normalize("dish best served cold") == normalize("A Dish Best Served Cold")
    assert normalize("PS-DC-PUB-1") != normalize("PS-DC-PUB-15")
    assert normalize("Netheril’s Fall") == normalize("netherils fall")
    assert normalize("DDAL4-02") == normalize("DDAL04-02")


def test_canonical_catalog_name_by_code_title_or_name():
    assert canonical_catalog_name("ps-dc-pub-15", CATALOG) == "PS-DC-PUB-15 Spider Hunt"
    assert canonical_catalog_name("spider hunt", CATALOG) == "PS-DC-PUB-15 Spider Hunt"
    assert canonical_catalog_name("dish best served cold", CATALOG) == "DDAL05-05 A Dish Best Served Cold"
    assert canonical_catalog_name("FR-DC-LOOSE-001 Spells on the Loose", CATALOG) == (
        "FR-DC-LOOSE-01 Spells on the Loose"
    )


def test_canonical_catalog_name_refuses_ambiguous_matches():
    assert canonical_catalog_name("DDAL00-01", CATALOG) is None
    assert canonical_catalog_name("The Rescue", CATALOG) is None
    assert canonical_catalog_name("spider", CATALOG) is None


def test_resolve_adventure_name_prefers_catalog_then_known_then_freeform():
    assert resolve_adventure_name("PS-DC-PUB-15", [], CATALOG) == "PS-DC-PUB-15 Spider Hunt"
    assert resolve_adventure_name("ddal00 series", ["DDAL00 Series"], CATALOG) == "DDAL00 Series"
    assert resolve_adventure_name("  Something homebrew ", [], CATALOG) == "Something homebrew"
    assert resolve_adventure_name("PS-DC-PUB-15", [], []) == "PS-DC-PUB-15"


def test_resolve_adventure_name_joins_existing_spelling_of_same_adventure():
    warhorn = "FR-DC-LOOSE-001 Spells on the Loose"
    assert resolve_adventure_name("spells on the loose", [warhorn], CATALOG) == warhorn
    assert resolve_adventure_name("FR-DC-LOOSE-01", [warhorn], CATALOG) == warhorn
    assert resolve_adventure_name("PS-DC-PUB-10", ["PS-DC-PUB-10"], CATALOG) == (
        "PS-DC-PUB-10 Absent without Leave"
    )


def test_find_matching_name_matches_legacy_entries_both_ways():
    legacy = ["PS-DC-PUB-15", "dish best served cold", "Netheril's Fall"]
    assert find_matching_name("PS-DC-PUB-15 Spider Hunt", legacy, CATALOG) == "PS-DC-PUB-15"
    assert find_matching_name("DDAL05-05", legacy, CATALOG) == "dish best served cold"
    assert find_matching_name("netherils fall", legacy, CATALOG) == "Netheril's Fall"
    assert find_matching_name("PS-DC-PUB-10", legacy, CATALOG) is None


def test_suggest_adventures_orders_wishlist_recent_then_catalog():
    suggestions = suggest_adventures(
        "spider",
        wishlist_names=["PS-DC-PUB-15 Spider Hunt"],
        recent=[("PS-DC-PUB-11 Fallen for You", "Sep 2")],
        catalog=CATALOG,
    )

    assert suggestions == [
        ("PS-DC-PUB-15 Spider Hunt (requested)", "PS-DC-PUB-15 Spider Hunt"),
        ("DDAL99-01 Spider Queen's Lair (2h, T3)", "DDAL99-01 Spider Queen's Lair"),
    ]


def test_suggest_adventures_empty_query_skips_catalog_and_matches_token_prefixes():
    empty = suggest_adventures(
        "",
        wishlist_names=["Netheril's Fall"],
        recent=[("PS-DC-PUB-11 Fallen for You", "Sep 2")],
        catalog=CATALOG,
    )
    assert [value for _, value in empty] == ["Netheril's Fall", "PS-DC-PUB-11 Fallen for You"]
    assert empty[1][0] == "PS-DC-PUB-11 Fallen for You (ran Sep 2)"

    by_code = suggest_adventures("pub-1", wishlist_names=[], recent=[], catalog=CATALOG)
    assert [value for _, value in by_code] == [
        "PS-DC-PUB-15 Spider Hunt",
        "PS-DC-PUB-11 Fallen for You",
        "PS-DC-PUB-10 Absent without Leave",
    ]


def test_suggest_adventures_only_offers_two_hour_catalog_entries():
    rescue = suggest_adventures("rescue", wishlist_names=[], recent=[], catalog=CATALOG)
    assert [value for _, value in rescue] == ["CCC-BBB-01 The Rescue"]

    assert suggest_adventures("window", wishlist_names=[], recent=[], catalog=CATALOG) == []
    wishlisted = suggest_adventures(
        "window", wishlist_names=["DDAL00-01 Window to the Past"], recent=[], catalog=CATALOG
    )
    assert [value for _, value in wishlisted] == ["DDAL00-01 Window to the Past"]


def test_suggest_adventures_puts_exact_code_then_prepped_first():
    catalog = parse_catalog({"adventures": [
        {"n": "Spider Queen's Lair", "c": "DDAL99-01", "h": "2", "t": 3, "d": "20260101"},
        {"n": "Spider Hunt", "c": "PS-DC-PUB-15", "h": "2", "t": 2, "d": "20250101"},
        {"n": "Tiny Spider", "c": "DDAL99-03", "h": "2", "t": 1, "d": "20240101"},
    ]})
    mark_prepped(catalog, ["PS-DC-PUB-15 Spider Hunt"])

    spider = suggest_adventures("spider", wishlist_names=[], recent=[], catalog=catalog)
    assert spider == [
        ("PS-DC-PUB-15 Spider Hunt (2h, T2, prepped)", "PS-DC-PUB-15 Spider Hunt"),
        ("DDAL99-01 Spider Queen's Lair (2h, T3)", "DDAL99-01 Spider Queen's Lair"),
        ("DDAL99-03 Tiny Spider (2h, T1)", "DDAL99-03 Tiny Spider"),
    ]
    by_code = suggest_adventures("ddal99-03", wishlist_names=[], recent=[], catalog=catalog)
    assert by_code[0][1] == "DDAL99-03 Tiny Spider"

    partial = suggest_adventures("ddal99-0", wishlist_names=[], recent=[], catalog=catalog)
    assert len(partial) == 2

    exact = suggest_adventures("ps-dc-pub-10", wishlist_names=[], recent=[], catalog=CATALOG)
    assert exact[0][1] == "PS-DC-PUB-10 Absent without Leave"


def test_suggest_adventures_respects_limit_and_label_length():
    long_name = "X" * 150
    suggestions = suggest_adventures(
        "",
        wishlist_names=[long_name] + [f"Adventure {n}" for n in range(30)],
        recent=[],
        catalog=[],
    )
    assert len(suggestions) == 25
    assert len(suggestions[0][0]) == 100
    assert len(suggestions[0][1]) == 100


def test_match_wishlist_adventure_handles_padded_codes_and_word_boundaries():
    wishlist = build_wishlist_catalog([
        {"adventure": "FR-DC-LOOSE-01 Spells on the Loose", "display_name": "Alice"},
        {"adventure": "PS-DC-PUB-1", "display_name": "Bob"},
    ])
    assert match_wishlist_adventure(wishlist, "FR-DC-LOOSE-001 Spells on the Loose") == (
        "FR-DC-LOOSE-01 Spells on the Loose"
    )
    assert match_wishlist_adventure(wishlist, "PS-DC-PUB-15 Spider Hunt") is None


def test_match_prepped_file_handles_file_name_quirks():
    assert match_prepped_file("PS-DC-PUB-15 Spider Hunt", CATALOG) == "PS-DC-PUB-15 Spider Hunt"
    assert match_prepped_file("DDAL4-02 The Beast", CATALOG) == "DDAL04-02 The Beast"
    assert match_prepped_file("PS-DC-PUB-11 Fallen for You (2q)", CATALOG) == "PS-DC-PUB-11 Fallen for You"
    assert match_prepped_file("PS-DC-PUB-10 AWOL", CATALOG) == "PS-DC-PUB-10 Absent without Leave"
    assert match_prepped_file("XX-99 Spider Hunt", CATALOG) == "PS-DC-PUB-15 Spider Hunt"
    assert match_prepped_file("PS-DC-PUB-10 Spider Hunt", CATALOG) is None
    assert match_prepped_file("Liar's Night Wandering Monsters", CATALOG) is None


def test_load_and_mark_prepped(tmp_path):
    path = tmp_path / "prepped.json"
    path.write_text(
        '{"adventures": [{"name": "PS-DC-PUB-15 Spider Hunt", "file": "x.zip", "matched": true},'
        ' {"name": "Not in catalog", "file": "y.zip", "matched": false}]}',
        encoding="utf-8",
    )
    catalog = parse_catalog({"adventures": [
        {"n": "Spider Hunt", "c": "PS-DC-PUB-15", "h": "2", "t": 2},
        {"n": "Fallen for You", "c": "PS-DC-PUB-11", "h": "2", "t": 2},
    ]})

    assert mark_prepped(catalog, load_prepped_names(path)) == 1
    assert [entry["prepped"] for entry in catalog] == [True, False]
    assert load_prepped_names(tmp_path / "missing.json") == []


def test_catalog_names_for_product_expands_bundles():
    catalog = parse_catalog({"adventures": [
        {"i": "545950-01", "n": "Burl Trouble", "c": "FR-DC-UCON25-01", "h": "1"},
        {"i": "545950-02", "n": "Oily Conundrum", "c": "FR-DC-UCON25-02", "h": "1"},
        {"i": "5459500", "n": "Unrelated", "c": "XX-01", "h": "2"},
        {"i": "400000", "n": "Solo", "c": "XX-02", "h": "2"},
    ]})
    assert catalog_names_for_product("545950", catalog) == [
        "FR-DC-UCON25-01 Burl Trouble",
        "FR-DC-UCON25-02 Oily Conundrum",
    ]
    assert catalog_names_for_product("400000", catalog) == ["XX-02 Solo"]
    assert catalog_names_for_product("999", catalog) == []
