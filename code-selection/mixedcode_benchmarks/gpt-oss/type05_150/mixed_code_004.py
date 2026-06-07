def agc_mixed_004_01(profile='pagerduty', subdomain=None, api_key=None):
    """
    List services belonging to this account

    CLI Example:

        salt myminion pagerduty.get_services
    """

    import requests

    if profile != "pagerduty":
        raise NotImplementedError(f"Profile '{profile}' is not supported")
    if not subdomain:
        raise ValueError("subdomain must be provided for PagerDuty API")
    if not api_key:
        raise ValueError("api_key must be provided for PagerDuty API")

    url = f"https://{subdomain}.pagerduty.com/api/v1/services"
    try:
        resp = requests.get(url, params={"api_key": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("services", [])
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to retrieve services from PagerDuty: {exc}") 

def hwc_mixed_004_02(cmd, check_stderr=True, stdout=None, stderr=None):
    """
    Alias to run with check return code and stderr
    """
    code, out, err = run(cmd)

    # Because we're raising error, sometimes we want to process stdout/stderr after catching error
    # so we're copying these outputs if required
    if stdout is not None:
        stdout[:] = out
    if stderr is not None:
        stderr[:] = err

    if code != 0:
        for l in out:
            print(l)
    assert code == 0, 'Return: {} {}\nStderr: {}'.format(code, cmd, err)
    if check_stderr:
        assert err == [], 'Error: {} {}'.format(err, code)
    return code, out, err 

def agc_mixed_004_03(self, stmt: Statement, sctx: SchemaContext) -> None:
        """Handle identity statement."""
        if not hasattr(sctx, "identities"):
            sctx.identities = {}
        # Build a minimal representation of the identity statement
        identity_info = {
            "stmt": stmt,
            "description": getattr(stmt, "description", None),
            "reference": getattr(stmt, "reference", None),
            "if_features": getattr(stmt, "if_features", []),
        }
        # Store the identity using its argument (name) as the key
        sctx.identities[stmt.arg] = identity_info 

def hwc_mixed_004_04(
        self,
        filename: Optional[str] = None,
        show_link: bool = True,
        auto_open: bool = True,
        detect_notebook: bool = True,
    ) -> None:
        """Display the chart.

        Parameters
        ----------
        filename : str, optional
            Save plot to this filename, otherwise it's saved to a temporary file.
        show_link : bool, optional
            Show link to plotly.
        auto_open : bool, optional
            Automatically open the plot (in the browser).
        detect_notebook : bool, optional
            Try to detect if we're running in a notebook.

        """
        kargs = {}
        if detect_notebook and _detect_notebook():
            py.init_notebook_mode()
            plot = py.iplot
        else:
            plot = py.plot
            if filename is None:
                filename = NamedTemporaryFile(prefix='plotly', suffix='.html', delete=False).name
            kargs['filename'] = filename
            kargs['auto_open'] = auto_open

        plot(self, show_link=show_link, **kargs) 

def agc_mixed_004_05(self, query):
        """
        Translates the query for possible aliases
        """
        if not query:
            return query
        alias_map = getattr(self, "aliases", {})
        result_tokens = []
        for token in query.split():
            if token in alias_map:
                result_tokens.append(alias_map[token])
            else:
                low = token.lower()
                result_tokens.append(alias_map.get(low, token))
        return " ".join(result_tokens) 

def hwc_mixed_004_06(args):
    """
    %prog links url

    Extract all the links "<a href=''>" from web page.
    """
    p = OptionParser(links.__doc__)
    p.add_option("--img", default=False, action="store_true",
                 help="Extract <img> tags [default: %default]")
    opts, args = p.parse_args(args)

    if len(args) != 1:
        sys.exit(not p.print_help())

    url, = args
    img = opts.img

    htmlfile = download(url)
    page = open(htmlfile).read()
    soup = BeautifulSoup(page)

    tag = 'img' if img else 'a'
    src = 'src' if img else 'href'
    aa = soup.findAll(tag)
    for a in aa:
        link = a.get(src)
        link = urljoin(url, link)
        print(link)
