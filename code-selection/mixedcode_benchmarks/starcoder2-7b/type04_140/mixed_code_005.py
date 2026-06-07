async def agc_mixed_005_01(self):  # pragma: no cover
        """Monitor connected clients and clean up those that time out."""
        while True:
            await asyncio.sleep(self._timeout)
            now = time.time()
            for client in self._clients.copy():
                if now - client.last_seen > self._timeout:
                    self._clients.pop(client.id)
                    self._logger.debug("Client %s timed out", client.id)
                    await self._on_client_disconnect(client) 

def agc_mixed_005_02(self, dt, use_dst=True, _recurse=False, **kwds):
        """Return pywws timestamp (utc, no tzinfo) for the most recent
        local time before the pywws timestamp dt, with datetime replace
        applied.

        """
        if not _recurse:
            self._local_replace_cache = {}
        if dt in self._local_replace_cache:
            return self._local_replace_cache[dt]
        if dt.tzinfo is None:
            dt = self.localize(dt)
        if use_dst:
            dt = dt.replace(tzinfo=self.tzinfo)
        else:
            dt = dt.replace(tzinfo=None)
        self._local_replace_cache[dt] = dt
        return dt 

def hwc_mixed_005_03(self):
        """ Close file stream.  Unlike close(), we don't tear anything down, we
        expect the log to be re-opened after rotation."""

        if self.stream:
            try:
                if not self.stream.closed:
                    # Flushing probably isn't technically necessary, but it feels right
                    self.stream.flush()
                    self.stream.close()
            finally:
                self.stream = None 

def hwc_mixed_005_04(logger=None):
    """
    Remove only stream handlers from the specified logger

    :param logger: logging name or object to modify, defaults to root logger
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)

    new_handlers = []
    for handler in logger.handlers:
        # FileHandler is a subclass of StreamHandler so
        # 'if not a StreamHandler' does not work
        if (isinstance(handler, logging.FileHandler) or
            isinstance(handler, logging.NullHandler) or
            (isinstance(handler, logging.Handler) and not
                isinstance(handler, logging.StreamHandler))):
            new_handlers.append(handler)
    logger.handlers = new_handlers 

def agc_mixed_005_05(conn, tablename, column_names, records, chunksize=2500):
    """Insert many records by chunking data into insert statements.

    Notes
    -----
    records should be Iterable collection of namedtuples or tuples.
    """

    cursor = conn.cursor()
    for i in range(0, len(records), chunksize):
        records_slice = records[i:i + chunksize]
        cursor.executemany(
            'INSERT INTO {} ({}) VALUES ({})'.format(
                tablename,
                ','.join(column_names),
                ','.join(['%s'] * len(column_names))
            ),
            records_slice
        )
    conn.commit() 

def hwc_mixed_005_06(html):
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
