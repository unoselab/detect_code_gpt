def hwc_mixed_002_01(self, i, x):
        """Handles string formatting of cell data

            i - index of the cell datatype in self._dtype
            x - cell data to format
        """
        FMT = {
            'a':self._fmt_auto,
            'i':self._fmt_int,
            'f':self._fmt_float,
            'e':self._fmt_exp,
            't':self._fmt_text,
            }

        n = self._precision
        dtype = self._dtype[i]
        try:
            if callable(dtype):
                return dtype(x)
            else:
                return FMT[dtype](x, n=n)
        except FallbackToText:
            return self._fmt_text(x) 

def agc_mixed_002_02(f):
    """
    Ensures that *args consist of a consistent type

    :param f: any client method with *args parameter
    :return: function f
    """

    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if args:
            first_type = type(args[0])
            for a in args[1:]:
                if type(a) is not first_type:
                    raise TypeError(
                        f"All positional arguments must be of the same type, "
                        f"got {first_type.__name__} and {type(a).__name__}"
                    )
        return f(*args, **kwargs)

    return wrapper 

def hwc_mixed_002_03(dfs_data):
    """Sorts the adjacency list representation by the edge weights."""
    new_adjacency_lists = {}

    adjacency_lists = dfs_data['adj']
    edge_weights = dfs_data['edge_weights']
    edge_lookup = dfs_data['edge_lookup']

    for node_id, adj_list in list(adjacency_lists.items()):
        node_weight_lookup = {}
        frond_lookup = {}
        for node_b in adj_list:
            edge_id = dfs_data['graph'].get_first_edge_id_by_node_ids(node_id, node_b)
            node_weight_lookup[node_b] = edge_weights[edge_id]
            frond_lookup[node_b] = 1 if edge_lookup[edge_id] == 'backedge' else 2

        # Fronds should be before branches if the weights are equal
        new_list = sorted(adj_list, key=lambda n: frond_lookup[n])

        # Sort by weights
        new_list.sort(key=lambda n: node_weight_lookup[n])

        # Add the new sorted list to the new adjacency list lookup table
        new_adjacency_lists[node_id] = new_list

    return new_adjacency_lists 

def agc_mixed_002_04(options=None, xml=None):
    """
    Post data to Nagios NRDP
    """
    import requests

    if xml is None:
        raise ValueError("xml payload is required")
    if not isinstance(options, dict):
        raise ValueError("options must be a dict containing 'url' and 'token'")
    url = options.get('url')
    token = options.get('token')
    if not url:
        raise ValueError("options must include 'url'")
    if not token:
        raise ValueError("options must include 'token'")
    timeout = options.get('timeout', 10)
    verify = options.get('verify', True)

    payload = {
        'token': token,
        'XMLDATA': xml
    }

    try:
        resp = requests.post(url, data=payload, timeout=timeout, verify=verify)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to post data to NRDP: {e}") 

def agc_mixed_002_05(self, cx, cy, r, stroke=None, fill=None, stroke_width=1):
        """
        :param cx: Center X
        :param cy: Center Y
        :param r: Radius
        """
        attrs = {'cx': cx, 'cy': cy, 'r': r}
        if stroke is not None:
            attrs['stroke'] = stroke
        if fill is not None:
            attrs['fill'] = fill
        if stroke_width is not None:
            attrs['stroke-width'] = stroke_width
        attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        element = f'<circle {attr_str} />'
        if hasattr(self, '_elements'):
            self._elements.append(element)
        elif hasattr(self, 'elements'):
            self.elements.append(element)
        else:
            self._elements = [element]
        return self 

def hwc_mixed_002_06(args, edges):
    """Run OSLOM with an in-memory list of edges, return in-memory results."""
    # Create an OSLOM runner with a temporary working directory
    oslom_runner = OslomRunner(tempfile.mkdtemp())

    # Write temporary edges file with re-mapped Ids
    logging.info("writing temporary edges file with re-mapped Ids ...")
    oslom_runner.store_edges(edges)

    # Run OSLOM
    logging.info("running OSLOM ...")
    log_file = os.path.join(oslom_runner.working_dir, OSLOM_LOG_FILE)
    result = oslom_runner.run(args.oslom_exec, args.oslom_args, log_file)
    with open(log_file, "r") as reader:
        oslom_log = reader.read()
    if result["retval"] != 0:
        logging.error("error running OSLOM, check the log")
        return (None, oslom_log)
    logging.info("OSLOM executed in %.3f secs", result["time"])

    # Read back clusters found by OSLOM
    logging.info("reading OSLOM clusters output file ...")
    clusters = oslom_runner.read_clusters(args.min_cluster_size)
    logging.info(
        "found %d cluster(s) and %d with size >= %d",
        clusters["num_found"], len(clusters["clusters"]), args.min_cluster_size)

    # Clean-up temporary working directory
    oslom_runner.cleanup()

    # Finished
    logging.info("finished")
    return (clusters, oslom_log)
