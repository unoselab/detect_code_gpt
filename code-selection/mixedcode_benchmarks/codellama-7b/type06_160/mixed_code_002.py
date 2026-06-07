def hwc_mixed_002_01(self, lang, field):
        """
        Return the translation string of an specific field in a Translatable
        istance

        @type lang: string
        @param lang: a string with the name of the language

        @type field: string
        @param field: a string with the name that we try to get

        @rtype: string
        @return: Returns a translation string
        """
        # Read from cache
        key = self._get_translation_cache_key(lang, field)
        trans = cache.get(key, '')

        if not trans:
            trans_obj = self.get_translation_obj(lang, field)
            trans = getattr(trans_obj, 'translation', '')
            # if there's no translation text fall back to the model field
            if not trans:
                trans = getattr(self, field, '')
            # update cache
            cache.set(key, trans)
        return trans 

def agc_mixed_002_02(name, value, check_keys, opts):
    """Encode a mapping type."""
    items = []
    for item_key, item_value in value.items():
        if check_keys and item_key.startswith('_'):
            raise TypeError(
                "Detected private key '{0}' in mapping. "
                'Remove the underscore prefix to use it.'.format(item_key))
        if isinstance(item_value, Mapping):
            item_value = _encode_mapping(item_key, item_value, check_keys, opts)
        elif isinstance(item_value, Sequence):
            item_value = _encode_sequence(item_key, item_value, check_keys, opts)
        items.append((item_key, item_value))
    return {name: items} 

def hwc_mixed_002_03(name):
    """
    Return information about a group

    Args:

        name (str):
            The name of the group for which to get information

    Returns:
        dict: A dictionary of information about the group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    """
    try:
        groupObj = _get_group_object(name)
        gr_name = groupObj.Name
        gr_mem = [_get_username(x) for x in groupObj.members()]
    except pywintypes.com_error as exc:
        msg = 'Failed to access group {0}. {1}'.format(
            name, win32api.FormatMessage(exc.excepinfo[5]))
        log.debug(msg)
        return False

    if not gr_name:
        return False

    return {'name': gr_name,
            'passwd': None,
            'gid': None,
            'members': gr_mem} 

def agc_mixed_002_04(self, argv):
        """
        Set up any environment changes requested (e.g., Python path
        and Django settings), then run this command. If the
        command raises a ``CommandError``, intercept it and print it sensibly
        to stderr.
        """
        if self.use_unicode_console_output():
            encoding.set_console_output_encoding()

        # Set up the Python path.
        self.setup_paths(self.app)

        # Set up the Django settings.
        self.setup_environ(self.app)

        # Command-specific setup.
        self.handle_default_options()

        # Run the command.
        try:
            self.execute(*self.parse_args(argv))
        except CommandError as e:
            self.stderr.write('%s: %s' % (e.__class__.__name__, e))
            sys.exit(1) 

def agc_mixed_002_05(self, context):

		"""
		Applies database changes.

		:param resort.engine.execution.Context context:
		   Current execution context.
		"""

		db = context.db

		# Get the database cursor.
		cursor = db.cursor()

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema.
		schema = context.schema

		# Get the database schema 

def hwc_mixed_002_06(self, scale, f, loop=3):
        """Get the running parameters (e.g. quark masses and the strong
        coupling at a given scale."""
        p = {}
        p['alpha_s'] = qcd.alpha_s(scale, self.f, self.parameters['alpha_s'], loop=loop)
        p['m_b'] = qcd.m_b(self.parameters['m_b'], scale, self.f, self.parameters['alpha_s'], loop=loop)
        p['m_c'] = qcd.m_c(self.parameters['m_c'], scale, self.f, self.parameters['alpha_s'], loop=loop)
        p['m_s'] = qcd.m_s(self.parameters['m_s'], scale, self.f, self.parameters['alpha_s'], loop=loop)
        p['m_u'] = qcd.m_s(self.parameters['m_u'], scale, self.f, self.parameters['alpha_s'], loop=loop)
        p['m_d'] = qcd.m_s(self.parameters['m_d'], scale, self.f, self.parameters['alpha_s'], loop=loop)
        # running ignored for alpha_e and lepton mass
        p['alpha_e'] = self.parameters['alpha_e']
        p['m_e'] = self.parameters['m_e']
        p['m_mu'] = self.parameters['m_mu']
        p['m_tau'] = self.parameters['m_tau']
        return p
