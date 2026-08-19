def hwc_mixed_002_01(pdf_name, pages_per_q) -> None:
    """
    Checks if PDF has the correct number of pages. If it has too many, warns
    the user. If it has too few, adds blank pages until the right length is
    reached.
    """
    pdf = PyPDF2.PdfFileReader(pdf_name)
    output = PyPDF2.PdfFileWriter()
    num_pages = pdf.getNumPages()
    if num_pages > pages_per_q:
        logging.warning('{} has {} pages. Only the first '
                        '{} pages will get output.'
                        .format(pdf_name, num_pages, pages_per_q))

    # Copy over up to pages_per_q pages
    for page in range(min(num_pages, pages_per_q)):
        output.addPage(pdf.getPage(page))

    # Pad if necessary
    if num_pages < pages_per_q:
        for page in range(pages_per_q - num_pages):
            output.addBlankPage()

    # Output the PDF
    with open(pdf_name, 'wb') as out_file:
        output.write(out_file) 

def agc_mixed_002_02(self, date, course_id, grader_id, assignment_id):
        """
        Lists submissions.

        Gives a nested list of submission versions
        """
        submissions = self.db.query(
            "SELECT submission_id, version_id, student_id, timestamp "
            "FROM submissions "
            "WHERE date = ? AND course_id = ? AND grader_id = ? AND assignment_id = ? "
            "ORDER BY submission_id, version_id",
            (date, course_id, grader_id, assignment_id)
        )

        result = {}
        for sub_id, ver_id, student_id, timestamp in submissions:
            if sub_id not in result:
                result[sub_id] = []
            result[sub_id].append((ver_id, student_id, timestamp))

        return list(result.values()) 

def hwc_mixed_002_03():
        """
            Riak checks the connection
            It displays on the screen whether or not you have a connection.
        """
        from pyoko.db.connection import client
        from socket import error as socket_error

        try:
            if client.ping():
                print(__(u"{0}Riak is working{1}").format(CheckList.OKGREEN, CheckList.ENDC))
            else:
                print(__(u"{0}Riak is not working{1}").format(CheckList.FAIL, CheckList.ENDC))
        except socket_error as e:
            print(__(u"{0}Riak is not working{1}").format(CheckList.FAIL,
                                                          CheckList.ENDC), e.message) 

def hwc_mixed_002_04(self, imports):
        """Print additional imports needed for protorpc."""
        google_imports = [x for x in imports if 'google' in x]
        other_imports = [x for x in imports if 'google' not in x]
        if other_imports:
            for import_ in sorted(other_imports):
                self.__printer(import_)
            self.__printer()
        # Note: If we ever were going to add imports from this package, we'd
        # need to sort those out and put them at the end.
        if google_imports:
            for import_ in sorted(google_imports):
                self.__printer(import_)
            self.__printer() 

def agc_mixed_002_05(fixed_text, cur=0):
    """Matches given text at cursor position with non rule patterns

    Returns a dictionary of three elements:

    - "matched" - Bool: depending on if match found
    - "found" - string/None: Value of matched pattern's 'find' key or none
    - "replaced": string Replaced string if match found else input string at
    cursor

     """
    import re
    patterns = [
        {"find": r"\s+", "replaced": " "},
        {"find": r"\s+", "replaced": ""},
    ]
    for p in patterns:
        match = re.match(p["find"], fixed_text[cur:])
        if match:
            return {
                "matched": True,
                "found": p["find"],
                "replaced": p["replaced"]
            }
    return {
        "matched": False,
        "found": None,
        "replaced": fixed_text[cur] if cur < len(fixed_text) else ""
    } 

def agc_mixed_002_06(identifier, namespace='cid', domain='compound', operation=None, output='JSON', searchtype=None, **kwargs):
    """Request wrapper that automatically handles async requests."""
    import requests
    import asyncio

    def sync_request():
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/{namespace}/{identifier}/{domain}"
        if operation:
            url += f"/{operation}"
        if output:
            url += f"/{output.lower()}"

        params = {}
        if searchtype:
            params['searchtype'] = searchtype
        params.update(kwargs)

        response = requests.get(url, params=params)
        response.raise_for_status()

        if output.upper() == 'JSON':
            return response.json()
        return response.text

    if asyncio.get_event_loop().is_running():
        return asyncio.to_thread(sync_request)
    return sync_request()
