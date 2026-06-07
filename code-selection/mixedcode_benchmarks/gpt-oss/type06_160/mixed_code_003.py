def agc_mixed_003_01(self, infile):
        """Return a cdf handle created by the available cdf library.
        python-netcdf4 and scipy supported (default:scipy)"""
        try:
            import netCDF4 as nc
            return nc.Dataset(infile, mode='r')
        except ImportError:
            pass
        try:
            from scipy.io import netcdf_file
            return netcdf_file(infile, mode='r')
        except ImportError as e:
            raise ImportError(
                "No supported CDF library found (netCDF4 or scipy.io)."
            ) from e 

def hwc_mixed_003_02(config, args):
    """
    Get the API base url. Try Terraform state first, then
    :py:class:`~.AWSInfo`.

    :param config: configuration
    :type config: :py:class:`~.Config`
    :param args: command line arguments
    :type args: :py:class:`argparse.Namespace`
    :return: API base URL
    :rtype: str
    """
    try:
        logger.debug('Trying to get Terraform base_url output')
        runner = TerraformRunner(config, args.tf_path)
        outputs = runner._get_outputs()
        base_url = outputs['base_url']
        logger.debug("Terraform base_url output: '%s'", base_url)
    except Exception:
        logger.info('Unable to find API base_url from Terraform state; '
                    'querying AWS.', exc_info=1)
        aws = AWSInfo(config)
        base_url = aws.get_api_base_url()
        logger.debug("AWS api_base_url: '%s'", base_url)
    if not base_url.endswith('/'):
        base_url += '/'
    return base_url 

def agc_mixed_003_03(self, url=None):
        """
        gets the referer url for the token handler
        """
        import urllib.parse

        if url:
            return url

        req = getattr(self, "request", None)
        if not req:
            return None

        referer = req.headers.get("Referer")
        if not referer:
            return None

        parsed = urllib.parse.urlparse(referer)
        if not parsed.scheme:
            base = getattr(req, "host_url", "")
            referer = urllib.parse.urljoin(base, referer)

        return referer 

def hwc_mixed_003_04(cwd, rev='tip', user=None):
    """
    Mimic git describe and return an identifier for the given revision

    cwd
        The path to the Mercurial repository

    rev: tip
        The path to the archive tarball

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' hg.describe /path/to/repo
    """
    cmd = [
            'hg',
            'log',
            '-r',
            '{0}'.format(rev),
            '--template',
            "'{{latesttag}}-{{latesttagdistance}}-{{node|short}}'"
            ]
    desc = __salt__['cmd.run_stdout'](
            cmd,
            cwd=cwd,
            runas=user,
            python_shell=False)

    return desc or revision(cwd, rev, short=True) 

def hwc_mixed_003_05(self, path):
        """Test a bunch of files and return a summary JSON report"""

        SEPARATOR = '=' * 40
        summary = {}
        res = True

        for _f in utils.get_files_by_path(path):
            L.info(SEPARATOR)
            status, summ = self._check_file(_f)
            res &= status
            if summ is not None:
                summary.update(summ)

        L.info(SEPARATOR)

        status = 'PASS' if res else 'FAIL'

        return {'files': summary, 'STATUS': status} 

def agc_mixed_003_06(self, master):
        """Add a standard button box.

        Override if you do not want the standard buttons
        """

        import tkinter as tk

        btn_frame = tk.Frame(master)
        btn_frame.pack(fill="x", side="bottom", pady=5)

        def _add(name):
            cmd = getattr(self, name.lower(), None)
            if not callable(cmd):
                cmd = lambda: None
            btn = tk.Button(btn_frame, text=name, command=cmd)
            btn.pack(side="right", padx=5)
            return btn

        _add("OK")
        _add("Cancel")
        return btn_frame
