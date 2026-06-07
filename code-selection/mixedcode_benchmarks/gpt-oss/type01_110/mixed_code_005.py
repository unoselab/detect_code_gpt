def agc_mixed_005_01(self, tree):
        """Provides the indexable - search engine oriented - raw text
        @param tree: an ElementTree
        @return: set(["foo", "bar", ...])
        """
        import re
        if tree is None:
            return set()
        words = set()
        pattern = re.compile(r"\b\w+\b")
        for text in tree.itertext():
            for match in pattern.findall(text):
                words.add(match.lower())
        return words 

def hwc_mixed_005_02(account=None, *args, **kwargs):
    """
    Simple Google Analytics integration.

    First looks for an ``account`` parameter. If not supplied, uses
    Django ``GOOGLE_ANALYTICS_ACCOUNT`` setting. If account not set, 
    raises ``TemplateSyntaxError``.

    :param account:
        Google Analytics account id to be used.

    """
    if not account:
        try:
            account = settings.GOOGLE_ANALYTICS_ACCOUNT
        except:
            raise template.TemplateSyntaxError( 
                    "Analytics account could not found either "
                    "in tag parameters or settings")
    return {'account': account, 'params':kwargs } 

def hwc_mixed_005_03(self, networks):
        """
        Returns a new experimental setup restricted to species present in the given list of networks

        Parameters
        ----------
        networks : :class:`caspo.core.logicalnetwork.LogicalNetworkList`
            List of logical networks

        Returns
        -------
        caspo.core.setup.Setup
            The restricted experimental setup
        """
        cues = self.stimuli + self.inhibitors
        active_cues = set()
        active_readouts = set()
        for clause, var in networks.mappings:
            active_cues = active_cues.union((l for (l, s) in clause if l in cues))
            if var in self.readouts:
                active_readouts.add(var)

        return Setup(active_cues.intersection(self.stimuli), active_cues.intersection(self.inhibitors), active_readouts) 

def agc_mixed_005_04(self, transport):
        """Method run when the UDP broadcast server is started
        """
        #print('started')
        self.transport = transport
        sock = transport.get_extra_info('socket')
        if sock is not None:
            import socket as _socket
            try:
                sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
            except OSError:
                pass 

def agc_mixed_005_05(data):
    """Retrieve regions to run in parallel, putting longest intervals first.
    """
    def _len(region):
        if isinstance(region, dict):
            return region.get('end', 0) - region.get('start', 0)
        try:
            start, end = region[0], region[1]
            return end - start
        except Exception:
            return 0

    return sorted(data, key=_len, reverse=True) 

def hwc_mixed_005_06(self, delta: Point):
        """
        Called by save calibration in order to update the offset on the object.
        """
        self._calibrated_offset = Point(x=self._offset.x + delta.x,
                                        y=self._offset.y + delta.y,
                                        z=self._offset.z + delta.z)
        self._wells = self._build_wells()
