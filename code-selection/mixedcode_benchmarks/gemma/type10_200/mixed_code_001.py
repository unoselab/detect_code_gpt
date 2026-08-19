def agc_mixed_001_01(self, x, y, center_x = 0, center_y = 0, **kwargs):

        """
        returns df/dx and df/dy (un-normalized!!!) interpolated from the numerical deflection table
        """

        dx = x - center_x
        dy = y - center_y

        # Assuming self.deflection_table is a 2D array and self.spacing is the grid step
        # Using central difference for numerical derivatives
        h = self.spacing

        # Interpolate values at offset positions
        # This assumes a helper method self.interpolate(x, y) exists
        f_px = self.interpolate(x + h, y)
        f_mx = self.interpolate(x - h, y)
        f_py = self.interpolate(x, y + h)
        f_my = self.interpolate(x, y - h)

        dfdx = (f_px - f_mx) / (2 * h)
        dfdy = (f_py - f_my) / (2 * h)

        return dfdx, dfdy 

def hwc_mixed_001_02(filename, entities=None, config=None,
                        include_unmatched=False):
    """ Parse the passed filename for entity/value pairs.

    Args:
        filename (str): The filename to parse for entity values
        entities (list): An optional list of Entity instances to use in
            extraction. If passed, the config argument is ignored.
        config (str, Config, list): One or more Config objects or names of
            configurations to use in matching. Each element must be a Config
            object, or a valid Config name (e.g., 'bids' or 'derivatives').
            If None, all available configs are used.
        include_unmatched (bool): If True, unmatched entities are included
            in the returned dict, with values set to None. If False
            (default), unmatched entities are ignored.

    Returns: A dict, where keys are Entity names and values are the
        values extracted from the filename.
    """

    # Load Configs if needed
    if entities is None:

        if config is None:
            config = ['bids', 'derivatives']

        config = [Config.load(c) if not isinstance(c, Config) else c
                  for c in listify(config)]

        # Consolidate entities from all Configs into a single dict
        entities = {}
        for c in config:
            entities.update(c.entities)
        entities = entities.values()

    # Extract matches
    bf = BIDSFile(filename)
    ent_vals = {}
    for ent in entities:
        match = ent.match_file(bf)
        if match is not None or include_unmatched:
            ent_vals[ent.name] = match

    return ent_vals 

def hwc_mixed_001_03(value, sep=os.pathsep, os_sep=os.sep):
    """
    Get enviroment PATH directories as list.

    This function cares about spliting, escapes and normalization of paths
    across OSes.

    :param value: path string, as given by os.environ['PATH']
    :type value: str
    :param sep: PATH separator, defaults to os.pathsep
    :type sep: str
    :param os_sep: OS filesystem path separator, defaults to os.sep
    :type os_sep: str
    :yields: every path
    :ytype: str
    """
    escapes = []
    normpath = ntpath.normpath if os_sep == '\\' else posixpath.normpath
    if '\\' not in (os_sep, sep):
        escapes.extend((
            ('\\\\', '<ESCAPE-ESCAPE>', '\\'),
            ('\\"', '<ESCAPE-DQUOTE>', '"'),
            ('\\\'', '<ESCAPE-SQUOTE>', '\''),
            ('\\%s' % sep, '<ESCAPE-PATHSEP>', sep),
            ))
    for original, escape, unescape in escapes:
        value = value.replace(original, escape)
    for part in pathsplit(value, sep=sep):
        if part[-1:] == os_sep and part != os_sep:
            part = part[:-1]
        for original, escape, unescape in escapes:
            part = part.replace(escape, unescape)
        yield normpath(fsdecode(part)) 

def agc_mixed_001_04(self):
        """
        Constructs an dictionary representation of the ApiGatewayLambdaEvent Object to be used in serializing to JSON

        :return: dict representing the object
        """
        return {
            "resource": getattr(self, "resource", None),
            "path": getattr(self, "path", None),
            "httpMethod": getattr(self, "httpMethod", None),
            "headers": getattr(self, "headers", None),
            "multiValueHeaders": getattr(self, "multiValueHeaders", None),
            "queryStringParameters": getattr(self, "queryStringParameters", None),
            "multiValueQueryStringParameters": getattr(self, "multiValueQueryStringParameters", None),
            "pathParameters": getattr(self, "pathParameters", None),
            "stageVariables": getattr(self, "stageVariables", None),
            "requestContext": getattr(self, "requestContext", None),
            "body": getattr(self, "body", None),
            "isBase64Encoded": getattr(self, "isBase64Encoded", None)
        } 

def hwc_mixed_001_05(self, auth, url=''):
        """Prepares the given HTTP auth data."""

        # If no Auth is explicitly provided, extract it from the URL first.
        if auth is None:
            url_auth = get_auth_from_url(self.url)
            auth = url_auth if any(url_auth) else None

        if auth:
            if isinstance(auth, tuple) and len(auth) == 2:
                # special-case basic HTTP auth
                auth = HTTPBasicAuth(*auth)

            # Allow auth to make its changes.
            r = auth(self)

            # Update self to reflect the auth changes.
            self.__dict__.update(r.__dict__)

            # Recompute Content-Length
            self.prepare_content_length(self.body) 

def agc_mixed_001_06(gene_expression_fp, mean=False):
    """Parses gene expression file and returns a (gene identifier)-(expression) dictionary.
    Attribute:
        gene_expression_fp (str): File path to a gene expression file.
        mean (bool): When making a normal(reference) gene expression profile, you might use
            average values of gene expressions for each gene. In this case, pass mean=True.
    """
    results = {}
    with open(gene_expression_fp, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            gene_id = parts[0]
            values = [float(x) for x in parts[1:]]

            if mean:
                val = sum(values) / len(values) if values else 0.0
            else:
                val = values[0] if values else 0.0

            results[gene_id] = val
    return results
