def agc_mixed_005_01(self, request, *args, **kwargs):
        """
        If the URL slug doesn't match an object, try slugifying the URL param
        and searching alt_url for that.
        If found, redirect to the canonical URL.
        If still not found, raise 404.
        """

        try:
            return super(SlugOrAltUrlRetrieveMixin, self).retrieve(request, *args, **kwargs)
        except Http404:
            try:
                slug = request.resolver_match.kwargs.get('slug')
                alt_url = self.get_alt_url(slug)
                if alt_url:
                    return redirect(alt_url)
            except Http404:
                raise
            except Exception:
                pass
        raise Http404 

def hwc_mixed_005_02(self):
        """Serialize an object into dictionary form.  Useful if you have to
        serialize an array of objects into JSON.  Otherwise, if you call the
        :meth:`to_json` method on each object in the list and then try to
        dump the array, you end up with an array with one string."""

        j = {}
        for p in self.properties:
            try:
                v = getattr(self, p)
            except AttributeError:
                continue
            if v is not None:
                if p == 't':
                    j[p] = getattr(self, p).isoformat()
                else:
                    j[p] = getattr(self, p)

        return j 

def agc_mixed_005_03(source_string):
    """
    A port of the functionality of in_cksum() from ping.c
    Ideally this would act on the string as a series of 16-bit ints (host
    packed), but this works.
    Network data is big-endian, hosts are typically little-endian
    """
    sum = 0
    count_to = (len(source_string) / 2) * 2
    count = 0
    while count < count_to:
        this_val = ord(source_string[count + 1]) * 256 + ord(source_string[count])
        sum = sum + this_val
        sum = sum & 0xffffffff  # Necessary?
        count = count + 2
    if count_to < len(source_string):
        sum = sum + ord(source_string[len(source_string) - 1])
        sum = sum & 0xffffffff  # Necessary?
    sum = (sum >> 16) + (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff
    # Swap bytes. Bugger me if I know why.
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer 

def hwc_mixed_005_04(self, evernote_filter):
        """
            get the notes related to the filter
            :param evernote_filter: filtering
            :return: notes
        """
        data = []

        note_store = self.client.get_note_store()
        our_note_list = note_store.findNotesMetadata(self.token, evernote_filter, 0, 100,
                                                     EvernoteMgr.set_evernote_spec())

        for note in our_note_list.notes:
            whole_note = note_store.getNote(self.token, note.guid, True, True, False, False)
            content = self._cleaning_content(whole_note.content)
            data.append({'title': note.title, 'my_date': arrow.get(note.created),
                         'link': whole_note.attributes.sourceURL, 'content': content})

        return data 

def agc_mixed_005_05(self):
    """Checks state names and destinations for validity.

    Each destination state must exist, be a valid name and
    not be a reserved name.
    There must be a 'Start' state and if 'EOF' or 'End' states are specified,
    they must be empty.

    Returns:
      True if FSM is valid.

    Raises:
      TextFSMTemplateError: If any state definitions are invalid.
    """

    # Must have 'Start' state.
    if not self.states:
      raise TextFSMTemplateError('No states defined.')
    if not self.states.get('Start'):
      raise TextFSMTemplateError('No Start state defined.')
    if self.states.get('EOF'):
      raise TextFSMTemplateError('EOF state cannot have a destination.')
    if self.states.get('End'):
      raise TextFSMTemplateError('End state cannot have a destination.')
    for state in self.states:
      if state in self.RESERVED_STATE_NAMES:
        raise TextFSMTemplateError('State name %s is reserved.' % state)
      if not self.states[state]:
        raise TextFSMTemplateError('State %s has no destination.' % state)
      if not self.states[state] in self.states:
        raise TextFSMTemplateError('State %s has invalid destination %s.' %
                                   (state, self.states[state]))
    return True 

def hwc_mixed_005_06(self):
        """Argument specific to playbook apps.

        These arguments will be passed to every playbook app by default.

        --tc_playbook_db_type type        The DB type (currently on Redis is supported).
        --tc_playbook_db_context context  The playbook context provided by TC.
        --tc_playbook_db_path path        The DB path or server name.
        --tc_playbook_db_port port        The DB port when required.
        --tc_playbook_out_variables vars  The output variable requested by downstream apps.
        """

        self.add_argument(
            '--tc_playbook_db_type', default=self._tc_playbook_db_type, help='Playbook DB type'
        )
        self.add_argument(
            '--tc_playbook_db_context',
            default=self._tc_playbook_db_context,
            help='Playbook DB Context',
        )
        self.add_argument(
            '--tc_playbook_db_path', default=self._tc_playbook_db_path, help='Playbook DB path'
        )
        self.add_argument(
            '--tc_playbook_db_port', default=self._tc_playbook_db_port, help='Playbook DB port'
        )
        self.add_argument(
            '--tc_playbook_out_variables', help='Playbook output variables', required=False
        )
