def hwc_mixed_004_01(generator, public_pair, chain_code_bytes, i):
    """
    Yield info for a child node for this node.

    generator:
        the ecdsa generator
    public_pair:
        base public pair
    chain_code:
        base chain code
    i:
        the index for this node.

    Returns a pair (new_public_pair, new_chain_code)
    """
    INFINITY = generator.infinity()
    ORDER = generator.order()
    i_as_bytes = struct.pack(">l", i)
    sec = public_pair_to_sec(public_pair, compressed=True)
    data = sec + i_as_bytes

    I64 = hmac.HMAC(key=chain_code_bytes, msg=data, digestmod=hashlib.sha512).digest()
    I_left_as_exponent = from_bytes_32(I64[:32]) % ORDER
    the_point = I_left_as_exponent * generator + generator.Point(*public_pair)
    if the_point == INFINITY:
        logger.critical(_SUBKEY_VALIDATION_LOG_ERR_FMT)
        raise DerivationError('K_{} == {}'.format(i, the_point))

    new_chain_code = I64[32:]
    return the_point, new_chain_code 

def hwc_mixed_004_02(self):
        """Update the channels list when a new group is selected."""
        group_dict = {k['name']: i for i, k in enumerate(self.groups)}
        group_index = group_dict[self.idx_group.currentText()]
        self.one_grp = self.groups[group_index]

        self.idx_chan.clear()

        self.idx_chan.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for chan in self.one_grp['chan_to_plot']:
            name = chan + '—(' + '+'.join(self.one_grp['ref_chan']) + ')'
            item = QListWidgetItem(name)
            self.idx_chan.addItem(item) 

def agc_mixed_004_03(index, start, end):
    """Compute the metrics for the project process section of the enriched
    github issues index.

    Returns a dictionary containing "bmi_metrics", "time_to_close_metrics",
    "time_to_close_review_metrics" and patchsets_metrics as the keys and
    the related Metrics as the values.
    time_to_close_title and time_to_close_review_title contain the file names
    to be used for time_to_close_metrics and time_to_close_review_metrics
    metrics data.

    :param index: index object
    :param start: start date to get the data from
    :param end: end date to get the data upto
    :return: dictionary with the value of the metrics
    """

    bmi_metrics = index.bmi_metrics(start, end)
    time_to_close_metrics = index.time_to_close_metrics(start, end)
    time_to_close_review_metrics = index.time_to_close_review_metrics(start, end)
    patchsets_metrics = index.patchsets_metrics(start, end)
    time_to_close_title = index.time_to_close_title(start, end)
    time_to_close_review_title = index.time_to_close_review_title(start, end)
    return {
        "bmi_metrics": bmi_metrics,
        "time_to_close_metrics": time_to_close_metrics,
        "time_to_close_review_metrics": time_to_close_review_metrics,
        "patchsets_metrics": patchsets_metrics,
        "time_to_close_title": time_to_close_title,
        "time_to_close_review_title": time_to_close_review_title,
    } 

def hwc_mixed_004_04(self, ax, new_value):
        """Make bars in horizontal bar chart thinner"""
        for patch in ax.patches:
            current_height = patch.get_height()
            diff = current_height - new_value

            # we change the bar height
            patch.set_height(new_value)

            # we recenter the bar
            patch.set_y(patch.get_y() + diff * .5) 

def agc_mixed_004_05(pst,logger=None, **kwargs):
    """plot current phi components as a pie chart.

    Parameters
    ----------
    pst : pyemu.Pst
    logger : pyemu.Logger
    kwargs : dict
        accepts 'include_zero' as a flag to include phi groups with
        only zero-weight obs (not sure why anyone would do this, but
        whatevs).
    Returns
    -------
    ax : matplotlib.Axis


    """
    if logger is not None:
        logger.statement("plotting phi components as a pie chart")
    phi_groups = pst.phi_components
    if not kwargs.get("include_zero", False):
        phi_groups = {k: v for k, v in phi_groups.items() if v!= 0.0}
    labels = list(phi_groups.keys())
    sizes = list(phi_groups.values())
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle.

    return ax 

def agc_mixed_004_06(infile, verbose, jsonout):
    """Extract email addresses from a file or stdin.

    Example:

    \b
    $ cat /var/log/auth.log | habu.extract.email
    john@securetia.com
    raven@acmecorp.net
    nmarks@fimax.com
    """

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    if infile:
        with open(infile, "r") as f:
            content = f.read()
    else:
        content = sys.stdin.read()
    emails = re.findall(email_pattern, content)
    if verbose:
        print(f"Found {len(emails)} email addresses in the input.")
    if jsonout:
        return json.dumps(emails)
    else:
        return "\n".join(emails)
