def agc_mixed_005_01(task_queue, result_queue, timer, timeout=Conf.TIMEOUT):
    """
    Takes a task from the task queue, tries to execute it and puts the result back in the result queue
    :type task_queue: multiprocessing.Queue
    :type result_queue: multiprocessing.Queue
    :type timer: multiprocessing.Value
    """
    while True:
        try:
            task = task_queue.get(timeout=timeout)
            if task is None:
                break
            result = task()
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e) 

def agc_mixed_005_02(gtf):
    """
    Load GTF file with precursor positions on genome
    """
    gtf_data = []
    with open(gtf, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            line = line.strip().split('\t')
            if line[2] == 'exon':
                gtf_data.append([line[0], line[3], line[4], line[6], line[8].split(';')[0].split(' ')[1]])
    return gtf_data 

def agc_mixed_005_03(self, start_address, search_length):
        """Find the control structure in RAM for this device.

        Returns:
            ControlStructure: The decoded contents of the shared memory control structure
                used for communication with this IOTile device.
        """

        control_structure_address = start_address + self.control_structure_offset
        control_structure = self.read_control_structure(control_structure_address)
        if control_structure.magic_number != self.control_structure_magic_number:
            raise ValueError(
                "Control structure magic number mismatch. Expected %s, got %s"
                % (self.control_structure_magic_number, control_structure.magic_number)
            )
        return control_structure 

def hwc_mixed_005_04(self, anon=github.GithubObject.NotSet):
        """
        :calls: `GET /repos/:owner/:repo/contributors <http://developer.github.com/v3/repos>`_
        :param anon: string
        :rtype: :class:`github.PaginatedList.PaginatedList` of :class:`github.NamedUser.NamedUser`
        """
        url_parameters = dict()
        if anon is not github.GithubObject.NotSet:
            url_parameters["anon"] = anon

        return github.PaginatedList.PaginatedList(
            github.NamedUser.NamedUser,
            self._requester,
            self.url + "/contributors",
            url_parameters
        ) 

def hwc_mixed_005_05():
    """
    Returns a pseudo-randomly generated Local Unique prefix. Function
    follows recommandation of Section 3.2.2 of RFC 4193 for prefix
    generation.
    """
    # Extracted from RFC 1305 (NTP) :
    # NTP timestamps are represented as a 64-bit unsigned fixed-point number, 
    # in seconds relative to 0h on 1 January 1900. The integer part is in the 
    # first 32 bits and the fraction part in the last 32 bits.

    # epoch = (1900, 1, 1, 0, 0, 0, 5, 1, 0) 
    # x = time.time()
    # from time import gmtime, strftime, gmtime, mktime
    # delta = mktime(gmtime(0)) - mktime(self.epoch)
    # x = x-delta

    tod = time.time() # time of day. Will bother with epoch later
    i = int(tod)
    j = int((tod - i)*(2**32))
    tod = struct.pack("!II", i,j)
    # TODO: Add some check regarding system address gathering
    rawmac = get_if_raw_hwaddr(conf.iface6)
    mac = b":".join(map(lambda x: b"%.02x" % ord(x), list(rawmac)))
    # construct modified EUI-64 ID
    eui64 = inet_pton(socket.AF_INET6, '::' + in6_mactoifaceid(mac))[8:] 
    import sha
    globalid = sha.new(tod+eui64).digest()[:5]
    return inet_ntop(socket.AF_INET6, b'\xfd' + globalid + b'\x00'*10) 

def hwc_mixed_005_06(self, mrls=None):
        """Create a new MediaList instance.
        @param mrls: optional list of MRL strings
        """
        l = libvlc_media_list_new(self)
        # We should take the lock, but since we did not leak the
        # reference, nobody else can access it.
        if mrls:
            for m in mrls:
                l.add_media(m)
        l._instance = self
        return l
