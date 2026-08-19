def agc_mixed_002_01(self, timeout=None):
        """
        Blocking wait for task status.
        """
        import time

        start_time = time.time()
        while not self.done():
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    break
                time.sleep(0.1)
            else:
                time.sleep(0.1)
        return self.result() if self.done() else None 

def agc_mixed_002_02(source, texinputs=[], builder=None):
    """Builds a LaTeX source to PDF.

    Will automatically instantiate an available builder (or raise a
    :class:`exceptions.RuntimeError` if none are available) and build the
    supplied source with it.

    Parameters are passed on to the builder's
    :meth:`~latex.build.LatexBuilder.build_pdf` function.

    :param builder: Specify which builder should be used - ``latexmk``,
                    ``pdflatex`` or ``xelatexmk``.
    """
    from sphinx.util.latex import LatexBuilder
    if builder is None:
        for b in ['latexmk', 'pdflatex', 'xelatexmk']:
            try:
                builder = LatexBuilder(b)
                break
            except Exception:
                continue
        if builder is None:
            from sphinx.errors import RuntimeError
            raise RuntimeError("No available LaTeX builder found.")
    elif isinstance(builder, str):
        builder = LatexBuilder(builder)

    return builder.build_pdf(source, texinputs=texinputs) 

def agc_mixed_002_03(n):
    """Print the position string equivalent of a positive integer. Examples:

        0: zeroeth
        1: first
        2: second
        14: 14th
        21: 21st
    """
    if n == 0:
        return "zeroeth"
    if n == 1:
        return "first"
    if n == 2:
        return "second"
    if n == 3:
        return "third"

    last_digit = n % 10
    last_two = n % 100

    if 11 <= last_two <= 13:
        suffix = "th"
    elif last_digit == 1:
        suffix = "st"
    elif last_digit == 2:
        suffix = "nd"
    elif last_digit == 3:
        suffix = "rd"
    else:
        suffix = "th"

    return f"{n}{suffix}" 

def hwc_mixed_002_04(env, identifier):
    """List server credentials."""

    manager = SoftLayer.HardwareManager(env.client)
    hardware_id = helpers.resolve_id(manager.resolve_ids,
                                     identifier,
                                     'hardware')
    instance = manager.get_hardware(hardware_id)

    table = formatting.Table(['username', 'password'])
    for item in instance['softwareComponents']:
        if 'passwords' not in item:
            raise exceptions.SoftLayerError("No passwords found in softwareComponents")
        for credentials in item['passwords']:
            table.add_row([credentials.get('username', 'None'), credentials.get('password', 'None')])
    env.fout(table) 

def hwc_mixed_002_05(poscar_string, transformations=None):
        """
        Generates TransformedStructure from a poscar string.

        Args:
            poscar_string (str): Input POSCAR string.
            transformations ([Transformations]): Sequence of transformations
                to be applied to the input structure.
        """
        p = Poscar.from_string(poscar_string)
        if not p.true_names:
            raise ValueError("Transformation can be craeted only from POSCAR "
                             "strings with proper VASP5 element symbols.")
        raw_string = re.sub(r"'", "\"", poscar_string)
        s = p.structure
        source_info = {"source": "POSCAR",
                       "datetime": str(datetime.datetime.now()),
                       "original_file": raw_string}
        return TransformedStructure(s, transformations, history=[source_info]) 

def hwc_mixed_002_06(self, alias, certFile):
        """
        This operation imports a certificate authority (CA) signed SSL
        certificate into the key store.
        """
        params = { "f" : "json" }
        files = {"file" : certFile}
        url = self._url + \
            "/sslCertificates/{cert}/importSignedCertificate".format(cert=alias)
        return self._post(url=url,
                          files=files,
                          param_dict=params,
                          proxy_port=self._proxy_port,
                          proxy_url=self._proxy_url)
