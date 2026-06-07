def hwc_mixed_003_01(lines):
    """
    Performs the actual file parsing, returning a dict of the config values
    in a given Oracle DB config file.

    Despite their differences, the two filetypes are similar enough to
    allow idential parsing.
    """
    config = {}

    for line in get_active_lines(lines):
        # Check for NULL in line to begin control char removal
        if '\00' in line:
            line = cleanup.sub('', line)
        if '=' in line:
            (key, value) = line.split('=', 1)
            key = key.strip(whitespace + '"\'').lower()
            if ',' in line:
                value = [s.strip(whitespace + '"\'').lower() for s in value.split(',')]
            else:
                value = value.strip(whitespace + '"\'').lower()
            config[key] = value

    return config 

def agc_mixed_003_02(self, axis=None, skipna=None, level=None, numeric_only=None, **kwargs):
        """Computes median across the DataFrame.

        Args:
            axis (int): The axis to take the median on.
            skipna (bool): True to skip NA values, false otherwise.

        Returns:
            The median of the DataFrame. (Pandas series)
        """
        import pandas as pd

        # Set default values matching pandas behavior
        if axis is None:
            axis = 0
        if skipna is None:
            skipna = True
        if numeric_only is None:
            numeric_only = False

        # Delegate to pandas.DataFrame.median
        return pd.DataFrame.median(self, axis=axis, skipna=skipna,
                                   level=level, numeric_only=numeric_only,
                                   **kwargs) 

def agc_mixed_003_03(self):
      """This is where we should also enforce evidence requirements"""
      import numpy as np

      # Ensure the instance has an 'evidence' attribute with required information
      if not hasattr(self, "evidence") or self.evidence is None:
          raise ValueError("Missing required 'evidence' attribute for RNG initialization.")
      if not isinstance(self.evidence, dict):
          raise TypeError("'evidence' must be a dictionary containing RNG parameters.")
      # Expected keys in evidence for RNG configuration
      required_keys = {"seed"}
      missing = required_keys - self.evidence.keys()
      if missing:
          raise ValueError(f"Evidence missing required keys for RNGs: {', '.join(sorted(missing))}")

      # Extract seed (allow None for nondeterministic RNG)
      seed = self.evidence.get("seed")
      # Create the primary RNG; additional RNGs could be added here as needed
      rngs = {"default": np.random.default_rng(seed)}
      return rngs 

def agc_mixed_003_04(self, prefix):
        """
        Return the key that maps to this prefix.
        """
        # (hard coded) If we match a CPR response, return Keys.CPRResponse.
        # (This one doesn't fit in the ANSI_SEQUENCES, because it contains
        # integer variables.)
        if hasattr(self, "_prefix_map"):
            try:
                return self._prefix_map[prefix]
            except KeyError:
                pass

        # Fallback: search through a generic mapping attribute
        mapping = getattr(self, "_map", None) or getattr(self, "mapping", None)
        if mapping is not None:
            for key, val in mapping.items():
                if val == prefix:
                    return key

        # If not found, raise an informative error
        raise KeyError(f"No key found for prefix: {prefix!r}") 

def hwc_mixed_003_05(mean_acceptance_fractions, burn=None, ax=None):
    """
    Plot the meana cceptance fractions for each MCMC step.

    :param mean_acceptance_fractions:
        The acceptance fractions at each MCMC step.

    :type mean_acceptance_fractions:
        :class:`numpy.array`

    :param burn: [optional]
        The burn-in point. If provided, a dashed vertical line will be shown at
        the burn-in point.

    :type burn:
        int

    :param ax: [optional]
        The axes to plot the mean acceptance fractions on.

    :type ax:
        :class:`matplotlib.axes.AxesSubplot`

    :returns:
        The acceptance fractions figure.
    """


    factor = 2.0
    lbdim = 0.2 * factor
    trdim = 0.2 * factor
    whspace = 0.10
    dimy = lbdim + factor + trdim
    dimx = lbdim + factor + trdim

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    lm = lbdim / dimx
    bm = lbdim / dimy
    trm = (lbdim + factor) / dimy
    fig.subplots_adjust(left=lm, bottom=bm, right=trm, top=trm,
        wspace=whspace, hspace=whspace)

    ax.plot(mean_acceptance_fractions, color="k", lw=2)

    if burn is not None:
        ax.axvline(burn, linestyle=":", color="k")

    ax.set_xlim(0, len(mean_acceptance_fractions))

    ax.xaxis.set_major_locator(MaxNLocator(5))
    [l.set_rotation(45) for l in ax.get_xticklabels()]
    ax.yaxis.set_major_locator(MaxNLocator(5))
    [l.set_rotation(45) for l in ax.get_yticklabels()]

    ax.set_xlabel("Step")
    ax.set_ylabel("$\langle{}a_f\\rangle$")
    fig.tight_layout()

    return fig 

def hwc_mixed_003_06 (scheme, assume_local_file=False):
    """Return checker class for given URL scheme. If the scheme
    cannot be matched and assume_local_file is True, assume a local file.
    """
    if scheme in ("http", "https"):
        klass = httpurl.HttpUrl
    elif scheme == "ftp":
        klass = ftpurl.FtpUrl
    elif scheme == "file":
        klass = fileurl.FileUrl
    elif scheme == "telnet":
        klass = telneturl.TelnetUrl
    elif scheme == "mailto":
        klass = mailtourl.MailtoUrl
    elif scheme in ("nntp", "news", "snews"):
        klass = nntpurl.NntpUrl
    elif scheme == "dns":
        klass = dnsurl.DnsUrl
    elif scheme == "itms-services":
        klass = itmsservicesurl.ItmsServicesUrl
    elif scheme and unknownurl.is_unknown_scheme(scheme):
        klass = unknownurl.UnknownUrl
    elif assume_local_file:
        klass = fileurl.FileUrl
    else:
        klass = unknownurl.UnknownUrl
    return klass
