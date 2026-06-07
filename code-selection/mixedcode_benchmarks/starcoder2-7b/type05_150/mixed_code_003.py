def agc_mixed_003_01(hostname, username, password, label):
    """
    A function to connect to a bigip device and start a new transaction.

    hostname
        The host/address of the bigip device
    username
        The iControl REST username
    password
        The iControl REST password
    label
        The name / alias for this transaction.  The actual transaction
        id will be stored within a grain called ``bigip_f5_trans:<label>``

    CLI Example::

        salt '*' bigip.start_transaction bigip admin admin my_transaction

    """

    #build the session
    if not hostname:
        raise SaltInvocationError("hostname is a required parameter")
    if not username:
        raise SaltInvocationError("username is a required parameter")
    if not password:
        raise SaltInvocationError("password is a required parameter")
    if not label:
        raise SaltInvocationError("label is a required parameter")

    # Connect to the device
    device = Device(hostname, username, password)
    device.open()

    # Start the transaction
    device.start_transaction(label)

    # Store the transaction id in the grains
    grains = __salt__['grains.get']()
    grains['bigip_f5_trans:' + label] = device.transaction_id
    __salt__['grains.set']('bigip_f5_trans:' + label, device.transaction_id)

    return device.transaction_id 

def agc_mixed_003_02(self, job_id, timeout=None):
        """
        Wait for the job given by job_id to change to COMPLETED or CANCELED. Raises a
        iceqube.exceptions.TimeoutError if timeout is exceeded before each job change.

        :param job_id: the id of the job to wait for.
        :param timeout: how long to wait for a job state change before timing out.
        """
        if timeout is None:
            timeout = self.timeout
        start_time = time.time()
        while True:
            job = self.get_job(job_id)
            if job.state in ['COMPLETED', 'CANCELED']:
                return
            if time.time() - start_time > timeout:
                raise TimeoutError('Timeout waiting for job to complete')
            time.sleep(self.poll_interval) 

def hwc_mixed_003_03(source=None, source_hash=None,
                              sources=None, source_hashes=None):
    """
    Silly little function to give us a standard tuple list for sources and
    source_hashes
    """
    if sources is None:
        sources = []

    if source_hashes is None:
        source_hashes = []

    if source and sources:
        return (False,
                "source and sources are mutually exclusive", [])

    if source_hash and source_hashes:
        return (False,
                "source_hash and source_hashes are mutually exclusive", [])

    if source:
        return (True, '', [(source, source_hash)])

    # Make a nice neat list of tuples exactly len(sources) long..
    return True, '', list(zip_longest(sources, source_hashes[:len(sources)])) 

def agc_mixed_003_04(upstream_file_url, data_source):
    """ The file format is:

    # Upstream contributions, bitergia will crawl this and extract the relevant information
    # system is one of Gerrit, Bugzilla, Launchpad (insert more)
    ---
    -
      url: https://review.openstack.org/169836
      system: Gerrit
    """

    with open(upstream_file_url, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            line = line.strip()
            if not line:
                continue
            data = yaml.safe_load(line)
            if not data:
                continue
            yield data 

def hwc_mixed_003_05 (data):
    """Return iterator for bookmarks of the form (url, name, line number).
    Bookmarks are not sorted.
    """
    name = None
    lineno = 0
    for line in data.splitlines():
        lineno += 1
        line = line.strip()
        if line.startswith("NAME="):
            name = line[5:]
        elif line.startswith("URL="):
            url = line[4:]
            if url and name is not None:
                yield (url, name, lineno)
        else:
            name = None 

def hwc_mixed_003_06(self):
        """DataFrame: Get a dataframe of UniProt -> best structure in PDB results"""
        df = pd.DataFrame()
        for g in self.genes_with_experimental_structures:
            protein_df = g.protein.df_pdb_ranking.copy().reset_index()
            if not protein_df.empty:
                protein_df['gene'] = g.id
                df = df.append(protein_df)
        if df.empty:
            log.warning('Empty dataframe')
            return df
        else:
            return ssbio.utils.clean_df(df.set_index('gene'))
