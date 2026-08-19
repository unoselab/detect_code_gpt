def agc_mixed_001_01(self, up_to_index=None, verbose=True):
        """Cache all event offsets."""
        if up_to_index is None:
            up_to_index = len(self.events)

        offsets = []
        current_offset = 0
        for i in range(up_to_index):
            offsets.append(current_offset)
            current_offset += len(self.events[i])

        self._offsets = offsets
        if verbose:
            print(f"Cached {len(offsets)} event offsets.") 

def agc_mixed_001_02(invec, outvec, N1, N2):
    """
    This implements the first phase of the FFT decomposition, using
    the standard FFT many plans.

    Parameters
    -----------
    invec : array
        The input array.
    outvec : array
        The output array.
    N1 : int
        Number of rows.
    N2 : int
        Number of columns.
    """
    import numpy as np

    for i in range(N1):
        for j in range(N2):
            outvec[i * N2 + j] = invec[i * N2 + j]

    for i in range(N1):
        row_start = i * N2
        # Perform 1D FFT on each row
        row_data = outvec[row_start : row_start + N2]
        fft_row = np.fft.fft(row_data)
        outvec[row_start : row_start + N2] = fft_row 

def hwc_mixed_001_03(func):
    """Wraps an asynchronous function into a synchronous function."""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        fut = asyncio.ensure_future(func(*args, **kwargs))
        cur = greenlet.getcurrent()
        def callback(fut):
            try:
                cur.switch(fut.result())
            except BaseException as e:
                cur.throw(e)
        fut.add_done_callback(callback)
        return cur.parent.switch()
    return wrapped 

def hwc_mixed_001_04(self, chunk):
        """
        Link one YAML chunk to another.

        Used when inserting a chunk of YAML into another chunk.
        """
        if self.is_mapping():
            for key, value in self.contents.items():
                self.key(key, key).pointer.make_child_of(chunk.pointer)
                self.val(key).make_child_of(chunk)
        elif self.is_sequence():
            for index, item in enumerate(self.contents):
                self.index(index).make_child_of(chunk)
        else:
            self.pointer.make_child_of(chunk.pointer) 

def hwc_mixed_001_05(self, namespace, start_offset, end_offset):
        """Get namespace statistics for the period between start_offset and
        end_offset (inclusive)"""
        cursor = self.cursor
        cursor.execute('SELECT SUM(data_points), SUM(byte_count) '
                       'FROM gauged_statistics WHERE namespace = %s '
                       'AND offset BETWEEN %s AND %s',
                       (namespace, start_offset, end_offset))
        return [long(count or 0) for count in cursor.fetchone()] 

def agc_mixed_001_06(self, start=0, stop=None, fps=30):
        """
        Method to return a matplotlib animation. The start and stop
        frames may be specified as well as the fps.
        """
        import matplotlib.animation as animation
        if stop is None:
            stop = self.num_frames

        fig = self.fig
        def update(frame):
            self.update_frame(frame)
            return fig.canvas.draw()

        return animation.FuncAnimation(
            fig, update, frames=range(start, stop), interval=1000/fps
        )
