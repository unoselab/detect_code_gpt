def agc_mixed_002_01(x, n_bases=10, spline_order=3, start=None, end=None, warn=True):
    """**Deprecated**. Function version of the transformer class `EncodeSplines`.
    Get B-spline base-function expansion

    # Details
        First, the knots for B-spline basis functions are placed
        equidistantly on the [start, end] range.
        (inferred from the data if None). Next, b_n(x) value is
        is computed for each x and each n (spline-index) with
        `scipy.interpolate.splev`.

    # Arguments
        x: a numpy array of positions with 2 dimensions
        n_bases int: Number of spline bases.
        spline_order: 2 for quadratic, 3 for qubic splines
        start, end: range of values. If None, they are inferred from the data
        as minimum and maximum value.
        warn: Show warnings.

    # Returns
        `np.ndarray` of shape `(x.shape[0], x.shape[1], n_bases)`
    """

    # TODO - make it general...
    if start is None:
        start = np.min(x)
    if end is None:
        end = np.max(x)
    knots = np.linspace(start, end, n_bases)
    basis_functions = np.empty((x.shape[0], x.shape[1], n_bases))
    for i in range(x.shape[0]):
        for j in range(x.shape[1]):
            tck = splrep(knots, x[i, j, :], k=spline_order)
            basis_functions[i, j, :] = splev(knots, tck)

    return basis_functions 

def hwc_mixed_002_02(self):
        """Returns an array of nodes in the tree that have balanced subtrees beneath them,
        moving from left to right.
        """
        subtrees = []
        loose_leaves = len(self.leaves) - 2**int(log(len(self.leaves), 2))
        the_node = self.root
        while loose_leaves:
            subtrees.append(the_node.l)
            the_node = the_node.r
            loose_leaves = loose_leaves - 2**int(log(loose_leaves, 2))
        subtrees.append(the_node)
        return subtrees 

def agc_mixed_002_03(self, api_url=None, offset=0, limit=-1, properties=None):
        """Get list of image group resources from a SCO-API.

        Parameters
        ----------
        api_url : string, optional
            Base Url of the SCO-API. Uses default API if argument not present.
        offset : int, optional
            Starting offset for returned list items
        limit : int, optional
            Limit the number of items in the result
        properties : List(string)
            List of additional object properties to be included for items in
            the result

        Returns
        -------
        List(scoserv.ResourceHandle)
            List of resource handles (one per image group in the listing)
        """
        # Get subject listing Url for given SCO-API and return the retrieved
        # resource listing
        api_url = api_url or self.api_url
        url = f"{api_url}/image_groups"
        params = {"offset": offset, "limit": limit}
        if properties:
            params["properties"] = ",".join(properties)
        response = self.session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return [self.resource_handle(item) for item in data["items"]] 

def hwc_mixed_002_04(self):
        """
        :return: the machine's mac address
        """
        command = const.CMD_OPTIONS_RRQ
        command_string = b'MAC\x00'
        response_size = 1024

        cmd_response = self.__send_command(command, command_string, response_size)
        if cmd_response.get('status'):
            mac = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return mac.decode()
        else:
            raise ZKErrorResponse("can't read mac address") 

def hwc_mixed_002_05(data, shape, dtype=None):
    """
    Zoom data to specific shape.
    """
    import scipy
    import scipy.ndimage

    zoomd = np.array(shape) / np.array(data.shape, dtype=np.double)
    import warnings

    datares = scipy.ndimage.interpolation.zoom(data, zoomd, order=0, mode="reflect")

    if datares.shape != shape:
        logger.warning("Zoom with different output shape")
    dataout = np.zeros(shape, dtype=dtype)
    shpmin = np.minimum(dataout.shape, shape)

    dataout[: shpmin[0], : shpmin[1], : shpmin[2]] = datares[
        : shpmin[0], : shpmin[1], : shpmin[2]
    ]
    return datares 

def agc_mixed_002_06(df, col_true=None, col_pred=None, col_scores=None, pos_label=1):
    r"""
    Compute life value, true positive rate (TPR) and threshold from predicted DataFrame.

    Note that this method will trigger the defined flow to execute.

    :param df: predicted data frame
    :type df: DataFrame
    :param pos_label: positive label
    :type pos_label: str
    :param col_true: true column
    :type col_true: str
    :param col_pred: predicted column, 'prediction_result' if absent.
    :type col_pred: str
    :param col_scores: score column, 'prediction_score' if absent.
    :type col_scores: str

    :return: lift value, true positive rate and threshold, in numpy array format.

    :Example:

    >>> import matplotlib.pyplot as plt
    >>> depth, lift, thresh = lift_chart(predicted)
    >>> plt.plot(depth, lift)
    """
    if col_pred is None:
        col_pred = 'prediction_result'
    if col_scores is None:
        col_scores = 'prediction_score'
    df = df.sort_values(col_scores, ascending=False)
    df['true_positive'] = (df[col_true] == pos_label).astype(int)
    df['false_positive'] = (df[col_true]!= pos_label).astype(int)
    df['cumulative_true_positive'] = df['true_positive'].cumsum()
    df['cumulative_false_positive'] = df['false_positive'].cumsum()
    df['depth'] = df.index + 1
    df['lift'] = df['cumulative_true_positive'] / df['depth']
    df['true_positive_rate'] = df['cumulative_true_positive'] / df['true_positive'].sum()
    df['threshold'] = df[col_scores]
    return df[['lift', 'true_positive_rate', 'threshold']].values
