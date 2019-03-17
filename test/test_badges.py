import os
import sqlite3
import tempfile

import pytest
from ..badge_deamon import (regid_known, clean_tex, parse_text,
                            DeamonTableException, check_input_table,
                            setup_config_env,
                            prepare_badge_email,
                            process_new_messages,
                            parse_message)

def test_check_regid():
    '''Test if the regid check works.'''
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badges (regid real)''')
        c.executemany('INSERT INTO badges VALUES (?)', [(34,), (34,), (125,)])
        conn.commit()

        assert regid_known(c, 125)
        assert not regid_known(c, 5)
        assert not regid_known(c, 34)


def test_clean_tex():
    # test OK
    clean, warn = clean_tex(r'G\"{u}nther', {'settings': {'max_tex_len': 15}})
    assert clean == r'G\"{u}nther'
    assert warn == ''

    # too long
    clean, warn = clean_tex(r'G\"{u}nther', {'settings': {'max_tex_len': 2}})
    assert clean is None
    assert 'each field can only contain 2 characters' in warn

    # forbidden command
    clean, warn = clean_tex(r'\def', {'settings': {'max_tex_len': 20}})
    assert clean is None
    assert 'LaTeX command def is disable' in warn

    # forbidden AND too long
    clean, warn = clean_tex(r'\def', {'settings': {'max_tex_len': 2}})
    assert clean is None
    assert 'LaTeX command def is disable' in warn


def test_parse_text():
    text='''
aa: 123
aa: 234
bb: asdf
cc asdü
'''
    regs = {'email parsing':
            {'a': r'aa:\s(?P<aa>[\d]+)',  # numbers, top line should be found
             'c': r'cc\s(?P<cc>[\s\S]+)', # with non-ascii character
             'd': r'dd:\s(?P<dd>[\d]+)'}, # not present
            'settings': {'max_tex_len': 15},
    }
    out, warn = parse_text(text.splitlines(), regs)
    assert out == {'aa': '123', 'cc': 'asdü'}
    assert warn == ''

    # One value is too long, the other one should still be present
    text='''
aa: 12345678901234567
aa: 234
bb: asdf
cc asdü
'''
    out, warn = parse_text(text.splitlines(), regs)
    assert out == {'cc': 'asdü'}
    assert 'each field can only contain 15 characters' in warn


def test_check_table_wrong_name():
    '''Test if automated chack catches most common mistakes'''
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badasr (regid real)''')
        conn.commit()

        with pytest.raises(DeamonTableException) as e:
            check_input_table(c, {})

        assert 'Table "badges" does not exist' in str(e)


def test_check_table_missing_cols():
    '''Test if automated chack catches most common mistakes'''
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badges (regid real)''')
        conn.commit()

        with pytest.raises(DeamonTableException) as e:
            check_input_table(c, {})

        assert 'are required in table "badges" but' in str(e)

def test_check_table_regex_does_not_match_colname():
    '''Test if automated chack catches most common mistakes'''
    config = {'email parsing': {'a': r'aa:\s(?P<aa>[\d]+)'}}
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badges (regid real, email text, image1 text, image2 text, bb text)''')
        conn.commit()
        with pytest.raises(DeamonTableException) as e:
            check_input_table(c, config)

        assert 'defines the groups' in str(e)


def test_check_table_all_OK():
    '''Test if automated chack catches most common mistakes'''
    config = {'email parsing': {'a': r'aa:\s(?P<aa>[\d]+)'}}
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badges (regid real, email text, image1 text, image2 text, aa text, notused real)''')
        conn.commit()

        check_input_table(c, config)


def test_generate_and_parse_email():
    with sqlite3.connect(':memory:') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE badges (regid real, email text, image1 text, image2 text, name text, notused real)''')
        c.execute("INSERT INTO badges VALUES (123, 'test@example.com', 'img1.png', 'img2.png', 'Hans Musterman', 45.678)")
        conn.commit()

        config, env = setup_config_env('test/test_config.cfg')
        msg = prepare_badge_email(c, 123, config, env, warntext='warnwarnwarn')

        # This message now has the data from above
        # We'll now change the database
        c.execute('UPDATE badges SET name="noname" WHERE regid=123')
        conn.commit()

        # Then we parse the message
        # and that should reset the database values to the previous ones
        with tempfile.TemporaryDirectory() as temp:
            config['path']['image_dir'] = temp
            warntext = parse_message(conn, c, '123', msg, config)
            # Check images contained in mail (in this case: a rendered badge)
            # is written to speciffied file
            assert os.path.isfile(os.path.join(temp, '123_front.pdf'))
        c.execute("SELECT name FROM badges WHERE regid=123")
        assert c.fetchone()[0].strip() == 'Hans Musterman'
        c.execute("SELECT image1 FROM badges WHERE regid=123")
        assert c.fetchone()[0] == '123_front.pdf'
        c.execute("SELECT image2 FROM badges WHERE regid=123")
        assert c.fetchone()[0] == '123_front.pdf'

        assert warntext == ' '
