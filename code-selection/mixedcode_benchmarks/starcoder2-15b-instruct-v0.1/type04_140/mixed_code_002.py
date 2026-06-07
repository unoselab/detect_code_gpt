def hwc_mixed_002_01(self):
        """
        Compute each asset's weight in the portfolio by calculating its held
        value divided by the total value of all positions.

        Each equity's value is its price times the number of shares held. Each
        futures contract's value is its unit price times number of shares held
        times the multiplier.
        """
        position_values = pd.Series({
            asset: (
                    position.last_sale_price *
                    position.amount *
                    asset.price_multiplier
            )
            for asset, position in self.positions.items()
        })
        return position_values / self.portfolio_value 

def agc_mixed_002_02(allow_self=False):
    """A decorator that doesn't allow for positional arguments.

    :param bool allow_self:
        Whether to allow ``self`` as a positional argument.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if allow_self and len(args) > 1:
                raise TypeError(f"{func.__name__}() does not allow for positional arguments")
            elif not allow_self and len(args) > 0:
                raise TypeError(f"{func.__name__}() does not allow for positional arguments")
            return func(*args, **kwargs)
        return wrapper
    return decorator 

def agc_mixed_002_03(self, Xt, y):
        """ takes time series data, and splits each series into temporal folds """
        n_samples, n_features = Xt.shape
        n_splits = self.n_splits
        fold_size = n_samples // n_splits
        folds_X = []
        folds_y = []
        for i in range(n_splits):
            fold_X = Xt[i * fold_size:(i + 1) * fold_size, :]
            fold_y = y[i * fold_size:(i + 1) * fold_size]
            folds_X.append(fold_X)
            folds_y.append(fold_y)
        return folds_X, folds_y 

def agc_mixed_002_04(runner_list, extra_tick, use_poll):
    """
    :return True - success; False - extra_tick failure; runner object - the runner who tick failure
    """
    for runner in runner_list:
        if use_poll:
            if not runner.poll():
                return runner
        else:
            if not runner.tick():
                return runner
    if not extra_tick:
        return False
    for runner in runner_list:
        if not runner.extra_tick():
            return runner
    return True 

def hwc_mixed_002_05(cls, data, key=None):
        """
        Parse a set of data to extract entity-only data.

        Use classmethod `parse` if available, otherwise use the `endpoint`
        class variable to extract data from a data blob.
        """
        parse = cls.parse if cls.parse is not None else cls.get_endpoint()

        if callable(parse):
            data = parse(data)
        elif isinstance(parse, str):
            data = data[key]
        else:
            raise Exception('"parse" should be a callable or string got, {0}'
                            .format(parse))
        return data 

def hwc_mixed_002_06(args):
    """
    %prog frg frgfile

    Extract FASTA sequences from frg reads.
    """
    p = OptionParser(frg.__doc__)
    opts, args = p.parse_args(args)

    if len(args) != 1:
        sys.exit(p.print_help())

    frgfile, = args
    fastafile = frgfile.rsplit(".", 1)[0] + ".fasta"
    fp = open(frgfile)
    fw = open(fastafile, "w")

    for rec in iter_records(fp):
        if rec.type != "FRG":
            continue
        id = rec.get_field("acc")
        seq = rec.get_field("seq")
        s = SeqRecord(Seq(seq), id=id, description="")
        SeqIO.write([s], fw, "fasta")

    fw.close()
