def agc_mixed_001_01(self, urls):
    """Return reachable urls sorted by their ping times."""
    import time
    import concurrent.futures
    try:
        import requests
    except ImportError:
        raise ImportError("The 'requests' library is required for get_available_urls")

    def _ping(url):
        start = time.time()
        try:
            requests.head(url, timeout=5, allow_redirects=True)
            return (url, time.time() - start)
        except Exception:
            return None

    urls = list(urls)
    if not urls:
        return []

    max_workers = min(20, len(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_ping, urls))

    reachable = [(u, t) for u, t in results if u is not None]
    reachable.sort(key=lambda x: x[1])
    return [u for u, _ in reachable] 

def agc_mixed_001_02(self, nickname, email=None, phone_number=None, user_id=None):
        """Add a user to the group.

        You must provide either the email, phone number, or user_id that
        uniquely identifies a user.

        :param str nickname: new name for the user in the group
        :param str email: email address of the user
        :param str phone_number: phone number of the user
        :param str user_id: user_id of the user
        :return: a membership request
        :rtype: :class:`MembershipRequest`
        """
        identifiers = {
            'email': email,
            'phone_number': phone_number,
            'user_id': user_id,
        }
        provided = [key for key, value in identifiers.items() if value is not None]
        if len(provided) != 1:
            raise ValueError(
                "You must provide exactly one of email, phone_number, or user_id."
            )

        # Build the request payload
        payload = {'nickname': nickname}
        payload.update({provided[0]: identifiers[provided[0]]})

        # Create and return a MembershipRequest instance
        return MembershipRequest(**payload) 

def hwc_mixed_001_03(self):
        """
        Checks whether the kernels in the combination act on disjoint subsets
        of dimensions. Currently, it is hard to asses whether two slice objects
        will overlap, so this will always return False.
        :return: Boolean indicator.
        """
        if np.any([isinstance(k.active_dims, slice) for k in self.kernels]):
            # Be conservative in the case of a slice object
            return False
        else:
            dimlist = [k.active_dims for k in self.kernels]
            overlapping = False
            for i, dims_i in enumerate(dimlist):
                for dims_j in dimlist[i + 1:]:
                    if np.any(dims_i.reshape(-1, 1) == dims_j.reshape(1, -1)):
                        overlapping = True
            return not overlapping 

def hwc_mixed_001_04(self, s):
    """Replace ansi escape sequences with spans of appropriately named css classes."""
    parts = HtmlReporter._ANSI_COLOR_CODE_RE.split(s)
    ret = []
    span_depth = 0
    # Note that len(parts) is always odd: text, code, text, code, ..., text.
    for i in range(0, len(parts), 2):
      ret.append(parts[i])
      if i + 1 < len(parts):
        for code in parts[i + 1].split(';'):
          if code == 0:  # Reset.
            while span_depth > 0:
              ret.append('</span>')
              span_depth -= 1
          else:
            ret.append('<span class="ansi-{}">'.format(code))
            span_depth += 1
    while span_depth > 0:
      ret.append('</span>')
      span_depth -= 1

    return ''.join(ret) 

def agc_mixed_001_05(status_code, response, headers=None):
    """
    Log an HTTP response data in a user-friendly representation.

    :param status_code: HTTP Status Code
    :param response: Raw response content (string)
    :param headers: Headers in the response (dict)
    :return: None
    """

    import logging

    logger = logging.getLogger(__name__)

    lines = [f"HTTP Response: {status_code}"]
    if headers:
        lines.append("Headers:")
        for key, value in sorted(headers.items()):
            lines.append(f"  {key}: {value}")
    # Ensure response is a string
    if isinstance(response, (bytes, bytearray)):
        try:
            response_text = response.decode("utf-8", errors="replace")
        except Exception:
            response_text = str(response)
    else:
        response_text = str(response)

    # Truncate long bodies for readability
    max_len = 500
    if len(response_text) > max_len:
        truncated = response_text[:max_len] + f"... (truncated {len(response_text) - max_len} characters)"
        response_text = truncated

    lines.append("Body:")
    lines.append(response_text)

    logger.info("\n".join(lines)) 

def hwc_mixed_001_06(append_version: bool = False) -> str:
    """A function to return the path to the current Python interpreter.

    Even when inside a venv, this will return the interpreter the venv was created with.

    """

    base_dir = Path(getattr(sys, "real_prefix", sys.base_prefix)).resolve()
    sys_exec = Path(sys.executable)
    name = sys_exec.stem
    suffix = sys_exec.suffix

    if append_version:
        name += str(sys.version_info.major)

    name += suffix

    try:
        return str(next(iter(base_dir.rglob(name))))

    except StopIteration:

        if not append_version:
            # If we couldn't find an interpreter, it's likely that we looked for
            # "python" when we should've been looking for "python3"
            # so we try again with append_version=True
            return _interpreter_path(append_version=True)

        # If we were still unable to find a real interpreter for some reason
        # we fallback to the current runtime's interpreter
        return sys.executable
