from utils import db
from utils.rss_format import (
    build_entry_content,
    extract_image_url,
    html_to_plain_text,
    parse_feed_summary,
)


def test_normalize_entry_id_strips_url_query_params():
    raw = (
        "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power"
        "?affiliate_id=171040&filters=45470_0_0_0_0_0_0_0_0"
    )
    assert db.normalize_entry_id(raw) == (
        "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power"
    )


def test_normalize_entry_id_strips_en_prefix():
    raw = "https://www.dmsguild.com/en/product/579088/Blackgate-Blues"
    assert db.normalize_entry_id(raw) == (
        "https://www.dmsguild.com/product/579088/Blackgate-Blues"
    )


def test_stable_entry_id_uses_link_when_id_is_site_root():
    entry = {
        "id": "https://www.legendsofgreyhawk.com/",
        "link": "https://www.legendsofgreyhawk.com/arcana-unleashed-trading/",
        "title": "Arcana Unleashed & Trading",
    }
    assert db.stable_entry_id(entry) == (
        "https://www.legendsofgreyhawk.com/arcana-unleashed-trading/"
    )


def test_stable_entry_id_prefers_product_id_for_dmsguild():
    entry = {
        "id": "https://www.dmsguild.com/product/579088/Blackgate-Blues-FRDCBIRD0101",
        "link": "https://www.dmsguild.com/en/product/579088/Blackgate-Blues?affiliate_id=171040",
        "title": "Blackgate Blues",
    }
    assert db.stable_entry_id(entry) == (
        "https://www.dmsguild.com/product/579088/Blackgate-Blues-FRDCBIRD0101"
    )


def test_stable_entry_id_uses_numeric_id_for_dndbeyond():
    entry = {
        "id": "2215",
        "link": "http://www.dndbeyond.com/posts/2215-d-d-vision-keynote-recap",
        "title": "D&D Vision Keynote Recap",
    }
    assert db.stable_entry_id(entry) == "2215"


def test_normalize_entry_id_keeps_non_url_ids():
    assert db.normalize_entry_id("2201") == "2201"
    assert db.normalize_entry_id("tag:warhorn.net,2002-01-01:/events/x") == (
        "tag:warhorn.net,2002-01-01:/events/x"
    )


def test_normalize_entry_id_truncates_long_values():
    long_id = "x" * 300
    assert len(db.normalize_entry_id(long_id)) == 255


def test_seen_ids_normalize_legacy_db_values():
    legacy = (
        "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power"
        "?affiliate_id=171040&filters=45470_0_0_0_0_0_0_0_0"
    )
    canonical = db.normalize_entry_id(legacy)
    seen = {db.normalize_entry_id(legacy)}
    assert canonical in seen


def test_html_to_plain_text_preserves_paragraph_breaks():
    raw = "<p><b>Publisher</b>: Dungeon Masters Guild</p><p>A desperate summons.</p>"
    text = html_to_plain_text(raw)
    assert "Publisher: Dungeon Masters Guild" in text
    assert "A desperate summons." in text
    assert "Guild" in text and "A desperate" in text
    assert text.find("A desperate") > text.find("Guild")


def test_parse_feed_summary_extracts_publisher_price_and_body():
    raw = """Publisher: Dungeon Masters Guild

A mage trying to join the Red Wizards of Thay has been causing harm in the town of Hearthome.

A Two-Hour Adventure for Tier 1 Characters. Optimized for APL 3.

FR-DC-HEARTHOME-03 Playing With Power
Price: $2.99"""
    parsed = parse_feed_summary(raw, "FR-DC-HEARTHOME-03 Playing With Power")
    assert parsed["publisher"] == "Dungeon Masters Guild"
    assert parsed["price"] == "$2.99"
    assert "Red Wizards of Thay" in parsed["description"]
    assert "FR-DC-HEARTHOME-03 Playing With Power" not in parsed["description"]
    assert "Price:" not in parsed["description"]


def test_build_entry_content_from_dmsguild_like_entry():
    entry = {
        "title": "FR-DC-HEARTHOME-03 Playing With Power",
        "link": "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power?affiliate_id=171040",
        "summary": (
            "<b>Publisher</b>: Dungeon Masters Guild<br>"
            "A mage trying to join the Red Wizards of Thay has been causing harm in the town of Hearthome.<br>"
            "A Two-Hour Adventure for Tier 1 Characters. Optimized for APL 3.<br>"
            "<b>Price</b>: $2.99"
        ),
        "media_thumbnail": [{"url": "https://www.dmsguild.com/image/cache/w900h900/data/cover.jpg"}],
    }
    content = build_entry_content(entry)
    assert content["author"] == "Dungeon Masters Guild"
    assert content["price"] == "$2.99"
    assert "Red Wizards of Thay" in content["description"]
    assert content["image_url"] == "https://www.dmsguild.com/image/cache/w900h900/data/cover.jpg"


def test_extract_image_url_ignores_bare_filenames():
    assert extract_image_url('<img src="551620-thumb140.jpg">') is None
