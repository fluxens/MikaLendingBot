import pytest
import tempfile
import collections
from six import iteritems
from decimal import Decimal

# Hack to get relative imports - probably need to fix the dir structure instead but we need this at the minute for
# pytest to work
import os, sys, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)


# Check two unsorted lists are equal without removing duplicates (like set would)
def compare_lists(x, y):
    return collections.Counter(x) == collections.Counter(y)


def add_to_env(category, option, value):
    os.environ['{0}_{1}'.format(category, option)] = value


def rm_from_env(category, option):
    os.environ.pop('{0}_{1}'.format(category, option))


def write_to_cfg(filename, category, val_dict):
    with open(filename, 'a') as out_file:
        out_file.write('\n')
        out_file.write('[{0}]\n'.format(category))
        for option, value in iteritems(val_dict):
            out_file.write('{0} = {1}\n'.format(option, value))


def write_skeleton_exchange(filename, exchange, all_currencies=['AAA', 'BBB', 'CCC', 'DDD', 'EEE']):
    all_currencies = f"{', '.join(all_currencies)}"
    write_to_cfg(filename, 'API', {'exchange': exchange})
    # Test 'coins' we can use later in testing
    write_to_cfg(filename, exchange.upper(), {'all_currencies': all_currencies})


def write_coin_cfg(filename,
                   coin='AAA',
                   minloansize=0.01,
                   mindailyrate=0.18,
                   maxactiveamount=1,
                   maxtolend=0,
                   maxpercenttolend=0,
                   maxtolendrate=0,):
    cfg = {'minloansize': minloansize,
           'mindailyrate': mindailyrate,
           'maxactiveamount': maxactiveamount,
           'maxtolend': maxtolend,
           'maxpercenttolend': maxpercenttolend,
           'maxtolendrate': maxtolendrate}
    write_to_cfg(filename, coin, cfg)


@pytest.fixture(autouse=True)
# This just adds and removes environment variables
def env_vars():
    var_set_1 = "ENVVAR,BOOL_T,true"
    var_set_2 = "ENVVAR,BOOL_F,false"
    var_set_3 = "ENVVAR,NUM,60"
    var_list = [var_set_1, var_set_2, var_set_3]
    for var_set in var_list:
        c, o, v = var_set.split(',')
        add_to_env(c, o, v)
    yield var_list  # Teardown after yield
    for var_set in var_list:
        c, o, v = var_set.split(',')
        rm_from_env(c, o)


@pytest.fixture()
def config():
    import modules.Configuration as Config
    # The CFG section isn't actually used for the bot in real life, it's just to make it easier to test
    cfg = {"BOOL_T": "true",
           "BOOL_F": "false",
           "NUM": "60"}
    f = tempfile.NamedTemporaryFile(delete=False)
    Config.filename = f.name
    write_to_cfg(Config.filename, 'CFG', cfg)
    Config.init(Config.filename)
    yield Config  # Teardown after yield
    del Config
    os.remove(f.name)


class TestClass(object):
    def test_has_option(self, config):
        assert(not config.has_option('fail', 'fail'))
        assert(config.has_option('ENVVAR', 'BOOL_T'))
        assert(config.has_option('CFG', 'BOOL_T'))

    def test_getboolean(self, config):
        assert(not config.getboolean('fail', 'fail'))
        assert(config.getboolean('ENVVAR', 'BOOL_T'))
        assert(config.getboolean('ENVVAR', 'BOOL_F') is False)
        assert(config.getboolean('CFG', 'BOOL_T'))
        assert(config.getboolean('CFG', 'BOOL_F') is False)
        with pytest.raises(ValueError):
            config.getboolean('ENVVAR', 'NUM')
            config.getboolean('CFG', 'NUM')
        assert(config.getboolean('some', 'default', True))
        assert(config.getboolean('some', 'default') is False)

    def test_get(self, config):
        assert(config.get('ENVVAR', 'NUM') == '60')
        assert(config.get('ENVVAR', 'NUM', False, 61) == 61)
        assert(config.get('ENVVAR', 'NUM', False, 1, 59) == 59)
        assert(config.get('ENVVAR', 'NO_NUM', 100) == 100)
        with pytest.raises(SystemExit):
            assert(config.get('ENVVAR', 'NO_NUM', None))

    def test_get_exchange_poloniex(self, config):
        write_skeleton_exchange(config.filename, 'Poloniex')
        config.init(config.filename)
        assert(config.get_exchange() == 'POLONIEX')

    def test_get_exchange_bitfinex(self, config):
        write_skeleton_exchange(config.filename, 'Bitfinex')
        config.init(config.filename)
        assert(config.get_exchange() == 'BITFINEX')

    def test_get_coin_cfg_new(self, config):
        write_skeleton_exchange(config.filename, 'Bitfinex')
        write_coin_cfg(config.filename)
        config.init(config.filename)
        result = {'AAA': {'minrate': Decimal('0.0018'), 'maxactive': Decimal('1'), 'maxtolend': Decimal('0'),
                          'maxpercenttolend': Decimal('0'), 'maxtolendrate': Decimal('0'), 'gapmode': False,
                          'gapbottom': Decimal('0'), 'gaptop': Decimal('0'), 'frrasmin': False, 'frrdelta': Decimal('0')}}
        assert(config.get_coin_cfg() == result)

    # This breaks the tests following it, I'm not sure why, looks like it messes up the config object and it can't
    # recover - laxdog
    # def test_get_coin_cfg_old(self, config):
    #     write_to_cfg(config.filename, 'BOT', {'coinconfig':  '["BTC:0.18:1:0:0:0","DASH:0.6:1:0:0:0"]'})
    #     with pytest.raises(SystemExit) as pytest_wrapped_e:
    #         config.init(config.filename)
    #     assert pytest_wrapped_e.type == SystemExit
    #     assert pytest_wrapped_e.value.code == 1

    def test_get_min_loan_sizes(self, config):
        write_skeleton_exchange(config.filename, 'Bitfinex')
        write_coin_cfg(config.filename, coin='AAA', minloansize=1)
        write_coin_cfg(config.filename, coin='BBB', minloansize=0)
        write_coin_cfg(config.filename, coin='CCC', minloansize=-9)
        write_coin_cfg(config.filename, coin='DDD', minloansize="a")
        config.init(config.filename)
        assert config.get_min_loan_sizes()['AAA'] == 1
        assert config.get_min_loan_sizes()['BBB'] == 0.01
        assert config.get_min_loan_sizes()['CCC'] == 0.01
        # This test will need update when the 'default value' fix in Configuration.py is done
        assert config.get_min_loan_sizes()['DDD'] == 0

    def test_get_currencies_list(self, config):
        alpha = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE']
        write_skeleton_exchange(config.filename, 'Bitfinex', all_currencies=alpha)
        write_to_cfg(config.filename, 'BOT', {'transferableCurrencies': ', '.join(alpha[0:2])})
        write_to_cfg(config.filename, 'MarketAnalysis', {'analyseCurrencies': ', '.join(alpha[2:4])})
        config.init(config.filename)
        assert compare_lists(config.get_currencies_list('all_currencies', section='BITFINEX'), alpha)
        assert compare_lists(config.get_currencies_list('analyseCurrencies', 'MarketAnalysis'), alpha[2:4])