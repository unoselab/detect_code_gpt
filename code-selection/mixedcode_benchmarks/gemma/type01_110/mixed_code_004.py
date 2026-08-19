def hwc_mixed_004_01(model, oldres, newres):
    """
    Replace one entity in the model with another with the same links

    :param model: Versa model to be updated
    :param oldres: old/former resource IRI to be replaced
    :param newres: new/replacement resource IRI
    :return: None
    """
    oldrids = set()
    for rid, link in model:
        if link[ORIGIN] == oldres or link[TARGET] == oldres or oldres in link[ATTRIBUTES].values():
            oldrids.add(rid)
            new_link = (newres if o == oldres else o, r, newres if t == oldres else t, dict((k, newres if v == oldres else v) for k, v in a.items()))
            model.add(*new_link)
    model.delete(oldrids)
    return 

def agc_mixed_004_02(self, format, resource, locale, domain=None):
        """
        Adds a resource
        @type format: str
        @param format: Name of the loader (@see add_loader)

        @type resource: str
        @param resource: The resource name

        @type locale: str
        @type domain: str

        @raises: ValueError If the locale contains invalid characters
        @return:
        """
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', locale):
            raise ValueError("Locale contains invalid characters")

        if domain is None:
            domain = 'default'

        if format not in self._loaders:
            raise ValueError(f"Loader '{format}' not registered")

        self._resources[format][locale][domain][resource] = True 

def hwc_mixed_004_03(self, tables=None, database=None):
        """Retrieve a dictionary of columns."""
        # Get table data and columns from source database
        source = database if database else self.database
        tables = tables if tables else self.tables
        return {tbl: self.get_columns(tbl) for tbl in tqdm(tables, total=len(tables),
                                                           desc='Getting {0} columns'.format(source))} 

def hwc_mixed_004_04(workflow, highlight=None):
    """Run workflow on multi-threaded worker cached with Sqlite3.

    :param workflow: workflow to evaluate.
    :param highlight: highlight these lines.
    """
    from noodles.run.threading.sqlite3 import run_parallel
    from noodles import serial

    import io
    import logging

    log = io.StringIO()
    log_handler = logging.StreamHandler(log)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    log_handler.setFormatter(formatter)

    logger = logging.getLogger('noodles')
    logger.setLevel(logging.INFO)
    logger.handlers = [log_handler]

    result = run_parallel(
        workflow, n_threads=4, registry=serial.base, db_file='tutorial.db',
        always_cache=True, echo_log=False)
    display_text(log.getvalue(), highlight or [], split_at=40)
    return result 

def agc_mixed_004_05(self, stat, file_object, knowledge_base):
    """Parse the status file."""
    content = file_object.read()
    for line in content.splitlines():
        if not line or line.startswith('#'):
            continue
        try:
            key, value = line.split('=', 1)
            knowledge_base[key.strip()] = value.strip()
        except ValueError:
            continue
    return knowledge_base 

def agc_mixed_004_06(self, url, data=None, params=None):
        """
        Low-level PATCH request interface to mite. Takes a URL to request
        (relative), and optionally data to add to the request. Either returns
        the JSON body of the request or raises a HttpException.

        """
        import requests
        from .exceptions import HttpException

        full_url = f"{self.base_url}{url}"
        try:
            response = requests.patch(full_url, data=data, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HttpException(str(e)) from e
