def hwc_mixed_003_01(
        self, timeout: Union[int, float] = None, safe: bool = False
    ) -> List[Union[Any, Exception]]:
        """
        Call :py:meth:`~Process.wait()` on all the Processes in this list.

        :param timeout:
            Same as :py:meth:`~Process.wait()`.

            This parameter controls the timeout for all the Processes combined,
            not a single :py:meth:`~Process.wait()` call.
        :param safe:
            Suppress any errors that occur while waiting for a Process.

            The return value of failed :py:meth:`~Process.wait()` calls are substituted with the ``Exception`` that occurred.
        :return:
            A ``list`` containing the values returned by child Processes of this Context.
        """
        if safe:
            _wait = self._wait_or_catch_exc
        else:
            _wait = Process.wait

        if timeout is None:
            return [_wait(process) for process in self]
        else:
            final = time.time() + timeout
            return [_wait(process, final - time.time()) for process in self] 

def hwc_mixed_003_02(text: str, ignore_chars: str = _DEFAULT_IGNORE_CHARS) -> float:
    """
    :param str text: input text
    :return: float, proportion of characters in the text that is Thai character
    """
    if not text or not isinstance(text, str):
        return 0

    if not ignore_chars:
        ignore_chars = ""

    num_thai = 0
    num_ignore = 0

    for ch in text:
        if ch in ignore_chars:
            num_ignore += 1
        elif isthaichar(ch):
            num_thai += 1

    num_count = len(text) - num_ignore

    return (num_thai / num_count) * 100 

def hwc_mixed_003_03(background):
    """Formats the background section

    :param background: the background content or file.

    :type background: str or file

    :returns: the background content.
    :rtype: str

    """
    # Getting the background
    if os.path.isfile(background):
        with open(background, "r") as i_file:
            background = i_file.read().splitlines()
    else:
        background = background.splitlines()

    # Formatting
    final_background = ""
    for line in background:
        if line == "":
            final_background += r"\\" + "\n\n"
            continue

        final_background += latex.wrap_lines(latex.sanitize_tex(line))

    return final_background 

def agc_mixed_003_04(self, rison_args):
        """
            Help function to handle rison order
            arguments

        :param rison_args:
        :return:
        """
        order_args = {}
        for arg in rison_args:
            key, value = arg.split('=')
            if key =='sort':
                order_args['order_by'] = value
            elif key == 'dir':
                order_args['order_dir'] = value
        return order_args 

def agc_mixed_003_05(device, response_queue, payload, timeout_s=None, poll=POLL_QUEUES):
    """
    Send payload to serial device and wait for response.

    Parameters
    ----------
    device : serial.Serial
        Serial instance.
    response_queue : Queue.Queue
        Queue to wait for response on.
    payload : str or bytes
        Payload to send.
    timeout_s : float, optional
        Maximum time to wait (in seconds) for response.

        By default, block until response is ready.
    poll : bool, optional
        If ``True``, poll response queue in a busy loop until response is
        ready (or timeout occurs).

        Polling is much more processor intensive, but (at least on Windows)
        results in faster response processing.  On Windows, polling is
        enabled by default.
    """
    device.write(payload)
    if poll:
        start_time = time.time()
        while True:
            if response_queue.qsize() > 0:
                return response_queue.get()
            if timeout_s is not None and time.time() - start_time > timeout_s:
                raise TimeoutError("Timeout occurred while waiting for response.")
    else:
        return response_queue.get(timeout=timeout_s) 

def agc_mixed_003_06(self):
        """
        Takes a list of IPOption objects and returns a packed byte string
        of options, appropriately padded if necessary.
        """
        options_bytes = b""
        for option in self:
            option_bytes = option.to_bytes()
            options_bytes += option_bytes
            if len(option_bytes) % 4!= 0:
                padding_bytes = b"\x00" * (4 - len(option_bytes) % 4)
                options_bytes += padding_bytes
        return options_bytes
