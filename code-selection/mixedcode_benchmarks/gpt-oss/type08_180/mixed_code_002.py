def hwc_mixed_002_01(cls, starA='starA', force_build=False):
        """
        For convenience, this function is available at the top-level as
        <phoebe.default_star> as well as <phoebe.frontend.bundle.Bundle.default_star>.

        sun

        This is a constructor, so should be called as:

        >>> b = Bundle.default_binary()

        Arguments
        -----------
        * `starA` (string, optional, default='starA'): the label to be set for
            starA.
        * `force_build` (bool, optional, default=False): whether to force building
            the bundle from scratch.  If False, pre-cached files will be loaded
            whenever possible to save time.

        Returns
        -----------
        * an instantiated <phoebe.frontend.bundle.Bundle> object.
        """
        if not force_build and not conf.devel:
            b = cls.open(os.path.join(_bundle_cache_dir, 'default_star.bundle'))

            if starA != 'starA':
                b.rename_component('starA', starA)

            return b

        b = cls()
        # IMPORTANT NOTE: if changing any of the defaults for a new release,
        # make sure to update the cached files (see frontend/default_bundles
        # directory for script to update all cached bundles)
        b.add_star(component=starA)
        b.set_hierarchy(_hierarchy.component(b[starA]))
        b.add_compute(distortion_method='rotstar', irrad_method='none')
        return b 

def agc_mixed_002_02(self):
        """ Load your configuration settings from a file """
        import json
        import os

        # Determine the configuration file path
        path = getattr(self, "config_path", None) or getattr(self, "config_file", None) or "config.json"

        if not os.path.isfile(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            try:
                cfg = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in configuration file {path}: {e}") from e

        self.config = cfg
        return cfg 

def agc_mixed_002_03(text, lexer_name='python', **kwargs):
    r"""
    SeeAlso:
        color_text
    """
    # Resolve extensions to languages
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, TextLexer
    from pygments.formatters import TerminalFormatter, HtmlFormatter

    # Resolve lexer
    lexer_opts = kwargs.pop('lexer_options', {})
    try:
        lexer = get_lexer_by_name(lexer_name, **lexer_opts)
    except Exception:
        lexer = TextLexer()

    # Resolve formatter
    fmt = kwargs.pop('formatter', None)
    fmt_opts = kwargs.pop('formatter_options', {})
    if fmt is None:
        fmt = TerminalFormatter(**fmt_opts)
    elif isinstance(fmt, str):
        if fmt.lower() == 'html':
            fmt = HtmlFormatter(**fmt_opts)
        else:
            fmt = TerminalFormatter(**fmt_opts)
    # If a formatter instance is supplied, use it directly (ignore fmt_opts)

    return highlight(text, lexer, fmt) 

def agc_mixed_002_04(self):
        """
        Check to see if this packet must be retransmitted until it was
        received.

        Packets which contain a connection-state changing flag (SYN or FIN) or
        a non-zero amount of data can be retransmitted.
        """
        syn_flag = getattr(self, 'syn', False)
        fin_flag = getattr(self, 'fin', False)

        # Determine if packet carries any payload data
        data = getattr(self, 'data', None)
        has_data = False
        if data is not None:
            try:
                has_data = len(data) > 0
            except Exception:
                # If data is not sized (e.g., a stream), treat as having data
                has_data = bool(data)

        return bool(syn_flag or fin_flag or has_data) 

def hwc_mixed_002_05(self):
        """Return value of text. Return False if text is invalid, raise exception if text is intermediate"""
        strn = self.lineEdit().text()
        suf = self.opts['suffix']
        if len(suf) > 0:
            if strn[-len(suf):] != suf:
                return False
            #raise Exception("Units are invalid.")
            strn = strn[:-len(suf)]
        try:
            val = fn.siEval(strn)
        except:
            #sys.excepthook(*sys.exc_info())
            #print "invalid"
            return False
        #print val
        return val 

def hwc_mixed_002_06(data, sample_rate, signal=False, in_seconds=False, out_seconds=False):
    """
    Function for generation of ECG Tachogram.

    ----------
    Parameters
    ----------
    data : list
        ECG signal or R peak list. When the input is a raw signal the input flag signal should be
        True.

    sample_rate : int
        Sampling frequency.

    signal : boolean
        If True, then the data argument contains the set of the ECG acquired samples.

    in_seconds : boolean
        If the R peaks list defined as the input argument "data" contains the sample numbers where
        the R peaks occur, then in_seconds needs to be False.

    out_seconds : boolean
        If True then each sample of the returned time axis is expressed in seconds.

    Returns
    -------
    out : list, list
        List of tachogram samples. List of instants where each cardiac cycle ends.

    """

    if signal is False:  # data is a list of R peaks position.
        data_copy = data
        time_axis = numpy.array(data)#.cumsum()
        if out_seconds is True and in_seconds is False:
            time_axis = time_axis / sample_rate
    else:  # data is a ECG signal.
        # Detection of R peaks.
        data_copy = detect_r_peaks(data, sample_rate, time_units=out_seconds, volts=False,
                                   resolution=None, plot_result=False)[0]
        time_axis = data_copy

    # Generation of Tachogram.
    tachogram_data = numpy.diff(time_axis)
    tachogram_time = time_axis[1:]

    return tachogram_data, tachogram_time
