def agc_mixed_003_01(self, additional_headers=None, **kwargs):
        """Prepare headers for http communication.

        Return dict of header to be used in requests.

        Args:
            .. versionadded:: 0.3.2
                **additional_headers**: (optional) Additional headers
                to be used with request

        Returns:
            Headers dict. Key and values are string

        """
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.access_token)
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers 

def hwc_mixed_003_02(self):
        """ Delete a library section. """
        try:
            return self._server.query('/library/sections/%s' % self.key, method=self._server._session.delete)
        except BadRequest:  # pragma: no cover
            msg = 'Failed to delete library %s' % self.key
            msg += 'You may need to allow this permission in your Plex settings.'
            log.error(msg)
            raise 

def agc_mixed_003_03(bytes, mimetype):
    """ This function finds URLs inside of PDF bytes. """

    # Start with only the ASCII bytes. Limit it to 12+ character strings.
    if mimetype != 'application/pdf':
        return []
    urls = []
    try:
        pdf = PdfFileReader(BytesIO(bytes))
        for page in range(pdf.getNumPages()):
            page_obj = pdf.getPage(page)
            page_text = page_obj.extractText()
            urls.extend(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', page_text))
    except:
        pass
    return urls 

def hwc_mixed_003_04(self):
        """
            Display the information (with a pretty print) about the method
        """
        self.show_info()
        self.show_notes()
        if self.code != None:
            self.each_params_by_register(self.code.get_registers_size(),
                                         self.get_descriptor())
            self.code.show(self.CM.get_vmanalysis().get_method(self))
            self.show_xref(self.CM.get_vmanalysis().get_method_analysis(self)) 

def hwc_mixed_003_05(self):
        """Helper for session-related API calls."""
        if self._spanner_api is None:
            credentials = self._instance._client.credentials
            if isinstance(credentials, google.auth.credentials.Scoped):
                credentials = credentials.with_scopes((SPANNER_DATA_SCOPE,))
            self._spanner_api = SpannerClient(
                credentials=credentials, client_info=_CLIENT_INFO
            )
        return self._spanner_api 

def agc_mixed_003_06(self, obj, name, column):
        """
        Format the value of the attribute 'name' from the given object
        """
        val = getattr(obj, name)
        if column.type.python_type == datetime.datetime:
            return val.strftime("%Y-%m-%d %H:%M:%S")
        elif column.type.python_type == datetime.date:
            return val.strftime("%Y-%m-%d")
        elif column.type.python_type == datetime.time:
            return val.strftime("%H:%M:%S")
        else:
            return val
