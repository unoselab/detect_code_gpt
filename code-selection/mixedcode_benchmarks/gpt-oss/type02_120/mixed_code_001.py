def agc_mixed_001_01(self, message_type, data, callback=None, one_way=False):
        """Sends a message of message_type

        Args:
            message_type (validator_pb2.Message): enum value
            data (bytes): serialized protobuf
            callback (function): a callback function to call when a
                response to this message is received

        Returns:
            future.Future
        """
        import struct, concurrent.futures

        # Ensure a unique request identifier for correlating responses
        request_id = 0
        if not one_way:
            request_id = getattr(self, "_next_req_id", 1)
            self._next_req_id = request_id + 1

        # Prepare a Future that will be returned to the caller
        fut = concurrent.futures.Future()

        # Register callback/future 

def agc_mixed_001_02(seqs, names, out_fa):
    """get fasta from sequences"""
    if len(seqs) != len(names):
        raise ValueError("seqs and names must have the same length")
    with open(out_fa, "w") as fh:
        for name, seq in zip(names, seqs):
            fh.write(f">{name}\n")
            # write sequence in lines of up to 60 characters for readability
            for i in range(0, len(seq), 60):
                fh.write(seq[i:i+60] + "\n") 

def hwc_mixed_001_03(self, key, ndim, subset=None):
        """
        Sub-classes to define. Return a sliced object.

        Parameters
        ----------
        key : string / list of selections
        ndim : 1,2
            requested ndim of result
        subset : object, default None
            subset to act on
        """
        self._set_binner()
        grouper = self.grouper
        if subset is None:
            subset = self.obj
        grouped = groupby(subset, by=None, grouper=grouper, axis=self.axis)

        # try the key selection
        try:
            return grouped[key]
        except KeyError:
            return grouped 

def hwc_mixed_001_04(self, dimension):
        """
        Partition subspace into desired dimension.

        :type dimension: int
        :param dimension: Maximum dimension to use.
        """
        # Take leftmost 'dimension' input basis vectors
        for i, channel in enumerate(self.u):
            if self.v[i].shape[1] < dimension:
                raise IndexError('Channel is max dimension %s'
                                 % self.v[i].shape[1])
            self.data[i] = channel[:, 0:dimension]
        self.dimension = dimension
        return self 

def hwc_mixed_001_05(pixel, level):
        """Transform from pixel to geo coordinates"""
        pixel_x = pixel[0]
        pixel_y = pixel[1]
        map_size = float(TileSystem.map_size(level))
        x = (TileSystem.clip(pixel_x, (0, map_size - 1)) / map_size) - 0.5
        y = 0.5 - (TileSystem.clip(pixel_y, (0, map_size - 1)) / map_size)
        lat = 90 - 360 * atan(exp(-y * 2 * pi)) / pi
        lon = 360 * x
        return round(lat, 6), round(lon, 6) 

def agc_mixed_001_06(self):
        """Draw the table

        - the table is returned as a whole string
        """

        rows = getattr(self, 'rows', None)
        if rows is None:
            rows = getattr(self, 'data', [])
        if not rows:
            return ''
        # Ensure rows are sequences
        rows = [list(r) for r in rows]
        col_count = max(len(r) for r in rows)
        # Pad rows to
