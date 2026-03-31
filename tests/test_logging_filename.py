from serialhub.app import sanitize_log_filename


def test_sanitize_log_filename() -> None:
    assert sanitize_log_filename('session') == 'session.txt'
    assert sanitize_log_filename('session.txt') == 'session.txt'
    assert sanitize_log_filename('bad<>:"/\\|?*name') == 'bad_name.txt'
    assert sanitize_log_filename('   .  ') == 'serialhub-log.txt'
