def hwc_mixed_001_01(self, instrument=None, count=50):
        """
            See more:
            http://developer.oanda.com/rest-live/orders/#getOrdersForAnAccount
        """
        url = "{0}/{1}/accounts/{2}/orders".format(
            self.domain,
            self.API_VERSION,
            self.account_id
        )
        params = {"instrument": instrument, "count": count}
        try:
            return self._Client__call(uri=url, params=params, method="get")
        except RequestException:
            return False
        except AssertionError:
            return False 

def agc_mixed_001_02(db_name):
    """Execute any pending work in the database stored in `db_name`,
    recording the results.

    This looks for any work in `db_name` which has no results, schedules it to
    be executed, and records any results that arrive.
    """
    db = get_db(db_name)
    for work in db.work_list():
        if work.results:
            continue
        if work.scheduled:
            continue
        db.schedule(work)
        try:
            results = work.execute()
        except Exception as e:
            db.record_failure(work, e)
        else:
            db.record_success(work, results) 

def agc_mixed_001_03(self, **kwargs):
        """Auto Generated Code
        """
        try:
            self.logger.info("Executing firmware_download_input_protocol_type_scp_protocol_scp_user step")
            # Setup the arguments for the command
            arguments = {}
            arguments["scp_user"] = kwargs["scp_user"]
            # Execute the command
            self.mgmt_client.firmware_download_input_protocol_type_scp_protocol_scp_user_put(**arguments)
        except Exception as e:
            print(e.args[0])
            raise 

def hwc_mixed_001_04(html):
        """
        Extract a list of hyperlinks from an HTML document.
        """
        links = []
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.findAll('a'):
            href = link.get('href')
            if not href:
                continue
            if href.startswith('/'):
                href = 'https://www.reddit.com' + href
            links.append({'text': link.text, 'href': href})
        return links 

def hwc_mixed_001_05(self):
        """Connect to the unix domain socket, which is passed to us as self.host

        This is in host because the format we use for the unix domain socket is:

        http+unix://%2Fpath%2Fto%2Fsocket.sock

        """
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

            if has_timeout(self.timeout):
                self.sock.settimeout(self.timeout)

            self.sock.connect(unquote(self.host))
        except socket.error as msg:
            if self.sock:
                self.sock.close()
            self.sock = None

            raise socket.error(msg) 

def agc_mixed_001_06(left, right, verbose=False):
    """Return the explanation for the diff between text or bytes

    Unless --verbose is used this will skip leading and trailing
    characters which are identical to keep the diff minimal.

    If the input are bytes they will be safely converted to text.
    """
    if isinstance(left, bytes):
        left = left.decode("utf-8", "replace")
    if isinstance(right, bytes):
        right = right.decode("utf-8", "replace")

    if verbose:
        return difflib.ndiff(left.splitlines(True), right.splitlines(True))

    # Skip identical leading and trailing lines
    left_lines = left.splitlines(True)
    right_lines = right.splitlines(True)
    while left_lines and right_lines and left_lines[0] == right_lines[0]:
        left_lines.pop(0)
        right_lines.pop(0)
    while left_lines and right_lines and left_lines[-1] == right_lines[-1]:
        left_lines.pop()
        right_lines.pop()

    return difflib.unified_diff(left_lines, right_lines, n=0)
