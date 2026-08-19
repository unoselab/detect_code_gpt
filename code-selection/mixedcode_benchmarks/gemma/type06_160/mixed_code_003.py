def hwc_mixed_003_01(cert_uri, cache):
  """Get certs from cache if present; otherwise, gets from URI and caches them.

  Args:
    cert_uri: URI from which to retrieve certs if cache is stale or empty.
    cache: Cache of pre-fetched certs.

  Returns:
    The retrieved certs.
  """
  certs = cache.get(cert_uri, namespace=_CERT_NAMESPACE)
  if certs is None:
    _logger.debug('Cert cache miss for %s', cert_uri)
    try:
      result = urlfetch.fetch(cert_uri)
    except AssertionError:
      # This happens in unit tests.  Act as if we couldn't get any certs.
      return None

    if result.status_code == 200:
      certs = json.loads(result.content)
      expiration_time_seconds = _get_cert_expiration_time(result.headers)
      if expiration_time_seconds:
        cache.set(cert_uri, certs, time=expiration_time_seconds,
                  namespace=_CERT_NAMESPACE)
    else:
      _logger.error(
          'Certs not available, HTTP request returned %d', result.status_code)

  return certs 

def hwc_mixed_003_02():
    """A Challenge Dataset for Open-Domain Question Answering.

    WikiQA dataset is a publicly available set of question and sentence (QS) pairs,
    collected and annotated for research on open-domain question answering.

    source: "Microsoft"
    sourceURI: "https://www.microsoft.com/en-us/research/publication/wikiqa-a-challenge-dataset-for-open-domain-question-answering/#"
    """  # noqa

    dataset_path = _load('wikiqa')

    data = _load_csv(dataset_path, 'data', set_index=True)
    questions = _load_csv(dataset_path, 'questions', set_index=True)
    sentences = _load_csv(dataset_path, 'sentences', set_index=True)
    vocabulary = _load_csv(dataset_path, 'vocabulary', set_index=True)

    entities = {
        'data': (data, 'd3mIndex', None),
        'questions': (questions, 'qIndex', None),
        'sentences': (sentences, 'sIndex', None),
        'vocabulary': (vocabulary, 'index', None)
    }
    relationships = [
        ('questions', 'qIndex', 'data', 'qIndex'),
        ('sentences', 'sIndex', 'data', 'sIndex')
    ]

    target = data.pop('isAnswer').values

    return Dataset(load_wikiqa.__doc__, data, target, accuracy_score, startify=True,
                   entities=entities, relationships=relationships) 

def agc_mixed_003_03(self, address, rpc_id):
        """Call an RPC and receive the result as an integer.

        If the RPC does not properly return a 32 bit integer, raise a warning
        unless it cannot be converted into an integer at all, in which case
        a HardwareError is thrown.

        Args:
            address (int): The address of the tile we want to call the RPC
                on
            rpc_id (int): The id of the RPC that we want to call

        Returns:
            int: The result of the RPC call.  If the rpc did not succeed
                an error is thrown instead.
        """

        # Always allow mocking an RPC to override whatever the defaul behavior is
        try:
            result = self.call_rpc(address, rpc_id)
        except Exception as e:
            raise HardwareError(f"RPC call failed: {e}") from e

        try:
            int_result = int(result)
        except (ValueError, TypeError):
            raise HardwareError(f"RPC result {result} cannot be converted to integer")

        if not (0 <= int_result <= 0xFFFFFFFF):
            import warnings
            warnings.warn(f"RPC result {int_result} is not a 32-bit integer")

        return int_result 

def agc_mixed_003_04(self, flags):
        """Implement the XInclude substitution on the XML document @doc """
        import lxml.etree as ET

        if flags is None:
            flags = 0

        # The lxml library provides a built-in XInclude processor
        # that handles the substitution based on the document's structure.
        try:
            self.doc.xinclude(flags)
        except Exception as e:
            # Depending on the specific framework requirements,
            # you might want to log this or re-raise.
            raise e 

def hwc_mixed_003_05(request, email_template, base_url, context):
    """
    Internal rendering of the placeholder/contentitems.

    This a simple variation of render_placeholder(),
    making is possible to render both a HTML and text item in a single call.
    Caching is currently not implemented.

    :rtype: fluentcms_emailtemplates.rendering.EmailBodyContent
    """
    placeholder = email_template.contents
    items = placeholder.get_content_items(email_template)

    if not items:  # NOTES: performs query
        # There are no items, fetch the fallback language.
        language_code = fc_appsettings.FLUENT_CONTENTS_DEFAULT_LANGUAGE_CODE
        items = placeholder.get_content_items(email_template, limit_parent_language=False).translated(language_code)

    html_fragments = []
    text_fragments = []

    for instance in items:
        plugin = instance.plugin
        html_part = _render_html(plugin, request, instance, context)
        text_part = _render_text(plugin, request, instance, context, base_url)
        html_fragments.append(html_part)
        text_fragments.append(text_part)

    html_body = u"".join(html_fragments)
    text_body = u"".join(text_fragments)

    return EmailBodyContent(text_body, html_body) 

def agc_mixed_003_06(prompt='', default=None, ispass=False, use_readline=True):
	"""Handles raw_input calls, and switches off interactivity if there is apparently
	no controlling terminal (or there are any other problems)
	"""
	import sys
	try:
	    import readline
	except ImportError:
	    readline = None

	if use_readline and readline:
	    try:
	        import rlcompleter
	        readline.parse_and_bind("tab: complete")
	    except Exception:
	        pass

	try:
	    if not sys.stdin.isatty():
	        raise IOError("No controlling terminal")
	except (AttributeError, IOError):
	    if default is not None:
	        return default
	    return ""

	if ispass:
	    import getpass
	    return getpass.getpass(prompt)

	try:
	    line = input(prompt) if sys.version_info[0] >= 3 else raw_input(prompt)
	    if not line and default is not None:
	        return default
	    return line
	except EOFError:
	    return default if default is not None else ""
