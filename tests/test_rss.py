from utils import db


def test_normalize_entry_id_strips_url_query_params():
    raw = (
        "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power"
        "?affiliate_id=171040&filters=45470_0_0_0_0_0_0_0_0"
    )
    assert db.normalize_entry_id(raw) == (
        "https://www.dmsguild.com/product/573916/FRDCHEARTHOME03-Playing-With-Power"
    )


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
